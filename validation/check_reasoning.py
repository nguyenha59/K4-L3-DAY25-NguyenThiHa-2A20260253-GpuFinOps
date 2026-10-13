"""Independent regression checks for Your Turn #4; existing tests stay intact.

Run from the repository root: python validation/check_reasoning.py
"""
from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finops import pricing
from finops.reasoning import analyze_reasoning
from missions._common import load_csv
from missions.m2_inference_levers import MODEL_PRICES


def optimized_cost(row: dict) -> float:
    pin, pout = MODEL_PRICES[row["route_tier"]]
    return pricing.request_cost(
        int(row["input_tokens"]), int(row["output_tokens"]), pin, pout,
        cached_in=int(row["cached_input_tokens"]), batch=bool(int(row["is_batch"])),
    )


def check() -> dict:
    rows = load_csv("token_usage.csv")
    original = copy.deepcopy(rows)
    result = analyze_reasoning(rows, optimized_cost)
    json.dumps(result, allow_nan=False)
    assert rows == original, "Analysis must not mutate source requests"
    totals, groups = result["totals"], result["groups"]
    assert totals["requests"] == len(rows)
    assert sum(g["requests"] for g in groups.values()) == totals["requests"]
    for metric in ("input_tokens", "output_tokens", "total_tokens", "cost_usd", "wh"):
        assert math.isclose(sum(g[metric] for g in groups.values()), totals[metric], abs_tol=1e-9)
    same = result["incremental_reasoning"]["same_token_standard_counterfactual"]
    assert math.isclose(groups["reasoning"]["wh"], same["wh"] * 80.0, abs_tol=1e-8)
    assert math.isclose(groups["reasoning"]["cost_usd"], same["cost_usd"], abs_tol=1e-9)
    assert result["incremental_reasoning"]["cost_usd"] < groups["reasoning"]["cost_usd"]
    cap10 = result["scenarios"]["cap_10_pct"]
    assert groups["reasoning"]["traffic_pct"] < 10.0
    assert cap10["rerouted_requests"] == 0
    assert cap10["cost_savings_usd"] == cap10["energy_savings_wh"] == 0.0
    assert cap10["totals"] == totals
    cap5 = result["scenarios"]["cap_5_pct"]
    assert cap5["groups"]["reasoning"]["traffic_pct"] <= 5.0
    assert cap5["rerouted_requests"] > 0
    assert cap5["cost_savings_usd"] > 0 and cap5["energy_savings_wh"] > 0
    assert cap5["totals"]["total_tokens"] < totals["total_tokens"]
    assert math.isclose(
        cap5["totals"]["cost_per_million_tokens_usd"],
        cap5["totals"]["cost_usd"] / cap5["totals"]["total_tokens"] * 1e6,
    )
    assert math.isclose(cap5["totals"]["cost_usd"] + cap5["cost_savings_usd"], totals["cost_usd"])
    assert math.isclose(cap5["totals"]["wh"] + cap5["energy_savings_wh"], totals["wh"])
    assert result == analyze_reasoning(rows, optimized_cost), "Selection must be deterministic"

    # Construct unequal cost/energy candidates: choosing the highest cost
    # reduction must take precedence over the greatest token/energy reduction.
    candidates = [
        {"route_tier": "small", "input_tokens": 100, "output_tokens": 6000,
         "cached_input_tokens": 0, "is_batch": 0, "is_reasoning": 1},
        {"route_tier": "large", "input_tokens": 100, "output_tokens": 600,
         "cached_input_tokens": 0, "is_batch": 0, "is_reasoning": 1},
    ]
    ranked = analyze_reasoning(candidates, optimized_cost, cap_fractions=(0.5,))
    assert ranked["scenarios"]["cap_50_pct"]["rerouted_row_indices"] == [1]
    all_normal = analyze_reasoning(candidates, optimized_cost, cap_fractions=(0.0,))
    assert all_normal["scenarios"]["cap_0_pct"]["after_reasoning_requests"] == 0
    empty = analyze_reasoning([], optimized_cost)
    assert empty["totals"]["requests"] == 0 and empty["totals"]["cost_usd"] == 0
    standard = [dict(candidates[0], is_reasoning=0)]
    assert analyze_reasoning(standard, optimized_cost)["groups"]["reasoning"]["requests"] == 0
    for invalid_cap in (-0.1, 1.1, float("nan")):
        try:
            analyze_reasoning([], optimized_cost, cap_fractions=(invalid_cap,))
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid caps must be rejected")
    return result


if __name__ == "__main__":
    analysis = check()
    reasoning = analysis["groups"]["reasoning"]
    cap = analysis["scenarios"]["cap_5_pct"]
    print("Reasoning extension checks passed (source tests unchanged).")
    print(f"Reasoning: {reasoning['requests']} requests, {reasoning['traffic_pct']:.3f}% traffic, "
          f"${reasoning['cost_usd']:.6f}, {reasoning['wh']:.3f} modeled Wh")
    print(f"10% cap saves $0 and 0 Wh; 5% cap reroutes {cap['rerouted_requests']} requests, "
          f"saves ${cap['cost_savings_usd']:.6f} and {cap['energy_savings_wh']:.3f} modeled Wh")
