"""Low-budget campaign (ratePerMinute 20, 10 blocks) against the main campaign and the 2025 study.

The low-budget plan repeats blocks 0-9 of the main plan (same order and EvoMaster seeds), so
each execution pairs with the main-campaign one of the same block and technique.
Reads data/runs_main.csv, data/rbpc_assertions.csv, data/inep_search.csv and data/coverage_2025.csv;
writes data/runs_low_budget.csv.
Usage: python low_budget.py [low_budget_dir] > output/low_budget.txt
"""
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from main_campaign import (CRIT, DATA, LOW_BUDGET, OFFICIAL, TECHS, VARIABLE, a12, a12_ci, compare, describe, hr,
                           load_runs, magnitude)

LOW = Path(sys.argv[1]) if len(sys.argv) > 1 else LOW_BUDGET
BLOCKS = 10
LIST_OPS = ['/v1/estudantes', '/v1/estudantes/inep/{inep}', '/v1/estudantes/lote',
            '/v1/estudantes/solicitacoes-alteracoes', '/v1/estudantes/validacao-cadastro',
            '/v1/profissionais', '/v1/profissionais/inep/{inep}', '/v1/profissionais/lote']
SHOWN_OPS = ['/v1/estudantes', '/v1/estudantes/inep/{inep}', '/v1/estudantes/solicitacoes-alteracoes',
             '/v1/estudantes/validacao-cadastro', '/v1/profissionais/inep/{inep}']
pd.set_option('display.width', 220, 'display.max_columns', 40, 'display.max_rows', 300)

DEF = re.compile(r'^\s*def (test_\w+)\(self\):', re.M)
REQ = re.compile(r'\bres_(\d+)\s*=\s*requests\b')
LEN_DATA = re.compile(r'assert len\(res_(\d+)\.json\(\)\["data"\]\) == (\d+)')
INEP = re.compile(r'"GET /v1/(profissionais|estudantes)/inep/[^/? ]+(\?\S*)? HTTP/[\d.]+" (\d{3}) (\d+)')


def asserted_lengths(run_dir):
    """(path) of a GET 200 call -> data lengths asserted on it (same parsing as rbpc_assertions.py)."""
    extracted = json.load(open(run_dir / 'extracted_test_data.json'))
    out = defaultdict(list)
    for fname, tests in extracted.items():
        src = (run_dir / 'generated_tests' / fname).read_text()
        marks = list(DEF.finditer(src))
        bodies = {m.group(1): src[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(src)]
                  for i, m in enumerate(marks)}
        for tname, t in tests.items():
            body = bodies[tname]
            if len(set(REQ.findall(body))) != len(t['paths']):
                continue
            lens = {int(k): int(v) for k, v in LEN_DATA.findall(body)}
            for k, c in enumerate(t['paths']):
                if c['method'] == 'GET' and c['status'] == '200' and k in lens:
                    out[c['path']].append(lens[k])
    return out


def run_extras(run_dir):
    """Per-execution facts load_runs does not keep: exit codes, list groups, inep calls during the search."""
    r = json.load(open(run_dir / 'run.json'))
    row = {'block': r['block'], 'algorithm': r['algorithm'], 'seed': r['seed'],
           'search_exit': r['search']['exit_code'],
           'na_failures': r['suite_without_assertions']['failures'],
           'na_errors': r['suite_without_assertions']['errors']}
    els = json.load(open(run_dir / 'criteria_analyzed/output_response_body_properties.json'))['required_elements']
    lens = asserted_lengths(run_dir)
    in_list = [e for e in els if e['method'] == 'GET' and str(e['status_code']) == '200' and e['path'] in LIST_OPS]
    row['n_el'], row['n_list'] = len(els), len(in_list)
    row['cov_all'] = sum(e['covered'] for e in els)
    row['cov_list'] = sum(e['covered'] for e in in_list)
    for op in LIST_OPS:
        row['kept:' + op] = any(x > 0 for x in lens.get(op, []))
        row['cov:' + op] = sum(e['covered'] for e in in_list if e['path'] == op)
    n = {'prof': [0, 0], 'est': [0, 0]}
    with gzip.open(run_dir / 'search_logs/nginx_access.log.gz', 'rt', errors='replace') as fh:
        for line in fh:
            m = INEP.search(line) if 'Jersey' in line else None
            if m:
                g = 'prof' if m.group(1) == 'profissionais' else 'est'
                n[g][0] += 1
                n[g][1] += m.group(3) == '200' and int(m.group(4)) > 400
    for g, (calls, nonempty) in n.items():
        row[g + '_calls'], row[g + '_nonempty'] = calls, nonempty
    return row


