"""RPVC and request-body exposure, full vs low budget: POST calls, calls per test and RPVC per execution.

Counts calls in the generated suites (extracted_test_data.json), the source of RPVC, and in the HTTP
traffic of the replay without assertions. Paired by block and technique (blocks 0-9).
Usage: python rpvc_post_low_budget.py [low_budget_dir] > output/rpvc_post_low_budget.txt
"""
import gzip
import json
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

from main_campaign import LOW_BUDGET, OFFICIAL, TECHS

LOW = Path(sys.argv[1]) if len(sys.argv) > 1 else LOW_BUDGET
BLOCKS = 10
pd.set_option('display.width', 220, 'display.max_columns', 40)


def suite_counts(run_dir):
    tests = calls = post = 0
    for file_tests in json.load(open(run_dir / 'extracted_test_data.json')).values():
        for t in file_tests.values():
            tests += 1
            calls += len(t['paths'])
            post += sum(c['method'] == 'POST' for c in t['paths'])
    replay_post = 0
    with gzip.open(run_dir / 'suite_without_assertions_http.jsonl.gz', 'rt') as fh:
        for line in fh:
            replay_post += json.loads(line).get('method', '').upper() == 'POST'
    rpvc = json.load(open(run_dir / 'criteria_analyzed/input_parameter_value.json'))['coverage']
    return {'tests': tests, 'calls': calls, 'post': post, 'replay_post': replay_post, 'RPVC': rpvc}


def collect(base, budget, blocks=None):
    rows = []
    for f in sorted(base.glob('repetition_*/*/run.json')):
        r = json.load(open(f))
        if blocks is not None and r['block'] >= blocks:
            continue
        rows.append({'budget': budget, 'block': r['block'], 'algorithm': r['algorithm'],
                     **suite_counts(f.parent)})
    return pd.DataFrame(rows)


full_all = collect(OFFICIAL, 'full')
low = collect(LOW, 'low')
full = full_all[full_all.block < BLOCKS]
for d in (full_all, full, low):
    d['calls_per_test'] = d.calls / d.tests

print('Check against the paper (30 blocks, median POST calls in the suite; paper: MIO 118.5, SMARTS 117, '
      'RANDOM 49.5, WTS 58):')
print('  generated tests:', full_all.groupby('algorithm').post.median().to_dict())
print('  replay without assertions:', full_all.groupby('algorithm').replay_post.median().to_dict())

print('\nMedians per technique and budget (blocks 0-9):')
both = pd.concat([full, low])
print(both.groupby(['algorithm', 'budget'])[['tests', 'calls', 'calls_per_test', 'post', 'replay_post', 'RPVC']]
      .median().round(2).to_string())

print('\nLow - full, paired by block (median of the difference; blocks with low > full; Wilcoxon p):')
pairs = low.merge(full, on=['block', 'algorithm'], suffixes=('_low', '_full'))
for t in TECHS:
    p = pairs[pairs.algorithm == t]
    parts = []
    for col in ['calls_per_test', 'post', 'RPVC']:
        d = p[col + '_low'] - p[col + '_full']
        w = stats.wilcoxon(d).pvalue if (d != 0).any() else float('nan')
        parts.append(f'{col} {d.median():+.2f} ({int((d > 0).sum())}/{len(d)}, p={w:.3f})')
    print(f'  {t:7s} ' + ' | '.join(parts))

print('\nSpearman RPVC x POST calls in the suite:')
for name, d in [('full, 30 blocks', full_all), ('low', low), ('full 0-9 + low', both)]:
    rho, p = stats.spearmanr(d.post, d.RPVC)
    print(f'  {name:20s} all executions: rho={rho:.2f} p={p:.2g}')
for t in TECHS:
    d = both[both.algorithm == t]
    rho, p = stats.spearmanr(d.post, d.RPVC)
    print(f'  {t:7s} full 0-9 + low (n={len(d)}): rho={rho:.2f} p={p:.2g}')
