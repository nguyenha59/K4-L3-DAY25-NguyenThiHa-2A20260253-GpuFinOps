"""Deterministic regional energy/carbon scenarios for interruptible workloads.

This is an illustrative energy ledger, not a cloud-price or live-grid optimizer.
GPU catalog watts are nameplate power; default PUE=1 excludes facility overhead.
The default spot overhead matches M3: 3% checkpoint + 5%/h * 0.5h rework.
"""
from __future__ import annotations

from math import isfinite

from finops.sustainability import REGION_CARBON, REGION_PRICE_KWH


def _nonnegative(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return value


def region_objectives(cost_weight: float = 0.5, carbon_weight: float = 0.5) -> dict:
    """Minimize price, intensity, or weighted min-max-normalized price/intensity.

    Equal weights mean the two quantities get equal normalized importance; they
    do not mean a gram of carbon equals a dollar. Region names break ties.
    """
    cost_weight = _nonnegative(cost_weight, "cost_weight")
    carbon_weight = _nonnegative(carbon_weight, "carbon_weight")
    if cost_weight + carbon_weight == 0:
        raise ValueError("At least one objective weight must be positive")
    regions = sorted(set(REGION_CARBON) & set(REGION_PRICE_KWH))
    if not regions:
        raise ValueError("No region has both price and carbon inputs")
    price_min = min(REGION_PRICE_KWH[r] for r in regions)
    price_range = max(REGION_PRICE_KWH[r] for r in regions) - price_min
    carbon_min = min(REGION_CARBON[r] for r in regions)
    carbon_range = max(REGION_CARBON[r] for r in regions) - carbon_min
    scores = {}
    for region in regions:
        price_score = (REGION_PRICE_KWH[region] - price_min) / price_range if price_range else 0.0
        carbon_score = (REGION_CARBON[region] - carbon_min) / carbon_range if carbon_range else 0.0
        scores[region] = (cost_weight * price_score + carbon_weight * carbon_score) / (cost_weight + carbon_weight)
    return {
        "cheapest": min(regions, key=lambda r: (REGION_PRICE_KWH[r], r)),
        "cleanest": min(regions, key=lambda r: (REGION_CARBON[r], r)),
        "balanced": min(regions, key=lambda r: (scores[r], r)),
        "cost_weight": cost_weight / (cost_weight + carbon_weight),
        "carbon_weight": carbon_weight / (cost_weight + carbon_weight),
        "scores": scores,
        "formula": "cost_weight * (price-min_price)/(max_price-min_price) + carbon_weight * (carbon-min_carbon)/(max_carbon-min_carbon)",
    }


def _regional_results(energy_kwh: float, baseline_region: str, objectives: dict) -> list[dict]:
    baseline_cost = energy_kwh * REGION_PRICE_KWH[baseline_region]
    baseline_carbon = energy_kwh * REGION_CARBON[baseline_region]
    return [{
        "region": region,
        "price_usd_per_kwh": REGION_PRICE_KWH[region],
        "carbon_g_per_kwh": REGION_CARBON[region],
        "energy_kwh": energy_kwh,
        "electricity_usd": energy_kwh * REGION_PRICE_KWH[region],
        "carbon_g": energy_kwh * REGION_CARBON[region],
        "electricity_savings_usd": baseline_cost - energy_kwh * REGION_PRICE_KWH[region],
        "carbon_savings_g": baseline_carbon - energy_kwh * REGION_CARBON[region],
        "balanced_score": objectives["scores"][region],
    } for region in REGION_PRICE_KWH if region in REGION_CARBON]


def _summary(jobs: list[dict], baseline_region: str, objectives: dict) -> dict:
    useful_energy = sum(job["useful_energy_kwh"] for job in jobs)
    energy = sum(job["energy_kwh"] for job in jobs)
    regions = _regional_results(energy, baseline_region, objectives)
    by_region = {row["region"]: row for row in regions}
    return {
        "job_ids": [job["job_id"] for job in jobs],
        "job_count": len(jobs),
        "regions": regions,
        "totals": {
            "useful_energy_kwh": useful_energy,
            "spot_overhead_energy_kwh": energy - useful_energy,
            "energy_kwh": energy,
            "baseline_electricity_usd": by_region[baseline_region]["electricity_usd"],
            "baseline_carbon_g": by_region[baseline_region]["carbon_g"],
            **{criterion: dict(by_region[objectives[criterion]]) for criterion in ("cheapest", "cleanest", "balanced")},
        },
    }


def evaluate_schedule(
    workloads: list[dict],
    catalog: dict,
    horizon_days: float | None = None,
    baseline_region: str = "us-east-1",
    use_spot: bool = True,
    pue: float = 1.0,
    interrupt_rate: float = 0.05,
    checkpoint_overhead_frac: float = 0.03,
    rework_hours_per_interrupt: float = 0.5,
    cost_weight: float = 0.5,
    carbon_weight: float = 0.5,
) -> dict:
    """Compare all five regions for every interruptible job at a fixed horizon.

    The baseline and alternatives use the SAME energy and spot overhead, so
    savings isolate region selection. The listed days are job-specific rather
    than a monthly total; pass horizon_days=30 for M3's recurring-month scenario.
    """
    if baseline_region not in REGION_CARBON or baseline_region not in REGION_PRICE_KWH:
        raise ValueError(f"Unknown baseline region: {baseline_region}")
    pue = _nonnegative(pue, "pue")
    if pue < 1.0:
        raise ValueError("pue must be at least 1")
    if horizon_days is not None:
        horizon_days = _nonnegative(horizon_days, "horizon_days")
    interrupt_rate = _nonnegative(interrupt_rate, "interrupt_rate")
    checkpoint_overhead_frac = _nonnegative(checkpoint_overhead_frac, "checkpoint_overhead_frac")
    rework_hours_per_interrupt = _nonnegative(rework_hours_per_interrupt, "rework_hours_per_interrupt")
    multiplier = 1.0 + checkpoint_overhead_frac + interrupt_rate * rework_hours_per_interrupt if use_spot else 1.0
    objectives = region_objectives(cost_weight, carbon_weight)
    jobs = []
    for workload in workloads:
        if not int(workload["interruptible"]):
            continue
        days = _nonnegative(workload["days"] if horizon_days is None else horizon_days, "days")
        hours_per_day = _nonnegative(workload["hours_per_day"], "hours_per_day")
        num_gpus = _nonnegative(workload["num_gpus"], "num_gpus")
        watts = _nonnegative(catalog[workload["gpu_type"]]["watts"], "watts")
        gpu_hours = hours_per_day * days * num_gpus
        useful_energy = watts / 1000.0 * gpu_hours * pue
        energy = useful_energy * multiplier
        jobs.append({
            "job_id": workload["job_id"], "kind": workload["kind"],
            "team": workload["team"], "gpu_type": workload["gpu_type"],
            "days": days, "hours_per_day": hours_per_day, "num_gpus": num_gpus,
            "gpu_watts": watts, "gpu_hours": gpu_hours,
            "useful_energy_kwh": useful_energy,
            "spot_overhead_energy_kwh": energy - useful_energy,
            "energy_kwh": energy,
            "regions": _regional_results(energy, baseline_region, objectives),
        })
    summary = _summary(jobs, baseline_region, objectives)
    summary.update({
        "horizon": "listed job durations" if horizon_days is None else f"{horizon_days:g}-day recurring scenario",
        "horizon_days": horizon_days,
        "baseline_region": baseline_region,
        "spot_energy_multiplier": multiplier,
        "pue": pue,
        "objectives": objectives,
        "jobs": jobs,
        "subsets": {
            "training": _summary([job for job in jobs if job["kind"] == "train"], baseline_region, objectives),
            "other_interruptible": _summary([job for job in jobs if job["kind"] != "train"], baseline_region, objectives),
        },
    })
    return summary
