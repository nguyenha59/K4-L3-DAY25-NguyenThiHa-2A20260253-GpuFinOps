"""Your Turn #5: all-region energy/carbon comparison, listed days and 30 days.

Run: python missions/m6_carbon_scheduling.py
"""
from __future__ import annotations

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from finops.carbon_schedule import evaluate_schedule
from missions._common import catalog_by_type, load_csv


ASSUMPTIONS = [
    "Static illustrative lab region factors; no live grid, price or time-of-day signal.",
    "Catalog GPU nameplate watts estimate energy. PUE=1.0 excludes cooling and CPU/network/storage power.",
    "Spot checkpoint/rework energy multiplier = 1 + 0.03 + 0.05 * 0.5 = 1.055, as in M3.",
    "Regional baseline and alternatives both include the same spot overhead; only region changes.",
    "Listed-horizon totals sum each job's own days. The separate recurring 30-day scenario matches M3.",
    "GPU prices and capacity by region, egress, data sovereignty, checkpoint transfer and latency are unknown.",
    "Electricity savings are an energy-ledger estimate, not an extra discount on GPU cloud rent; do not add to M5 savings.",
    "Prefer training migration first; sandbox/eval are included separately and need deadline/latency review.",
]


def _print_scenario(scenario: dict) -> None:
    print(f"\nHorizon: {scenario['horizon']}; all {scenario['job_count']} interruptible jobs")
    print(f"{'job':19} {'days':>5} {'GPU-h':>9} {'energy kWh':>11} {'east gCO2':>11} {'clean gCO2':>11} {'saved gCO2':>11}")
    cleanest = scenario["objectives"]["cleanest"]
    for job in scenario["jobs"]:
        rows = {row["region"]: row for row in job["regions"]}
        baseline = rows[scenario["baseline_region"]]
        clean = rows[cleanest]
        print(f"{job['job_id']:19} {job['days']:5g} {job['gpu_hours']:9.0f} {job['energy_kwh']:11.3f} {baseline['carbon_g']:11.1f} {clean['carbon_g']:11.1f} {clean['carbon_savings_g']:11.1f}")
    print(f"\n{'region':18} {'USD/kWh':>8} {'gCO2/kWh':>9} {'electricity $':>14} {'carbon g':>12} {'saved $':>10} {'saved gCO2':>12} {'score':>8}")
    for row in scenario["regions"]:
        print(f"{row['region']:18} {row['price_usd_per_kwh']:8.3f} {row['carbon_g_per_kwh']:9.0f} {row['electricity_usd']:14.3f} {row['carbon_g']:12.1f} {row['electricity_savings_usd']:10.3f} {row['carbon_savings_g']:12.1f} {row['balanced_score']:8.4f}")
    totals = scenario["totals"]
    print(f"Energy: useful {totals['useful_energy_kwh']:.3f} + spot overhead {totals['spot_overhead_energy_kwh']:.3f} = {totals['energy_kwh']:.3f} kWh")
    for name, subset in scenario["subsets"].items():
        totals = subset["totals"]
        clean = totals["cleanest"]
        print(f"{name}: {subset['job_count']} jobs, {totals['energy_kwh']:.3f} kWh; cleanest saves ${clean['electricity_savings_usd']:.3f} and {clean['carbon_savings_g']:.1f} gCO2")


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    catalog = catalog_by_type()
    listed = evaluate_schedule(jobs, catalog)
    monthly = evaluate_schedule(jobs, catalog, horizon_days=30)
    result = {
        "baseline_region": listed["baseline_region"],
        "objectives": listed["objectives"],
        "spot_energy_multiplier": listed["spot_energy_multiplier"],
        "listed_horizon": listed,
        "normalized_30_days": monthly,
        "assumptions": list(ASSUMPTIONS),
    }
    if verbose:
        print("== Extension #5: Carbon-aware Scheduling ==")
        for criterion in ("cheapest", "cleanest", "balanced"):
            print(f"{criterion}: {result['objectives'][criterion]}")
        print("Balanced score: 0.5 * min-max normalized electricity price + 0.5 * min-max normalized grid carbon.")
        _print_scenario(listed)
        _print_scenario(monthly)
        print("\nAssumptions and deployment constraints:")
        for assumption in ASSUMPTIONS:
            print(f"- {assumption}")
        print("Latency: remote training is less latency-sensitive; online inference remains near users. Check eval deadlines before migration.")
    return result


if __name__ == "__main__":
    run()
