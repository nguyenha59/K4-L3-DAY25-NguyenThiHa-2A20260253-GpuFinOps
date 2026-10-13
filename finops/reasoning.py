"""Reasoning traffic budgets on the lab's request and energy models.

This is a counterfactual cost analysis, not a measured energy benchmark. The
generator already expands reasoning output by 6x, then wh_per_query applies
its separate 80x multiplier to the complete recorded token count.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence

from finops.pricing import dollars_per_million
from finops.sustainability import REASONING_ENERGY_MULTIPLIER, wh_per_query

Request = Mapping[str, object]
CostFunction = Callable[[Request], float]


def _integer(value: object, field: str) -> int:
    """Accept raw CSV integers and numeric values without silent truncation."""
    number = float(value)
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError(f"{field} must be a nonnegative integer")
    return int(number)


def _finite_nonnegative(value: object, field: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be finite and nonnegative")
    return number


def _is_reasoning(row: Request) -> bool:
    flag = _integer(row["is_reasoning"], "is_reasoning")
    if flag not in (0, 1):
        raise ValueError("is_reasoning must be 0 or 1")
    return bool(flag)


def _normal_request(row: Request, output_factor: int) -> dict:
    """Preserve route, input, cache and batch; contract only reasoning output."""
    result = dict(row)
    result["output_tokens"] = _integer(row["output_tokens"], "output_tokens") // output_factor
    result["is_reasoning"] = 0
    return result


def _measure(row: Request, cost_fn: CostFunction, wh_per_1k_tokens: float) -> dict:
    inp = _integer(row["input_tokens"], "input_tokens")
    out = _integer(row["output_tokens"], "output_tokens")
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "cost_usd": _finite_nonnegative(cost_fn(row), "request cost"),
        "wh": wh_per_query(inp + out, wh_per_1k_tokens, _is_reasoning(row)),
        "is_reasoning": _is_reasoning(row),
    }


def _summary(measurements: Sequence[dict]) -> dict:
    totals = {
        "requests": len(measurements),
        "input_tokens": sum(m["input_tokens"] for m in measurements),
        "output_tokens": sum(m["output_tokens"] for m in measurements),
        "total_tokens": sum(m["total_tokens"] for m in measurements),
        "cost_usd": math.fsum(m["cost_usd"] for m in measurements),
        "wh": math.fsum(m["wh"] for m in measurements),
    }
    totals["cost_per_million_tokens_usd"] = dollars_per_million(
        totals["cost_usd"], totals["total_tokens"]
    )
    return totals


def _groups(measurements: Sequence[dict], totals: dict) -> dict:
    result = {}
    for label, flag in (("reasoning", True), ("standard", False)):
        group = _summary([m for m in measurements if m["is_reasoning"] is flag])
        for name, denominator in (
            ("traffic_pct", "requests"),
            ("token_share_pct", "total_tokens"),
            ("cost_share_pct", "cost_usd"),
            ("energy_share_pct", "wh"),
        ):
            group[name] = 100.0 * group[denominator] / totals[denominator] if totals[denominator] else 0.0
        result[label] = group
    return result


def analyze_reasoning(
    rows: Sequence[Request],
    cost_fn: CostFunction,
    cap_fractions: Sequence[float] = (0.10, 0.05),
    wh_per_1k_tokens: float = 0.30,
    normal_output_factor: int = 6,
) -> dict:
    """Return JSON-serializable observed groups and request-share cap scenarios.

    ``rows`` use token_usage.csv's field names; ``cost_fn(row)`` must use the
    chosen billing policy for both observed and counterfactual requests. For
    example, M2's optimized prices hold route_tier, cached input and is_batch
    fixed. A pure callback must not change the row it receives.

    For each cap, reroute the excess reasoning requests with the highest
    incremental USD cost first, then energy, then original row position. This
    ranks potential savings, not task suitability. In production, independently
    validate which tasks can use standard responses without quality loss.

    Every cap is evaluated independently against the observed dataset. A cap
    already satisfied changes no requests and claims zero savings. Rerouting
    preserves request count but reduces output tokens; unit costs therefore
    use the scenario's new token denominator.
    """
    wh_rate = _finite_nonnegative(wh_per_1k_tokens, "wh_per_1k_tokens")
    factor = _integer(normal_output_factor, "normal_output_factor")
    if factor < 1:
        raise ValueError("normal_output_factor must be at least 1")
    caps = [float(cap) for cap in cap_fractions]
    if any(not math.isfinite(cap) or not 0.0 <= cap <= 1.0 for cap in caps):
        raise ValueError("cap fractions must be between 0 and 1")
    if len(set(caps)) != len(caps):
        raise ValueError("cap fractions must be unique")

    observed = [_measure(row, cost_fn, wh_rate) for row in rows]
    reasoning_indices = [i for i, m in enumerate(observed) if m["is_reasoning"]]
    normal = {
        i: _measure(_normal_request(rows[i], factor), cost_fn, wh_rate)
        for i in reasoning_indices
    }
    totals = _summary(observed)
    groups = _groups(observed, totals)
    gross_reasoning = groups["reasoning"]
    normal_totals = _summary(list(normal.values()))
    # Same recorded tokens isolate the energy flag from output expansion.
    same_token_standard = []
    for i in reasoning_indices:
        row = dict(rows[i])
        row["is_reasoning"] = 0
        same_token_standard.append(_measure(row, cost_fn, wh_rate))
    same_token_totals = _summary(same_token_standard)
    incremental = {
        "normal_output_counterfactual": normal_totals,
        "same_token_standard_counterfactual": same_token_totals,
        "cost_usd": gross_reasoning["cost_usd"] - normal_totals["cost_usd"],
        "wh": gross_reasoning["wh"] - normal_totals["wh"],
        "extra_output_tokens": gross_reasoning["output_tokens"] - normal_totals["output_tokens"],
        "same_token_extra_cost_usd": gross_reasoning["cost_usd"] - same_token_totals["cost_usd"],
        "same_token_extra_wh": gross_reasoning["wh"] - same_token_totals["wh"],
    }
    ranked = sorted(
        reasoning_indices,
        key=lambda i: (
            -(observed[i]["cost_usd"] - normal[i]["cost_usd"]),
            -(observed[i]["wh"] - normal[i]["wh"]),
            i,
        ),
    )
    scenarios = {}
    for cap in caps:
        maximum = math.floor(len(rows) * cap + 1e-12)
        reroute_count = max(0, len(reasoning_indices) - maximum)
        selected = ranked[:reroute_count]
        selected_set = set(selected)
        after = [normal[i] if i in selected_set else m for i, m in enumerate(observed)]
        after_totals = _summary(after)
        after_groups = _groups(after, after_totals)
        cost_savings = math.fsum(observed[i]["cost_usd"] - normal[i]["cost_usd"] for i in selected)
        energy_savings = math.fsum(observed[i]["wh"] - normal[i]["wh"] for i in selected)
        scenario = {
            "cap_fraction": cap,
            "cap_pct": cap * 100.0,
            "max_reasoning_requests": maximum,
            "before_reasoning_requests": len(reasoning_indices),
            "after_reasoning_requests": len(reasoning_indices) - reroute_count,
            "rerouted_requests": reroute_count,
            "rerouted_row_indices": selected,
            "status": "cap_already_satisfied" if reroute_count == 0 else "modeled_rerouting",
            "totals": after_totals,
            "groups": after_groups,
            "cost_savings_usd": cost_savings,
            "cost_savings_pct": cost_savings / totals["cost_usd"] * 100.0 if totals["cost_usd"] else 0.0,
            "energy_savings_wh": energy_savings,
            "energy_savings_pct": energy_savings / totals["wh"] * 100.0 if totals["wh"] else 0.0,
            "output_token_reduction": totals["output_tokens"] - after_totals["output_tokens"],
        }
        scenarios[f"cap_{cap * 100:g}_pct"] = scenario
    return {
        "totals": totals,
        "groups": groups,
        "incremental_reasoning": incremental,
        "scenarios": scenarios,
        "assumptions": {
            "energy_model": "wh_per_query from finops.sustainability; modeled, not measured power",
            "wh_per_1k_tokens": wh_rate,
            "reasoning_energy_multiplier": REASONING_ENERGY_MULTIPLIER,
            "normal_output_factor": factor,
            "output_model": "Recorded reasoning output already includes 6x from data/generate.py; normal output uses integer division by normal_output_factor",
            "energy_composition": "The 80x multiplier applies after the recorded 6x output expansion, so comparing differing token counts does not imply an overall 80x per request",
            "fixed_fields": ["model", "route_tier", "input_tokens", "cached_input_tokens", "is_batch"],
            "cap_basis": "Reasoning request count / all requests, rounded down to whole requests",
            "selection": "Highest incremental cost, then incremental Wh, then source row index; economic scenario only",
            "routing_rule": "Run standard model first; allow reasoning only if calibrated confidence < 0.70 or a validated complex-task rule fires, within the request-share budget",
            "routing_limitations": "No confidence, complexity or answer-quality labels exist in the synthetic data; the 0.70 threshold is a proposed policy and cannot be evaluated here",
            "quality": "A/B evaluation and quality/SLA checks are required before enforcing either cap; savings do not guarantee equivalent responses",
            "aggregation": "Cap scenarios are alternatives and must not be summed or added to already-counted mission savings",
        },
    }
