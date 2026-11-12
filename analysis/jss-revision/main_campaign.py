"""Analysis of the main campaign (EvoMaster 6.2.0, populated database, 30 blocks).

Methods follow the paper (Kruskal-Wallis, eta^2_H, Dunn with Bonferroni, Spearman), plus
Vargha-Delaney A12 with a bootstrap 95% interval for every pair of techniques.
Writes data/runs_main.csv and cache/elements_allocation.pkl, which the other scripts read.
Usage: python main_campaign.py > output/main_campaign.txt
"""
import gzip
import json
import os
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import scikit_posthocs as sp
from scipy import stats

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.environ.get('CMDE_DATA', REPO / 'tool/data_generated'))
OFFICIAL = DATA_ROOT / 'official-6.2.0'
LOW_BUDGET = DATA_ROOT / 'low-budget-6.2.0'
DATA = HERE / 'data'
CACHE = HERE / 'cache'
RUN2025 = CACHE / 'run2025'   # the 2025 study recomputed with the corrected tool (recompute_2025.py)
TECHS = ['MIO', 'RANDOM', 'SMARTS', 'WTS']
CRIT = {'PC': 'input_path', 'OC': 'input_operation', 'RPC': 'input_parameter', 'RPVC': 'input_parameter_value',
        'SCCC': 'output_status_code_class', 'SCC': 'output_status_code', 'RBPC': 'output_response_body_properties'}
VARIABLE = ['RPC', 'RPVC', 'SCCC', 'SCC', 'RBPC']
pd.set_option('display.width', 220, 'display.max_columns', 40, 'display.max_rows', 300)
RNG = np.random.default_rng(20261108)


def hr(t):
    print('\n' + '=' * 90 + '\n' + t + '\n' + '=' * 90)


