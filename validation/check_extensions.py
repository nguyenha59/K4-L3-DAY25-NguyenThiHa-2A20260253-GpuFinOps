"""Run extension checks and reconcile every generated submission artifact.

Run: python validation/check_extensions.py
The instructor-owned tests/ and verify.py are not modified.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_cache import check_cache
from check_carbon import check as check_carbon
from check_reasoning import check as check_reasoning
from missions import m2_inference_levers, m4_allocation, m5_report


def check_artifacts() -> None:
    result = m5_report.run(verbose=False)
    out = ROOT / "outputs"
    evidence = json.loads((out / "mission_results.json").read_text(encoding="utf-8"))
    m2, m4 = m2_inference_levers.run(False), m4_allocation.run(False)
    assert evidence["m5"] == result
    assert evidence["m2"] == m2
    assert evidence["m4"] == m4
    assert math.isclose(m2["optimized_daily_exact"], m4["total_daily"], abs_tol=1e-12)
    with (out / "focus_export.csv").open(newline="", encoding="utf-8") as stream:
        focus = list(csv.DictReader(stream))
    assert len(focus) == m2["request_count"] == m4["focus_rows"]
    assert len({row["ResourceId"] for row in focus}) == len(focus)
    assert all(row["BillingCurrency"] == "USD" for row in focus)
    assert math.isclose(sum(float(row["BilledCost"]) for row in focus), m2["optimized_daily_exact"], abs_tol=1e-9)
    for team, amount in m4["by_team_exact"].items():
        assert math.isclose(sum(float(row["BilledCost"]) for row in focus if row["team"] == team), amount, abs_tol=1e-9)
    assert sum(all(row[key] for key in ("team", "project")) for row in focus) == m4["tagged_count"]
    assert sum(result["levers"].values()) == result["baseline_monthly"] - result["optimized_monthly"]
    assert math.isclose(
        sum(stage["incremental_savings_daily"] for stage in m2["stages"]),
        m2["baseline_daily_exact"] - m2["optimized_daily_exact"],
    )
    reasoning = m2["reasoning"]
    assert math.isclose(reasoning["totals"]["cost_usd"], m2["optimized_daily_exact"])
    assert reasoning["scenarios"]["cap_10_pct"]["rerouted_requests"] == 0
    assert reasoning["scenarios"]["cap_10_pct"]["energy_savings_wh"] == 0
    cap5 = reasoning["scenarios"]["cap_5_pct"]
    assert cap5["totals"]["total_tokens"] < m2["total_tokens"]
    assert math.isclose(cap5["totals"]["cost_usd"] + cap5["cost_savings_usd"], m2["optimized_daily_exact"])
    md = (out / "report.md").read_text(encoding="utf-8")
    writeup = (out / "writeup.md").read_text(encoding="utf-8")
    for amount in (result["baseline_monthly"], result["optimized_monthly"]):
        assert f"${amount:,.0f}" in md and f"${amount:,.0f}" in writeup
    for amount in (m2["baseline_per_m"], m2["optimized_per_m"]):
        assert f"${amount:.3f}" in md and f"${amount:.3f}" in writeup
    for text in (md, writeup):
        assert "\ufffd" not in text
        assert "#3" in text and "#4" in text and "#5" in text
    png = (out / "savings.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(png[16:20], "big") >= 1000
    assert int.from_bytes(png[20:24], "big") >= 600
    # A rerun must preserve the narrative, exact costs and figure, addressing
    # the lab's overwrite warning without relying on handwritten outputs.
    names = ("report.md", "writeup.md", "focus_export.csv", "mission_results.json", "savings.png")
    signatures = {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in names}
    m5_report.run(verbose=False)
    assert signatures == {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in names}
    print(f"Artifact checks passed: {len(focus)} FOCUS rows, M2/M4/JSON reconciliation, report/writeup, PNG, deterministic regeneration.")


if __name__ == "__main__":
    check_cache()
    check_reasoning()
    print("Reasoning extension checks passed: grouping, counterfactuals, cap boundaries, changed token denominator.")
    check_carbon()
    check_artifacts()
    print("All extension and submission checks passed.")
