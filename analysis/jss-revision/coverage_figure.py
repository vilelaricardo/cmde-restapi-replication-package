"""Figure fig:cobertura: coverage of RPVC, SCCC, SCC and RBPC per technique (main campaign, 2026).

One panel per criterion, techniques on the x axis, boxplot plus every execution as a point.
Technique identity is carried by the axis labels, so the marks use neutral ink (prints in grey).
Usage: python coverage_figure.py [data/runs_main.csv] [output/fig-coverage-2026.pdf]
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RUNS = sys.argv[1] if len(sys.argv) > 1 else str(HERE / 'data' / 'runs_main.csv')
OUT = sys.argv[2] if len(sys.argv) > 2 else str(HERE / 'output' / 'fig-coverage-2026.pdf')
TECHS = ['MIO', 'RANDOM', 'SMARTS', 'WTS']
CRITERIA = [('RPVC', 'Request Parameter Value'), ('SCCC', 'Status Code Class'),
            ('SCC', 'Status Code'), ('RBPC', 'Response Body Properties')]
INK, MUTED, FILL, GRID = '#222222', '#6b6b6b', '#e4e4e4', '#d9d9d9'

df = pd.read_csv(RUNS)
rng = np.random.default_rng(20261108)
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK,
                     'xtick.color': INK, 'ytick.color': MUTED, 'font.family': 'serif'})
fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.6), constrained_layout=True)
for ax, (col, name) in zip(axes, CRITERIA):
    data = [df[df.algorithm == t][col].values for t in TECHS]
    ax.boxplot(data, widths=0.55, patch_artist=True, showfliers=False,
               boxprops=dict(facecolor=FILL, edgecolor=MUTED, linewidth=0.8),
               medianprops=dict(color=INK, linewidth=1.6),
               whiskerprops=dict(color=MUTED, linewidth=0.8), capprops=dict(color=MUTED, linewidth=0.8))
    for i, v in enumerate(data, start=1):
        ax.scatter(i + rng.uniform(-0.16, 0.16, len(v)), v, s=9, color=INK, alpha=0.55, linewidths=0, zorder=3)
    lo, hi = min(map(min, data)), max(map(max, data))
    pad = max(0.6, (hi - lo) * 0.08)
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_title(col, fontsize=9, color=INK)
    ax.set_xticks(range(1, 5), TECHS, rotation=45, ha='right', fontsize=7.5)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
axes[0].set_ylabel('Coverage (%)')
fig.savefig(OUT)
fig.savefig(OUT.replace('.pdf', '.png'), dpi=150)
print('ok', Path(OUT).name)
