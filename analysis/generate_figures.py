"""Regenerates every result figure used in the paper, directly from the raw data
in this replication package. Nothing here re-runs EvoMaster; it only re-derives
figures from data already present in ../results/.

Data sources:
  - results/statistics/experiment-date-03-05-25-time-21-29-51-725.csv
      (canonical dataset, used for all boxplot figures and the correlation heatmap)
  - results/statistics/minimization_analysis.csv
      (produced by ../tool/analyze_minimization.py, used for the minimization figure)

Usage: run from replication-package/analysis/:
    pip install -r requirements.txt
    python generate_figures.py

Output is written to ./output/ (not to the paper's figuras/ directory, to keep
this package self-contained and side-effect-free on the paper source). Diff the
files in ./output/ against ../../figuras/ to confirm they match.
"""
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import scikit_posthocs as sp
from scipy import stats

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, MaxNLocator  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_CSV = ROOT / "results" / "statistics" / "experiment-date-03-05-25-time-21-29-51-725.csv"
MINIMIZATION_CSV = ROOT / "results" / "statistics" / "minimization_analysis.csv"
OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)

TECHS = ["RANDOM", "SMARTS", "WTS"]
# Categorical palette validated for CVD-safety (see the `dataviz` design method used
# throughout the paper's figures): blue / green / magenta, in this fixed order.
COLORS = {"RANDOM": "#2a78d6", "SMARTS": "#008300", "WTS": "#e87ba4"}

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#ffffff"

CRIT_COLS = {
    "PC": "input_path_coverage",
    "OC": "input_operation_coverage",
    "RPC": "input_parameter_coverage",
    "RPVC": "input_parameter_value_coverage",
    "SCC": "output_status_code_coverage",
    "SCCC": "output_status_code_class_coverage",
    "RBPC": "output_response_body_properties_coverage",
}

rng = np.random.default_rng(42)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.titleweight": "medium",
    "axes.titlesize": 11.5,
    "axes.titlecolor": INK_PRIMARY,
    "axes.labelsize": 10.5,
    "axes.labelcolor": INK_SECONDARY,
    "xtick.labelsize": 10,
    "ytick.labelsize": 9.5,
    "xtick.color": INK_SECONDARY,
    "ytick.color": INK_MUTED,
    "text.color": INK_PRIMARY,
    "axes.edgecolor": BASELINE,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})

df = pd.read_csv(CANONICAL_CSV)
df["aggregate"] = df[list(CRIT_COLS.values())].mean(axis=1)


def stars(p):
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def dunn_pvals(data, col):
    return sp.posthoc_dunn(data, val_col=col, group_col="algorithm", p_adjust="bonferroni")


def brackets_for(col):
    dunn = dunn_pvals(df, col)
    return [
        ((0, 1), dunn.loc["RANDOM", "SMARTS"]),
        ((1, 2), dunn.loc["SMARTS", "WTS"]),
        ((0, 2), dunn.loc["RANDOM", "WTS"]),
    ]


def add_brackets(ax, pairs_pvals, base, step, x_positions):
    for k, ((i, j), p) in enumerate(pairs_pvals):
        y = base + step * (k + 1)
        x1, x2 = x_positions[i], x_positions[j]
        ax.plot([x1, x1, x2, x2], [y, y + step * 0.22, y + step * 0.22, y],
                lw=0.9, c=INK_SECONDARY, solid_capstyle="round", zorder=5)
        ax.text((x1 + x2) / 2, y + step * 0.28, stars(p), ha="center", va="bottom",
                fontsize=9.5, color=INK_PRIMARY, zorder=5)


def box_with_points(ax, col, brackets=None, ylabel="Coverage (%)"):
    """Zooms the y-axis to the data's own range (with padding), rather than
    forcing a fixed 0-100 scale -- appropriate here because position (not bar
    area) encodes the value, unlike a bar chart."""
    x = np.arange(len(TECHS))
    data = [df[df.algorithm == t][col].values for t in TECHS]

    bp = ax.boxplot(
        data, positions=x, widths=0.30, patch_artist=True, showfliers=False,
        whiskerprops=dict(color=INK_SECONDARY, linewidth=1.0),
        capprops=dict(color=INK_SECONDARY, linewidth=1.0),
        medianprops=dict(color=INK_PRIMARY, linewidth=1.8),
        boxprops=dict(linewidth=1.1),
        zorder=4,
    )
    for i, t in enumerate(TECHS):
        rgb = matplotlib.colors.to_rgb(COLORS[t])
        bp["boxes"][i].set_alpha(None)
        bp["boxes"][i].set_facecolor((*rgb, 0.16))
        bp["boxes"][i].set_edgecolor((*rgb, 1.0))

    for i, (t, vals) in enumerate(zip(TECHS, data)):
        jitter = rng.uniform(-0.11, 0.11, size=len(vals))
        ax.scatter(np.full(len(vals), x[i]) + jitter, vals, s=17,
                   color=COLORS[t], alpha=0.75, linewidths=0, zorder=6)

    ax.set_xticks(x)
    ax.set_xticklabels(TECHS, rotation=0, ha="center", color=INK_SECONDARY)
    ax.set_ylabel(ylabel)

    all_vals = np.concatenate(data)
    data_min, data_max = all_vals.min(), all_vals.max()
    span = max(data_max - data_min, 1e-6)
    pad = span * 0.35
    y_bottom = data_min - pad

    if brackets:
        n = len(brackets)
        headroom = span * 1.0
        base = data_max + headroom * 0.12
        bracket_step = (headroom * 0.85) / n
        y_top = base + bracket_step * (n + 0.55)
    else:
        y_top = data_max + pad

    ax.set_ylim(y_bottom, y_top)
    locator = MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10])
    ticks = locator.tick_values(y_bottom, y_top)
    if "%" in ylabel:
        # coverage is a percentage: the axis area may extend past 100 to fit
        # bracket headroom, but no tick label should ever claim > 100%
        ticks = ticks[ticks <= 100]
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_color(BASELINE)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)

    if brackets:
        add_brackets(ax, brackets, base, bracket_step, x)


