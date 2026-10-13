"""M5 — Optimization Report: combine M1-M4 into baseline-vs-optimized (deck §1/§11).

Run: python missions/m5_report.py   ->  outputs/report.md + outputs/savings.png
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
import json
from missions._common import num, catalog_by_type, ROOT
from finops import report, sustainability
from finops.narrative import build_writeup
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing, m4_allocation, m6_carbon_scheduling

DAYS = 30
# one tier down for over-provisioned ("util-lie") GPUs
RIGHTSIZE_MAP = {"H100": "A100", "H200": "H100", "A100": "A10G", "A10G": "L4", "L4": "L4"}


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    r4 = m4_allocation.run(verbose=False)
    carbon = m6_carbon_scheduling.run(verbose=False)
    cat = catalog_by_type()

    # --- buckets ---
    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]

    idle_savings = r1["idle_waste_daily"] * DAYS
    rightsize_savings = 0.0
    rightsize = []
    for lie in r1["lies"]:
        cur = lie["gpu_type"]
        tgt = RIGHTSIZE_MAP.get(cur, cur)
        delta = num(cat[cur]["on_demand_hr"]) - num(cat[tgt]["on_demand_hr"])
        rightsize_savings += max(0.0, delta) * 24 * DAYS
        rightsize.append({"gpu_id": lie["gpu_id"], "current": cur, "target": tgt,
                          "hourly_delta": max(0.0, delta),
                          "monthly_savings": max(0.0, delta) * 24 * DAYS})

    levers = {
        "Inference (cascade/cache/batch)": round(infer_savings),
        "Purchasing (spot/reserved)": round(purchasing_savings),
        "Right-size util-lies": round(rightsize_savings),
        "Kill idle GPUs": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    # --- sustainability snapshot ---
    illustrative_tokens = 800
    wh = sustainability.wh_per_query(illustrative_tokens)
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "best_region": min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get),
        "cheapest_region": min(sustainability.REGION_PRICE_KWH, key=sustainability.REGION_PRICE_KWH.get),
        "energy_cost_usd": sustainability.energy_cost_usd(wh, "us-east-1"),
    }

    evidence = {"m1": r1, "m2": r2, "m3": r3, "m4": r4,
                "carbon": carbon, "rightsize": rightsize}
    result = {"baseline_monthly": round(baseline), "optimized_monthly": round(optimized),
              "levers": levers, "total_savings_pct": round(total_pct, 1)}
    md = report.build_report(baseline, optimized, levers, sustainability=sust,
                             period="30-day recurring lab scenario", evidence=evidence)
    out_md = os.path.join(ROOT, "outputs", "report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8", newline="\n") as f:
        f.write(md + "\n")
    with open(os.path.join(ROOT, "outputs", "writeup.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(build_writeup(evidence, baseline, optimized, levers))
    with open(os.path.join(ROOT, "outputs", "mission_results.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({**evidence, "m5": result, "sustainability": sust}, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    png = report.savings_waterfall(levers, os.path.join(ROOT, "outputs", "savings.png"), baseline_usd=baseline)

    if verbose:
        print("== M5 Optimization Report ==")
        print(md)
        print("\nWritten: outputs/report.md + outputs/writeup.md + outputs/mission_results.json + outputs/focus_export.csv"
              + (" + outputs/savings.png" if png else " (matplotlib absent: PNG skipped)"))

    return result


if __name__ == "__main__":
    run()