def a12(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    return ((x[:, None] > y).sum() + 0.5 * (x[:, None] == y).sum()) / (len(x) * len(y))


def a12_ci(x, y, n=2000):
    x, y = np.asarray(x, float), np.asarray(y, float)
    boot = [a12(RNG.choice(x, len(x)), RNG.choice(y, len(y))) for _ in range(n)]
    return np.percentile(boot, [2.5, 97.5])


def magnitude(a):
    d = abs(a - 0.5)
    return 'negl' if d < 0.06 else 'small' if d < 0.14 else 'medium' if d < 0.21 else 'large'


def spec_operations(spec_file):
    spec = json.load(open(spec_file))
    ops = []
    for path, item in spec['paths'].items():
        rx = re.compile('^' + re.sub(r'\{[^}]+\}', '[^/]+', path) + '$')
        for method in item:
            if method.lower() in ('get', 'post', 'put', 'patch', 'delete'):
                ops.append((rx, method.upper(), path))
    # literal segments before templated ones, so /lote/erros is not taken by /lote/{id}
    ops.sort(key=lambda o: o[2].count('{'))
    return ops


OPS = spec_operations(OFFICIAL / 'api-docs.json')
LINE = re.compile(r'"(GET|POST|PUT|PATCH|DELETE) (\S+) HTTP')


def operation(method, url):
    path = url.split('?')[0]
    for rx, m, p in OPS:
        if m == method and rx.match(path):
            return f'{m} {p}'
    return f'{method} (outside the spec) {path}'


def search_requests(run_dir):
    ops = Counter()
    with gzip.open(run_dir / 'search_logs' / 'nginx_access.log.gz', 'rt', errors='replace') as fh:
        for line in fh:
            if 'Jersey' not in line or '/docs' in line:
                continue
            m = LINE.search(line)
            if m:
                ops[operation(m.group(1), m.group(2))] += 1
    return ops


def load_runs(base):
    rows, elements, allocation = [], {}, {}
    for run_file in sorted(base.glob('repetition_*/*/run.json')):
        r = json.load(open(run_file))
        d = run_file.parent
        tests = json.load(open(d / 'extracted_test_data.json'))
        row = {'block': r['block'], 'pos': r['position'], 'algorithm': r['algorithm'], 'status': r['status'],
               'search_s': r['phases']['search']['seconds'],
               'suite_na_s': r['phases']['suite_without_assertions']['seconds'],
               'evaluated_tests': r['search']['evaluated_tests'], 'evaluated_actions': r['search']['evaluated_actions'],
               'saved_EM': r['search']['saved_tests'], 'NT': r['suite_without_assertions']['tests_run'],
               'NT_extracted': sum(len(v) for v in tests.values()) if isinstance(tests, dict) else None,
               'HTTP_suite': r['suite_without_assertions']['http_exchanges'],
               'suite_failures': r['suite']['failures']}
        for c, f in CRIT.items():
            j = json.load(open(d / 'criteria_analyzed' / f'{f}.json'))
            row[c] = j['coverage']
            elements[(r['block'], r['algorithm'], c)] = j['required_elements']
        ops = search_requests(d)
        allocation[(r['block'], r['algorithm'])] = ops
        row['requests_api'] = sum(ops.values())
        st = Counter()
        with gzip.open(d / 'suite_without_assertions_http.jsonl.gz', 'rt') as fh:
            for line in fh:
                st[json.loads(line)['status']] += 1
        for cl in (2, 4, 5):
            row[f'suite_{cl}xx'] = sum(v for k, v in st.items() if k and k // 100 == cl)
        rows.append(row)
    df = pd.DataFrame(rows).sort_values(['block', 'pos']).reset_index(drop=True)
    return df, elements, allocation


def describe(df, cols):
    for col in cols:
        print(f'\n{col}')
        for t in TECHS:
            v = df[df.algorithm == t][col]
            if v.empty:
                continue
            print(f'  {t:7s} med {v.median():9.2f}  IQR [{v.quantile(.25):9.2f} - {v.quantile(.75):9.2f}]'
                  f'  min-max ({v.min():9.2f} - {v.max():9.2f})  mean {v.mean():9.2f}')


def compare(df, col):
    techs = [t for t in TECHS if (df.algorithm == t).any()]
    groups = [df[df.algorithm == t][col].values for t in techs]
    if np.ptp(np.concatenate(groups)) == 0:
        print(f'\n[{col}] no variance')
        return
    H, p = stats.kruskal(*groups)
    n = sum(map(len, groups))
    eta = (H - len(techs) + 1) / (n - len(techs))
    print(f'\n[{col}] Kruskal-Wallis H={H:.2f} p={p:.3g} eta2_H={eta:.2f}')
    dunn = sp.posthoc_dunn(df[df.algorithm.isin(techs)], val_col=col, group_col='algorithm', p_adjust='bonferroni')
    for a, b in combinations(techs, 2):
        x, y = df[df.algorithm == a][col], df[df.algorithm == b][col]
        A = a12(x, y)
        lo, hi = a12_ci(x, y)
        sig = '*' if dunn.loc[a, b] < .05 else ' '
        print(f'    {a:7s} x {b:7s}  Dunn p={dunn.loc[a, b]:.3g}{sig}  A12={A:.2f} [{lo:.2f}, {hi:.2f}] {magnitude(A)}'
              f'  medians {x.median():.2f} x {y.median():.2f}')


def main():
    DATA.mkdir(exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    df, elements, allocation = load_runs(OFFICIAL)
    df.to_csv(DATA / 'runs_main.csv', index=False)
    pd.to_pickle((elements, allocation), CACHE / 'elements_allocation.pkl')

    hr('A. Integrity')
    print('executions', len(df), df.status.value_counts().to_dict(), df.groupby('algorithm').size().to_dict())
    print('NT (pytest) == NT extracted by the criteria tool:', (df.NT == df.NT_extracted).all())
    print('EvoMaster reports more tests than it wrote:',
          df[df.saved_EM != df.NT].groupby('algorithm').size().to_dict())
    print('search (s):', df.search_s.min(), '-', df.search_s.max())
    print('requests outside the spec:',
          sum(v for ops in allocation.values() for k, v in ops.items() if 'outside the spec' in k))
    print('evaluated_actions - requests to the API, per technique (median):',
          (df.evaluated_actions - df.requests_api).groupby(df.algorithm).median().to_dict())
    starts, ends = [], []
    for run_file in OFFICIAL.glob('repetition_*/*/run.json'):
        phases = json.load(open(run_file))['phases'].values()
        starts += [pd.Timestamp(p['started']) for p in phases]
        ends += [pd.Timestamp(p['finished']) for p in phases]
    print(f'campaign duration (first phase start to last phase end): {(max(ends) - min(starts)).total_seconds() / 3600:.1f} h')
    rate = df.requests_api / (df.search_s / 60)
    print(f'requests to the API per minute of search: {rate.min():.0f} - {rate.max():.0f}')
    failing = 100 * df.suite_failures / df.NT
    print('tests failing when the suite is re-executed with assertions, % (median per technique):',
          failing.groupby(df.algorithm).median().round(1).to_dict(), f'| overall median {failing.median():.1f}')

    hr('B. Descriptive: cost and effort')
    describe(df, ['NT', 'HTTP_suite', 'suite_na_s', 'requests_api', 'evaluated_tests', 'suite_2xx', 'suite_4xx', 'suite_5xx'])
    hr('B2. Descriptive: criteria')
    describe(df, list(CRIT))

    hr('C. Inference (Kruskal-Wallis, Dunn-Bonferroni, A12 with bootstrap 95% CI)')
    for col in ['NT', 'HTTP_suite', 'suite_na_s', 'requests_api', *VARIABLE]:
        compare(df, col)

    hr('D. RQ2: Spearman NT x criterion, over all executions and within each technique')
    for c in VARIABLE:
        rho, p = stats.spearmanr(df.NT, df[c])
        inside = {t: stats.spearmanr(df[df.algorithm == t].NT, df[df.algorithm == t][c]) for t in TECHS}
        print(f'{c:5s} all rho={rho:+.2f} p={p:.3g} | ' +
              '  '.join(f'{t} {r.statistic:+.2f} (p={r.pvalue:.2f})' for t, r in inside.items()))

    hr('E. Comparison between studies: medians per technique')
    c25 = pd.read_csv(DATA / 'coverage_2025.csv').rename(columns={v: k for k, v in CRIT.items()})
    table = []
    for name, d in [('2025 (3.4.0, n=10)', c25), ('2026 main (n=30)', df)]:
        for t in TECHS:
            sub = d[d.algorithm == t]
            if sub.empty:
                continue
            table.append({'study': name, 'technique': t, **{c: round(sub[c].median(), 2) for c in VARIABLE}})
    print(pd.DataFrame(table).to_string(index=False))
    print('\n2025 recomputed, inference among RANDOM, SMARTS, and WTS:')
    for c in VARIABLE:
        compare(c25, c)


if __name__ == '__main__':
    main()