def fig_num_tests():
    fig, ax = plt.subplots(figsize=(4.8, 5.0))
    box_with_points(ax, "num_tests", brackets=brackets_for("num_tests"),
                    ylabel="Number of Generated Tests")
    fig.tight_layout()
    fig.savefig(OUT / "custo.pdf", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def fig_aggregate():
    # Purely descriptive: no significance brackets. The aggregate score is
    # not a validated metric and is not used for any hypothesis-test
    # decision in the paper (see the Global Coverage Analysis subsection).
    fig, ax = plt.subplots(figsize=(4.8, 5.0))
    box_with_points(ax, "aggregate", brackets=None)
    fig.tight_layout()
    fig.savefig(OUT / "fig-todos-os-criterios.pdf", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def fig_input_criteria():
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 5.0))
    titles = {
        "RPC": "RPC — Request Parameter Coverage",
        "RPVC": "RPVC — Request Parameter Value Coverage",
    }
    for ax, crit in zip(axes.flat, ["RPC", "RPVC"]):
        col = CRIT_COLS[crit]
        box_with_points(ax, col, brackets=brackets_for(col))
        ax.set_title(titles[crit], fontsize=11, pad=14)
    fig.tight_layout(w_pad=3)
    fig.savefig(OUT / "fig-criterios-entrada.pdf", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def fig_output_criteria():
    fig = plt.figure(figsize=(9.0, 8.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.15], hspace=0.45, wspace=0.32)
    ax_scc = fig.add_subplot(gs[0, 0])
    ax_sccc = fig.add_subplot(gs[0, 1])
    ax_rbpc = fig.add_subplot(gs[1, :])

    box_with_points(ax_scc, CRIT_COLS["SCC"])
    ax_scc.set_title("SCC — Status Code Coverage", fontsize=11, pad=14)

    box_with_points(ax_sccc, CRIT_COLS["SCCC"])
    ax_sccc.set_title("SCCC — Status Code Class Coverage", fontsize=11, pad=14)

    box_with_points(ax_rbpc, CRIT_COLS["RBPC"], brackets=brackets_for(CRIT_COLS["RBPC"]))
    ax_rbpc.set_title("RBPC — Response Body Properties Coverage",
                      fontsize=11, pad=14)

    fig.savefig(OUT / "fig-criterio-saida.pdf", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


def fig_correlation_heatmap():
    labels = ["NT", "RPC", "RPVC", "SCC", "SCCC", "RBPC"]
    cols = ["num_tests", CRIT_COLS["RPC"], CRIT_COLS["RPVC"], CRIT_COLS["SCC"], CRIT_COLS["SCCC"], CRIT_COLS["RBPC"]]
    corr = df[cols].corr(method="spearman")

    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_yticklabels(labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            v = corr.values[i, j]
            color = "white" if abs(v) > 0.55 else INK_PRIMARY
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", color=color, fontsize=10.5)
    ax.set_title("Spearman Correlation between NT and Coverage Criteria", fontsize=12, pad=12)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Spearman correlation (ρ)")
    fig.tight_layout()
    fig.savefig(OUT / "fig_correlacao_siglas.pdf", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def fig_minimization():
    mdf = pd.read_csv(MINIMIZATION_CSV)

    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    for t in TECHS:
        sub = mdf[mdf.algorithm == t]
        ax.scatter(sub["candidates_gt1"], sub["minim_seconds"] / 60,
                   s=42, color=COLORS[t], alpha=0.85, edgecolors="none", label=t, zorder=4)

    x = mdf["candidates_gt1"].values
    y = (mdf["minim_seconds"] / 60).values
    coef = np.polyfit(x, y, 1)
    xs = np.linspace(x.min() - 2, x.max() + 2, 100)
    ax.plot(xs, np.polyval(coef, xs), color=INK_MUTED, linewidth=1.2, linestyle="--",
            zorder=2, label="Pooled linear fit (visual aid only)")

    rho, p = stats.spearmanr(mdf["candidates_gt1"], mdf["minim_seconds"])
    p_str = "< 0.0001" if p < 0.0001 else f"= {p:.4f}"
    ax.text(0.03, 0.97, f"Spearman $\\rho$ = {rho:.2f} ($p$ {p_str})",
            transform=ax.transAxes, ha="left", va="top", fontsize=10.5, color=INK_PRIMARY)

    ax.set_xlabel("Candidate tests for minimization (size > 1)")
    ax.set_ylabel("Minimization phase duration (minutes)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)
    ax.legend(frameon=False, loc="lower right", fontsize=10)

    fig.tight_layout()
    fig.savefig(OUT / "fig-minimization.pdf", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def main():
    fig_num_tests()
    fig_aggregate()
    fig_input_criteria()
    fig_output_criteria()
    fig_correlation_heatmap()
    fig_minimization()
    print(f"Wrote 6 figures to {OUT}")


if __name__ == "__main__":
    main()