def enough(df, k=3):
    return all((df.algorithm == t).sum() >= k for t in TECHS)


def main():
    df, _, _ = load_runs(LOW)
    extras = pd.DataFrame([run_extras(f.parent) for f in sorted(LOW.glob('repetition_*/*/run.json'))])
    df = df.merge(extras, on=['block', 'algorithm'])
    df['req_per_min'] = df.requests_api / (df.search_s / 60)
    best = {op: 0 for op in LIST_OPS}
    official = pd.read_csv(DATA / 'runs_main.csv')
    rb = pd.read_csv(DATA / 'rbpc_assertions.csv')
    for op in LIST_OPS:   # best coverage of each list group over 2025, main campaign and low budget
        best[op] = int(max(rb[rb.op == op].covered.max(), df['cov:' + op].max()))
    df['RBPC_list'] = 100 * df.cov_list / df.n_list
    df['RBPC_rest'] = 100 * (df.cov_all - df.cov_list) / (df.n_el - df.n_list)
    df['RBPC_cf'] = 100 * (df.cov_all - df.cov_list + sum(best.values())) / df.n_el
    df.to_csv(DATA / 'runs_low_budget.csv', index=False)

    hr('A. Integrity')
    print('directory:', LOW.name)
    print(f'executions completed: {len(df)} of {BLOCKS * len(TECHS)}', df.status.value_counts().to_dict(),
          df.groupby('algorithm').size().to_dict())
    plan_low = {(p['block'], p['algorithm']): p['seed'] for p in json.load(open(LOW / 'plan.json'))}
    plan_off = {(p['block'], p['algorithm']): p['seed'] for p in json.load(open(OFFICIAL / 'plan.json'))
                if p['block'] < BLOCKS}
    print('plan equal to blocks 0-9 of the main campaign:', plan_low == plan_off,
          '| executed seeds match the plan:',
          all(plan_low[(r.block, r.algorithm)] == r.seed for r in df.itertuples()))
    print('search with exit code != 0:', int((df.search_exit != 0).sum()),
          '| suite without assertions with failures/errors:', int((df.na_failures + df.na_errors > 0).sum()))
    print(f'search (s): {df.search_s.min():.0f} - {df.search_s.max():.0f}'
          f' | requests per minute: {df.req_per_min.min():.2f} - {df.req_per_min.max():.2f}')
    print('requests to the API (min-max per technique):',
          df.groupby('algorithm').requests_api.agg(['min', 'max']).to_dict('index'))
    print('evaluated_actions - requests to the API (median per technique):',
          (df.evaluated_actions - df.requests_api).groupby(df.algorithm).median().to_dict())
    print('NT (pytest) == NT extracted:', bool((df.NT == df.NT_extracted).all()))

    hr('B. Descriptive')
    describe(df, ['requests_api', 'evaluated_tests', 'NT', 'HTTP_suite', 'suite_failures'])
    describe(df, list(CRIT))

    hr('C. Inference among techniques in the low budget (Kruskal-Wallis, Dunn-Bonferroni, A12)')
    if enough(df):
        for col in ['NT', 'requests_api', *VARIABLE]:
            compare(df, col)
    else:
        print('fewer than 3 executions for some technique: inference postponed')

    hr('D. Low budget x full budget, paired by seed (blocks 0-9 of the main campaign)')
    off = official[official.block < BLOCKS]
    pairs = df.merge(off, on=['block', 'algorithm'], suffixes=('_low', '_full'))
    rows = []
    for t in TECHS:
        p = pairs[pairs.algorithm == t]
        for col in ['requests_api', 'NT', *VARIABLE]:
            d = p[col + '_low'] - p[col + '_full']
            w = stats.wilcoxon(d).pvalue if len(d) >= 5 and (d != 0).any() else np.nan
            rows.append({'technique': t, 'measure': col, 'pairs': len(p), 'low': round(p[col + '_low'].median(), 2),
                         'full': round(p[col + '_full'].median(), 2), 'median_diff': round(d.median(), 2),
                         'low<full': int((d < 0).sum()), 'low>full': int((d > 0).sum()),
                         'Wilcoxon_p': round(w, 4) if w == w else None})
    print(pd.DataFrame(rows).to_string(index=False))

    hr('E. Low budget x 2025 (same technique; 2025 recomputed with the corrected tool)')
    c25 = pd.read_csv(DATA / 'coverage_2025.csv').rename(columns={v: k for k, v in CRIT.items()})
    rows = []
    for t in ['RANDOM', 'SMARTS', 'WTS']:
        x, y = df[df.algorithm == t], c25[c25.algorithm == t]
        for col in VARIABLE:
            if len(x) == 0:
                continue
            A = a12(x[col], y[col])
            lo, hi = a12_ci(x[col], y[col]) if len(x) > 1 else (np.nan, np.nan)
            mw = stats.mannwhitneyu(x[col], y[col]).pvalue if len(x) > 1 else np.nan
            rows.append({'technique': t, 'criterion': col, 'n_low': len(x), 'low': round(x[col].median(), 2),
                         '2025': round(y[col].median(), 2), 'A12(low,2025)': round(A, 2),
                         'CI95': f'[{lo:.2f}, {hi:.2f}]', 'magnitude': magnitude(A), 'MW_p': round(mw, 4)})
    print(pd.DataFrame(rows).to_string(index=False))
    print('\nRBPC between techniques, A12(RANDOM, SMARTS) [CI95]:')
    for name, d in [('2025', c25), ('full budget, blocks 0-9', off), ('full budget, 30 blocks', official),
                    ('low budget', df)]:
        x, y = d[d.algorithm == 'RANDOM'].RBPC, d[d.algorithm == 'SMARTS'].RBPC
        if len(x) and len(y):
            lo, hi = a12_ci(x, y) if min(len(x), len(y)) > 1 else (np.nan, np.nan)
            print(f'  {name:28s} {a12(x, y):.2f} [{lo:.2f}, {hi:.2f}]  medians RANDOM {x.median():.2f}'
                  f' SMARTS {y.median():.2f}  (n={len(x)}, {len(y)})')

    hr('F. RBPC: list groups (executions with a non-empty list asserted / executions)')
    rows = []
    for op in SHOWN_OPS:
        row = {'operation': op}
        for t in TECHS:
            s25 = rb[(rb.year == 2025) & (rb.tech == t) & (rb.op == op)]
            s26 = rb[(rb.year == 2026) & (rb.tech == t) & (rb.op == op)]
            s26b = s26[s26.block < BLOCKS]
            sl = df[df.algorithm == t]
            row[f'{t} 2025'] = f'{int((s25.max_len.fillna(0) > 0).sum())}/{len(s25)}' if len(s25) else '-'
            row[f'{t} full0-9'] = f'{int((s26b.max_len.fillna(0) > 0).sum())}/{len(s26b)}'
            row[f'{t} low'] = f'{int(sl["kept:" + op].sum())}/{len(sl)}'
        rows.append(row)
    print(pd.DataFrame(rows).set_index('operation').T.to_string())
    print('\nbest coverage of each group (for the counterfactual):', best)
    if enough(df):
        for col in ['RBPC', 'RBPC_list', 'RBPC_rest', 'RBPC_cf']:
            compare(df, col)
    else:
        print(df.groupby('algorithm')[['RBPC', 'RBPC_list', 'RBPC_rest', 'RBPC_cf']].median().round(2).to_string())

    hr('G. Calls to /inep/{inep} during the search: total and 200 responses with a non-empty list (median [min, max])')
    ib = pd.read_csv(DATA / 'inep_search.csv')
    ib = ib[ib.block < BLOCKS]
    for g in ('prof', 'est'):
        print(f'--- {g}/inep')
        for t in TECHS:
            s, o = df[df.algorithm == t], ib[ib.tech == t]
            f = lambda v: f'{v.median():.0f} [{v.min()}, {v.max()}]'
            if len(s):
                print(f'  {t:7s} low: calls {f(s[g + "_calls"]):14s} non-empty {f(s[g + "_nonempty"]):12s}'
                      f' with none: {int((s[g + "_nonempty"] == 0).sum())}/{len(s)}'
                      f' | full 0-9: calls {f(o[g + "_calls"]):16s} non-empty {f(o[g + "_nonempty"])}')


if __name__ == '__main__':
    main()
