"""M4 — Cost Allocation: tag -> showback -> chargeback + FOCUS export (deck §10).

Run: python missions/m4_allocation.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import csv
import os
from missions._common import load_csv, ROOT
from finops import allocation
from missions.m2_inference_levers import MODEL_PRICES
from finops import cache_economics

TAGS = ["team", "project"]


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    cache_analysis = cache_economics.analyze_cache(rows, MODEL_PRICES)
    priced = []
    for index, r in enumerate(rows):
        cost = cache_economics.request_cost_with_cache_policy(r, MODEL_PRICES, cache_analysis)
        priced.append({"team": r["team"], "project": r["project"],
                       "service": "gpu-inference", "cost": cost,
                       "resource_id": f"request-{index:04d}"})

    by_team = allocation.cost_by_tag(priced, "team")
    by_project = allocation.cost_by_tag(priced, "project")
    coverage = allocation.tag_coverage(priced, TAGS)
    ready = allocation.chargeback_ready(coverage)

    # Export the entire priced day, so the bill can be reconciled with M2.
    focus = allocation.to_focus_rows(priced)
    out_path = os.path.join(ROOT, "outputs", "focus_export.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["BillingAccountId", "ChargePeriodStart", "ServiceCategory",
                    "ServiceName", "ResourceId", "BilledCost", "BillingCurrency", "team", "project"])
        for fr, source in zip(focus, priced):
            w.writerow([fr["BillingAccountId"], fr["ChargePeriodStart"], fr["ServiceCategory"],
                        fr["ServiceName"], fr["ResourceId"], f"{source['cost']:.12f}", fr["BillingCurrency"],
                        fr["Tags"]["team"], fr["Tags"]["project"]])

    if verbose:
        print("== M4 Cost Allocation ==")
        print("cost by team ($/day):")
        for k, v in sorted(by_team.items(), key=lambda x: -x[1]):
            print(f"  {k:12} ${v:8.2f}")
        print(f"tag coverage: {coverage:.0%}  ->  chargeback ready? {ready}")
        print(f"FOCUS export -> outputs/focus_export.csv ({len(focus)} rows)")

    return {"by_team": {k: round(v, 2) for k, v in by_team.items()},
            "by_project": {k: round(v, 2) for k, v in by_project.items()},
            "tag_coverage": round(coverage, 3), "chargeback_ready": ready,
            "request_count": len(rows), "tagged_count": sum(all(r[k] for k in TAGS) for r in rows),
            "total_daily": sum(r["cost"] for r in priced),
            "by_team_exact": by_team, "by_project_exact": by_project,
            "focus_rows": len(focus)}


if __name__ == "__main__":
    run()
