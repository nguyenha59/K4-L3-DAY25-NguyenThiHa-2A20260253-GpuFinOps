"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly",
                 evidence: dict | None = None) -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}",
        "",
        f"**Baseline spend:** ${baseline_usd:,.0f}",
        "",
        f"**Optimized spend:** ${optimized_usd:,.0f}",
        "",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cleanest region: {sustainability.get('best_region', 'n/a')}",
            f"- Cheapest electricity region: {sustainability.get('cheapest_region', 'n/a')}",
            f"- Electricity per query (us-east-1): ${sustainability.get('energy_cost_usd', 0):.8f}",
        ]
    if evidence:
        from finops.narrative import technical_analysis
        lines += ["", technical_analysis(evidence, baseline_usd, optimized_usd, levers)]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str, baseline_usd: float | None = None) -> str:
    """Write a waterfall with four saving steps and reconciled endpoints."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    fig, ax = plt.subplots(figsize=(11, 5.8))
    if baseline_usd is None:
        bars = ax.bar(range(len(names)), vals, color="#247a62")
        labels = [name.replace(" (", "\n(") for name in names]
        for bar, value in zip(bars, vals):
            ax.annotate(f"${value:,.0f}", (bar.get_x() + bar.get_width()/2, value),
                        xytext=(0, 7), textcoords="offset points", ha="center")
        positions = list(range(len(names)))
    else:
        current = baseline_usd
        heights, bottoms = [current], [0]
        for value in vals:
            current -= value
            heights.append(value)
            bottoms.append(current)
        heights.append(current)
        bottoms.append(0)
        positions = list(range(len(heights)))
        colors = ["#2e548a"] + ["#247a62"] * len(vals) + ["#8055a6"]
        ax.bar(positions, heights, bottom=bottoms, color=colors, width=0.66)
        annotations = [f"${baseline_usd:,.0f}"] + [f"-${v:,.0f}" for v in vals] + [f"${current:,.0f}"]
        for x, height, bottom, label in zip(positions, heights, bottoms, annotations):
            ax.annotate(label, (x, height + bottom), xytext=(0, 8),
                        textcoords="offset points", ha="center", fontweight="bold")
        level = baseline_usd
        for index, value in enumerate(vals):
            ax.plot([index+.33, index+1-.33], [level, level], color="#8c99a6", linestyle="--")
            level -= value
        ax.plot([len(vals)+.33, len(vals)+1-.33], [level, level], color="#8c99a6", linestyle="--")
        labels = ["Baseline"] + [name.replace(" (", "\n(").replace("util-lies", "\nutil-lies") for name in names] + ["Optimized"]
        ax.set_ylim(0, baseline_usd * 1.16)
    ax.set_xticks(positions, labels, fontsize=9)
    ax.set_ylabel("Monthly spend / savings (USD)")
    ax.set_title("NimbusAI: baseline to optimized spend (30-day lab scenario)", pad=18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, alpha=0.16)
    ax.set_axisbelow(True)
    plt.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path
