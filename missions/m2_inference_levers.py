"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, cache_economics, reasoning

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    cache_analysis = cache_economics.analyze_cache(rows, MODEL_PRICES)
    base_cost = opt_cost = 0.0
    cascade_cost = cache_cost = legacy_cost = 0.0
    total_tokens = 0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        cascade_cost += pricing.request_cost(inp, out, pin, pout)
        cache_cost += cache_economics.request_cost_with_cache_policy(
            dict(r, is_batch="0"), MODEL_PRICES, cache_analysis)
        legacy_cost += pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        opt_cost += cache_economics.request_cost_with_cache_policy(r, MODEL_PRICES, cache_analysis)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    stages = []
    previous = base_cost
    for name, cost in (("Baseline: large, no cache/batch", base_cost),
                       ("Cascade", cascade_cost), ("Cache (gate + write premium)", cache_cost),
                       ("Batch", opt_cost)):
        stages.append({"name": name, "daily_usd": cost,
                       "per_m": pricing.dollars_per_million(cost, total_tokens),
                       "incremental_savings_daily": previous - cost})
        previous = cost
    reasoning_analysis = reasoning.analyze_reasoning(
        rows, lambda row: cache_economics.request_cost_with_cache_policy(row, MODEL_PRICES, cache_analysis))

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print("Sequential attribution (fixed input+output token denominator):")
        for stage in stages:
            print(f"  {stage['name']}: ${stage['daily_usd']:.6f}/day, ${stage['per_m']:.3f}/1M-token")
        print(f"Legacy free-write cache: ${legacy_cost:.6f}/day; policy includes cache writes.")
        for tier, policy in cache_analysis["tiers"].items():
            print(f"  cache {tier}: reuse={policy['effective_avg_reads']}, threshold={policy['break_even_reads']}, enabled={policy['cache_enabled']}")
        for name, group in reasoning_analysis["groups"].items():
            print(f"  {name}: {group['requests']} requests ({group['traffic_pct']:.3f}%), "
                  f"${group['cost_usd']:.6f}/day ({group['cost_share_pct']:.2f}%), "
                  f"{group['wh']:.3f} modeled Wh/day")
        for scenario in reasoning_analysis["scenarios"].values():
            print(f"  reasoning cap {scenario['cap_pct']:.0f}%: reroute={scenario['rerouted_requests']}, "
                  f"save ${scenario['cost_savings_usd']:.6f}/day, {scenario['energy_savings_wh']:.3f} modeled Wh/day")
        print("Cache and reasoning assumptions + modeled scenarios are recorded in outputs/report.md.")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "request_count": len(rows), "stages": stages,
        "legacy_optimized_daily": legacy_cost,
        "baseline_daily_exact": base_cost, "optimized_daily_exact": opt_cost,
        "cache": cache_analysis, "reasoning": reasoning_analysis,
    }


if __name__ == "__main__":
    run()
