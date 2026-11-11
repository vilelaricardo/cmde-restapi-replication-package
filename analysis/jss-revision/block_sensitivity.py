"""Sensitivity to the block design: Friedman + pairwise Wilcoxon signed-rank (Bonferroni, 6 pairs),
as an alternative to the Kruskal-Wallis + Dunn of main_campaign.py and low_budget.py.
Usage: python block_sensitivity.py [runs_main.csv | runs_low_budget.csv]   (file in data/)
"""
import sys
from itertools import combinations
from pathlib import Path

import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
TECHS = ['MIO', 'RANDOM', 'SMARTS', 'WTS']
df = pd.read_csv(HERE / 'data' / (sys.argv[1] if len(sys.argv) > 1 else 'runs_main.csv'))
for col in ['NT', 'requests_api', 'RPC', 'RPVC', 'SCCC', 'SCC', 'RBPC']:
    w = df.pivot(index='block', columns='algorithm', values=col)[TECHS]
    chi, p = stats.friedmanchisquare(*[w[t] for t in TECHS])
    kendall_w = chi / (len(w) * (len(TECHS) - 1))
    print(f'[{col}] Friedman chi2={chi:.2f} p={p:.2g} W={kendall_w:.2f}')
    for a, b in combinations(TECHS, 2):
        d = w[a] - w[b]
        if (d == 0).all():
            print(f'    {a:6s} x {b:6s}  all differences = 0')
            continue
        pw = min(1.0, stats.wilcoxon(w[a], w[b]).pvalue * 6)
        print(f'    {a:6s} x {b:6s}  Wilcoxon p_bonf={pw:.3g}{"*" if pw < .05 else " "}  '
              f'{a}>{b} in {int((d > 0).sum())}, < in {int((d < 0).sum())}, = in {int((d == 0).sum())} blocks')
