"""RQ1: size of the generated suites in tests, HTTP calls, lines of code and assertions,
plus suite execution time and search requests. Definitions (paper, Table tab:metrics):
  LOC        = lines holding at least one code token (comments and blank lines excluded) in
               EvoMaster_*_Test.py; em_test_utils.py is a fixed helper and is not counted
  assertions = 'assert' statements in the same files
Writes data/rq1_suite_size.csv.
Usage: python rq1_suite_size.py [campaign_dir] [runs_csv] [out_csv] > output/rq1_suite_size.txt
"""
import io
import sys
import tokenize
from pathlib import Path

import pandas as pd
from scipy import stats

from main_campaign import DATA, OFFICIAL, TECHS, compare, describe, hr

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else OFFICIAL
RUNS = Path(sys.argv[2]) if len(sys.argv) > 2 else DATA / 'runs_main.csv'
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else DATA / 'rq1_suite_size.csv'
NON_CODE = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
            tokenize.ENCODING, tokenize.ENDMARKER}


def size(files):
    loc, asserts = 0, 0
    for f in files:
        lines = set()
        for tok in tokenize.tokenize(io.BytesIO(f.read_bytes()).readline):
            if tok.type in NON_CODE:
                continue
            lines.update(range(tok.start[0], tok.end[0] + 1))
            if tok.type == tokenize.NAME and tok.string == 'assert':
                asserts += 1
        loc += len(lines)
    return loc, asserts


rows = []
for d in sorted(BASE.glob('repetition_*/*/generated_tests')):
    run = d.parent
    loc, asserts = size(sorted(d.glob('EvoMaster_*_Test.py')))
    rows.append({'block': int(run.parent.name.split('_')[1]), 'algorithm': run.name, 'LOC': loc, 'assertions': asserts})
df = pd.DataFrame(rows).merge(pd.read_csv(RUNS), on=['block', 'algorithm'])
df['calls_per_test'] = df.HTTP_suite / df.NT
df['assertions_per_test'] = df.assertions / df.NT
df['LOC_per_test'] = df.LOC / df.NT
df.to_csv(OUT, index=False)

MEASURES = ['NT', 'HTTP_suite', 'LOC', 'assertions', 'suite_na_s', 'requests_api']
hr('RQ1: descriptive')
describe(df, MEASURES + ['calls_per_test', 'assertions_per_test', 'LOC_per_test'])
hr('RQ1: Kruskal-Wallis, Dunn-Bonferroni, A12 [95% CI]')
for col in MEASURES + ['calls_per_test', 'assertions_per_test']:
    compare(df, col)
hr('RQ1: sensitivity to the blocks (Friedman + paired Wilcoxon, Bonferroni)')
for col in MEASURES:
    w = df.pivot(index='block', columns='algorithm', values=col)[TECHS]
    chi, p = stats.friedmanchisquare(*[w[t] for t in TECHS])
    pairs = []
    for i, a in enumerate(TECHS):
        for b in TECHS[i + 1:]:
            if (w[a] != w[b]).any():
                pw = min(1.0, stats.wilcoxon(w[a], w[b]).pvalue * 6)
                pairs.append(f'{a}-{b} {pw:.2g}{"*" if pw < .05 else ""}')
    print(f'[{col}] Friedman p={p:.2g} | ' + '  '.join(pairs))
