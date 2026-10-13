"""Independent boundary and hand-calculated checks for the carbon extension.

Run: python validation/check_carbon.py
The original instructor tests in tests/ remain untouched.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finops.carbon_schedule import evaluate_schedule, region_objectives
from missions._common import catalog_by_type, load_csv
from missions.m6_carbon_scheduling import run


def check() -> None:
    result = run(verbose=False)
    listed = result["listed_horizon"]
    monthly = result["normalized_30_days"]
    assert listed["job_count"] == 5
    assert listed["subsets"]["training"]["job_count"] == 3
    assert listed["subsets"]["other_interruptible"]["job_count"] == 2
    # Hand calculation from workload rows, using each actual listed duration.
    expected_useful = 0.7 * 8 * 20 * 14 + 0.4 * 4 * 10 * 5 + 0.7 * 2 * 6 * 3 + 0.15 * 2 * 8 * 22 + 0.7 * 1 * 3 * 30
    assert math.isclose(listed["totals"]["useful_energy_kwh"], expected_useful)
    assert math.isclose(listed["totals"]["energy_kwh"], expected_useful * 1.055)
    assert math.isclose(listed["totals"]["cleanest"]["carbon_savings_g"], expected_useful * 1.055 * (380 - 30))
    expected_monthly = (0.7 * 8 * 20 + 0.4 * 4 * 10 + 0.7 * 2 * 6 + 0.15 * 2 * 8 + 0.7 * 1 * 3) * 30
    assert math.isclose(monthly["totals"]["energy_kwh"], expected_monthly * 1.055)
    assert result["objectives"]["cheapest"] == "us-east-wa"
    assert result["objectives"]["cleanest"] == "europe-north1"
    assert result["objectives"]["balanced"] == "us-east-wa"
    assert region_objectives(cost_weight=0, carbon_weight=1)["balanced"] == "europe-north1"
    assert region_objectives(cost_weight=1, carbon_weight=0)["balanced"] == "us-east-wa"
    # A per-job conservation check: all five regions receive the same compute.
    for job in listed["jobs"]:
        assert len(job["regions"]) == 5
        for row in job["regions"]:
            assert math.isclose(row["electricity_usd"], job["energy_kwh"] * row["price_usd_per_kwh"])
            assert math.isclose(row["carbon_g"], job["energy_kwh"] * row["carbon_g_per_kwh"])
    empty = evaluate_schedule([], catalog_by_type())
    assert empty["totals"]["energy_kwh"] == 0
    no_spot = evaluate_schedule(load_csv("workloads.csv"), catalog_by_type(), use_spot=False)
    assert math.isclose(no_spot["totals"]["energy_kwh"], expected_useful)
    assert no_spot["spot_energy_multiplier"] == 1
    for kwargs in ({"pue": 0.5}, {"horizon_days": -1}, {"baseline_region": "unknown"}, {"cost_weight": 0, "carbon_weight": 0}):
        try:
            evaluate_schedule([], catalog_by_type(), **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid input was accepted: {kwargs}")
    print("Carbon extension checks passed: coverage, horizons, overhead, region objectives, accounting and boundaries.")


if __name__ == "__main__":
    check()
