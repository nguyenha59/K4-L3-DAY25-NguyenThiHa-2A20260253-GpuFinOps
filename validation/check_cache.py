"""Independent extension checks; instructor-owned tests/ remains unchanged.

Run from the repository root: python validation/check_cache.py
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finops import pricing
from finops.cache_economics import analyze_cache, request_cost_with_cache_policy
from missions._common import load_csv


PRICES = {"small": (0.2, 0.4), "large": (3.0, 15.0)}


def check_cache() -> None:
    threshold = (1.25 - 1) / (1 - 0.1)
    assert not pricing.cache_is_worth_it(0, 1.25, 0.1)
    assert not pricing.cache_is_worth_it(threshold / 2, 1.25, 0.1)
    assert not pricing.cache_is_worth_it(threshold, 1.25, 0.1)
    assert pricing.cache_is_worth_it(threshold + 0.1, 1.25, 0.1)
    assert pricing.cache_is_worth_it(1, 1.0, 0.1)
    assert not pricing.cache_is_worth_it(100, 1.25, 1.0)
    for args in ((-1, 1.25, 0.1), (1, 0.9, 0.1), (1, 1.25, 1.1), (math.nan, 1.25, 0.1)):
        try:
            pricing.cache_is_worth_it(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid cache assumptions accepted: {args}")

    # A low-reuse row would cost more with the write premium. The gate must
    # turn cache off and bill the ordinary input cost, preserving batch pricing.
    low_reuse = {
        "team": "assistant", "route_tier": "small", "input_tokens": 1000,
        "output_tokens": 100, "cached_input_tokens": 100, "is_batch": 1,
        "avg_cache_reads": 0.1,
    }
    result = analyze_cache([low_reuse], PRICES)
    assert result["tiers"]["small"]["cache_enabled"] is False
    assert result["ungated_daily"] > result["no_cache_daily"]
    assert math.isclose(result["gated_daily"], result["no_cache_daily"])
    assert math.isclose(
        request_cost_with_cache_policy(low_reuse, PRICES, result),
        pricing.request_cost(1000, 100, 0.2, 0.4, batch=True),
    )

    # Exactly one prefix write followed by two equivalent reads: explicitly
    # supplied reuse enables cache; the 25% write premium is charged and batched.
    high_reuse = dict(low_reuse, cached_input_tokens=400, avg_cache_reads=2)
    result = analyze_cache([high_reuse], PRICES)
    assert result["tiers"]["small"]["cache_enabled"] is True
    expected_premium = 200 / 1e6 * 0.2 * 0.25 * 0.5
    assert math.isclose(result["write_premium_daily"], expected_premium)
    expected = pricing.request_cost(1000, 100, 0.2, 0.4, cached_in=400, batch=True) + expected_premium
    assert math.isclose(result["gated_daily"], expected)

    # No repeated reads does not make an attempted initial cache write free.
    # The gate declines it; an ungated scenario must still charge its premium.
    zero_reads = dict(low_reuse, cached_input_tokens=0, avg_cache_reads=0)
    result = analyze_cache([zero_reads], PRICES)
    small = result["tiers"]["small"]
    assert small["write_equivalent_tokens"] == 700
    assert small["avg_reads"] == 0
    assert small["cache_enabled"] is False
    assert math.isclose(result["gated_daily"], result["no_cache_daily"])
    assert math.isclose(
        result["ungated_daily"] - result["no_cache_daily"],
        700 / 1e6 * 0.2 * 0.25 * 0.5,
    )

    # Scenario descriptions must reflect custom pricing, rather than claiming
    # that every call used the default write/read multipliers.
    custom = analyze_cache([high_reuse], PRICES, write_cost=1.5, read_discount=0.2)
    assert "Write multiplier 1.5 and read multiplier 0.2" in custom["assumptions"]
    assert math.isclose(custom["break_even_reads"], 0.5 / 0.8)
    assert custom["write_cost_multiplier"] == 1.5
    assert custom["read_discount"] == 0.2

    rows = load_csv("token_usage.csv")
    result = analyze_cache(rows, PRICES)
    assert result["read_basis"] == "estimated_token_equivalent_reuse"
    assert set(result["tiers"]) == set(PRICES)
    assert all(tier["cache_enabled"] for tier in result["tiers"].values())
    assert result["write_premium_daily"] > 0
    assert result["gated_daily"] < result["no_cache_daily"]
    total_rows = sum(request_cost_with_cache_policy(row, PRICES, result) for row in rows)
    assert math.isclose(total_rows, result["gated_daily"], abs_tol=1e-12)
    legacy_cached = sum(
        pricing.request_cost(
            int(row["input_tokens"]), int(row["output_tokens"]),
            *PRICES[row["route_tier"]], cached_in=int(row["cached_input_tokens"]),
            batch=bool(int(row["is_batch"])),
        ) for row in rows
    )
    assert math.isclose(result["gated_daily"], legacy_cached + result["write_premium_daily"])
    print("Cache extension checks passed: thresholds, invalid assumptions, gate, write premium, reconciliation.")


if __name__ == "__main__":
    check_cache()
