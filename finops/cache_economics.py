"""Cache economics including write premiums and honest reuse estimates.

The supplied token CSV has cached tokens but no prompt IDs, cache-write events,
TTL or ``avg_cache_reads``. Its generator documents a cacheable input fraction
of 70% for assistant/rag and 10% for other teams. We estimate cache-write token
equivalents as cacheable input minus cached input; cached / write equivalents
is an estimated token-equivalent reuse ratio, *not* observed reads per prompt.
If a caller supplies positive ``avg_cache_reads`` we instead use cached/reads
to obtain write equivalents. At zero reads we retain the cacheable-input write
estimate. Even then, those write equivalents are inferred.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from finops import pricing


def _cache_counts(row: Mapping) -> tuple[int, float, str]:
    """Return cached read tokens, inferred write tokens, and inference source."""
    inp = int(float(row["input_tokens"]))
    cached = min(inp, max(0, int(float(row.get("cached_input_tokens", 0)))))
    fraction = 0.7 if row.get("team") in ("assistant", "rag") else 0.1
    cacheable = int(inp * fraction)
    supplied = row.get("avg_cache_reads")
    if supplied not in (None, ""):
        avg_reads = float(supplied)
        if not math.isfinite(avg_reads) or avg_reads < 0:
            raise ValueError("avg_cache_reads must be finite and nonnegative")
        if avg_reads == 0 and cached:
            raise ValueError("Nonzero cached tokens contradict avg_cache_reads=0")
        # Zero reads still require an initial write in the ungated scenario.
        # Without write-event telemetry, retain the generator's inferred amount.
        writes = cached / avg_reads if avg_reads else float(cacheable)
        return cached, writes, "supplied_avg_cache_reads"
    return cached, float(max(0, cacheable - cached)), "estimated_token_equivalent_reuse"


def _batch_factor(row: Mapping, batch_discount: float = 0.5) -> float:
    return batch_discount if bool(int(float(row.get("is_batch", 0)))) else 1.0


def _row_cost(
    row: Mapping, model_prices: Mapping, enabled: bool,
    write_cost: float, read_discount: float,
) -> tuple[float, float]:
    inp = int(float(row["input_tokens"]))
    out = int(float(row["output_tokens"]))
    pin, pout = model_prices[row["route_tier"]]
    cached, writes, _ = _cache_counts(row)
    is_batch = bool(int(float(row.get("is_batch", 0))))
    cost = pricing.request_cost(
        inp, out, pin, pout, cached_in=cached if enabled else 0,
        cache_discount=read_discount, batch=is_batch,
    )
    # request_cost already includes the ordinary 1x input price for cache misses.
    # Charge the extra 0.25x for writes when write_cost is 1.25x; no free writes.
    premium = (write_cost - 1) * writes * pin / 1e6 * _batch_factor(row) if enabled else 0.0
    return cost + premium, premium


def request_cost_with_cache_policy(
    row: Mapping, model_prices: Mapping, analysis: Mapping,
) -> float:
    """Bill one routed/batched row using the same gated policy as M2 and M4.

    Reuse ``analyze_cache`` once for the complete dataset. All monetary values
    remain unrounded internally so allocation reconciles with aggregate costs.
    """
    enabled = analysis["tiers"][row["route_tier"]]["cache_enabled"]
    return _row_cost(
        row, model_prices, enabled,
        analysis["write_cost_multiplier"], analysis["read_discount"],
    )[0]


def analyze_cache(
    rows: Sequence[Mapping], model_prices: Mapping,
    write_cost: float = 1.25, read_discount: float = 0.10,
) -> dict:
    """Compare routed/batched bills with no cache, ungated cache and gated cache.

    The gate uses batch-weighted token equivalents so the decision compares
    dollars consistently, even if cached reads and writes have different batch
    proportions. Reports include unweighted reuse and its provenance as well.
    With the same price multipliers both model tiers have the same break-even
    read count; their dollar premiums and read savings differ by input price.
    """
    pricing.cache_is_worth_it(0, write_cost, read_discount)  # validate assumptions
    threshold = (write_cost - 1) / (1 - read_discount) if read_discount < 1 else None
    tiers = {}
    all_sources = set()
    for tier, (pin, _) in model_prices.items():
        tier_rows = [row for row in rows if row["route_tier"] == tier]
        reads = writes = effective_reads = effective_writes = 0.0
        sources = set()
        no_cache = ungated = premium = 0.0
        for row in tier_rows:
            cached, write_tokens, source = _cache_counts(row)
            sources.add(source)
            all_sources.add(source)
            reads += cached
            writes += write_tokens
            effective_reads += cached * _batch_factor(row)
            effective_writes += write_tokens * _batch_factor(row)
            no_cache += _row_cost(row, model_prices, False, write_cost, read_discount)[0]
            row_cached_cost, row_premium = _row_cost(row, model_prices, True, write_cost, read_discount)
            ungated += row_cached_cost
            premium += row_premium
        avg_reads = reads / writes if writes else None
        effective_avg = effective_reads / effective_writes if effective_writes else None
        if effective_avg is None:
            # No writes in this window: already warm cache is beneficial only if
            # there are reads with a discount. This does not prove zero setup cost.
            enabled = effective_reads > 0 and read_discount < 1
        else:
            enabled = pricing.cache_is_worth_it(effective_avg, write_cost, read_discount)
        gated = ungated if enabled else no_cache
        tiers[tier] = {
            "requests": len(tier_rows), "input_price_per_m": pin,
            "write_price_per_m": pin * write_cost,
            "read_price_per_m": pin * read_discount,
            "break_even_reads": threshold,
            "avg_reads": avg_reads, "effective_avg_reads": effective_avg,
            "read_basis": next(iter(sources)) if len(sources) == 1 else "mixed_or_empty",
            "cached_read_tokens": reads, "write_equivalent_tokens": writes,
            "cache_enabled": enabled,
            "no_cache_daily": no_cache, "ungated_daily": ungated,
            "gated_daily": gated, "write_premium_daily": premium if enabled else 0.0,
            "savings_daily": no_cache - gated,
            "savings_pct": (1 - gated / no_cache) * 100 if no_cache else 0.0,
        }
    no_cache_total = sum(tier["no_cache_daily"] for tier in tiers.values())
    gated_total = sum(tier["gated_daily"] for tier in tiers.values())
    sensitivity = []
    if threshold is not None:
        for label, reads in (("below", threshold / 2), ("equal", threshold), ("above", threshold + 1)):
            baseline = 1 + reads
            cached = write_cost + reads * read_discount
            sensitivity.append({
                "case": label, "avg_reads": reads,
                "cache_enabled": pricing.cache_is_worth_it(reads, write_cost, read_discount),
                "baseline_input_price_units": baseline,
                "cached_input_price_units": cached,
                "saving_input_price_units": baseline - cached,
            })
    return {
        "write_cost_multiplier": write_cost, "read_discount": read_discount,
        "break_even_reads": threshold,
        "read_basis": next(iter(all_sources)) if len(all_sources) == 1 else "mixed_or_empty",
        "assumptions": (
            f"Write multiplier {write_cost:g} and read multiplier {read_discount:g} are explicit lab scenarios; "
            "no storage/TTL charges are modelled. Without avg_cache_reads/prompt IDs, "
            "write equivalents use the generator's cacheable fractions (assistant/rag 70%, "
            "others 10%); inferred token-equivalent reuse is not observed prompt reads. "
            "Both ordinary processing and write premiums receive the lab's batch factor."
        ),
        "tiers": tiers, "sensitivity": sensitivity,
        "no_cache_daily": no_cache_total,
        "ungated_daily": sum(tier["ungated_daily"] for tier in tiers.values()),
        "gated_daily": gated_total,
        "write_premium_daily": sum(tier["write_premium_daily"] for tier in tiers.values()),
        "savings_daily": no_cache_total - gated_total,
        "savings_pct": (1 - gated_total / no_cache_total) * 100 if no_cache_total else 0.0,
    }
