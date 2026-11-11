"""RBPC: how much of the differences comes from the list groups, and an RBPC from observed responses.

A. Decomposition (2025 recomputed and 2026 main campaign): RBPC elements of the GET 200 groups of list
   operations vs. all other elements, and a counterfactual where every list group is as covered
   as its best execution (as if a non-empty list had been asserted).
B. Observed-response RBPC (2026 only): a property counts when it appears in any response the
   suite received when re-executed without assertions from the restored database
   (suite_without_assertions_http.jsonl.gz). Lists are traversed through all items.
Writes data/rbpc_sensitivity.csv.
Usage: python rbpc_sensitivity.py > output/rbpc_sensitivity.txt   (after recompute_2025.py)
"""
import gzip
import json
from collections import defaultdict
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from main_campaign import DATA, OFFICIAL, RUN2025, a12, a12_ci, hr, magnitude, operation

SOURCES = {'2025': RUN2025, '2026': OFFICIAL}
LIST_OPS = ['/v1/estudantes', '/v1/estudantes/inep/{inep}', '/v1/estudantes/lote',
            '/v1/estudantes/solicitacoes-alteracoes', '/v1/estudantes/validacao-cadastro',
            '/v1/profissionais', '/v1/profissionais/inep/{inep}', '/v1/profissionais/lote']
TECHS = {'2025': ['RANDOM', 'SMARTS', 'WTS'], '2026': ['MIO', 'RANDOM', 'SMARTS', 'WTS']}
pd.set_option('display.width', 220, 'display.max_columns', 40, 'display.max_rows', 300)


def is_list_el(e):
    return e['method'] == 'GET' and str(e['status_code']) == '200' and e['path'] in LIST_OPS


def flatten(obj, prefix=''):
    """Dotted property paths present in a JSON value, list indices dropped, ancestors included."""
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f'{prefix}.{k}' if prefix else k
            out.add(p)
            out |= flatten(v, p)
    elif isinstance(obj, list):
        for v in obj:
            out |= flatten(v, prefix)
    return out


def observed_keys(run_dir):
    keys, bad = set(), 0
    with gzip.open(run_dir / 'suite_without_assertions_http.jsonl.gz', 'rt') as fh:
        for line in fh:
            x = json.loads(line)
            if x.get('status') is None or not x.get('response_body'):
                continue
            op = operation(x['method'], x['url'].replace('http://localhost:8000', ''))
            method, path = op.split(' ', 1)
            try:
                body = json.loads(x['response_body'])
            except ValueError:
                bad += 1
                continue
            keys |= {(path, method, str(x['status']), p) for p in flatten(body)}
    return keys, bad


def compare(df, col, techs):
    groups = [df[df.tech == t][col].values for t in techs]
    h, p = stats.kruskal(*groups)
    n, k = len(df), len(techs)
    print(f'  {col}: medians ' + ', '.join(f'{t} {np.median(g):.2f}' for t, g in zip(techs, groups))
          + f' | KW H={h:.2f} p={p:.2g} eta2={(h - k + 1) / (n - k):.3f}')
    for a, b in combinations(techs, 2):
        x, y = df[df.tech == a][col].values, df[df.tech == b][col].values
        A = a12(x, y)
        lo, hi = a12_ci(x, y)
        print(f'      A12({a},{b})={A:.2f} [{lo:.2f},{hi:.2f}] {magnitude(A)}')


rows, best = [], defaultdict(int)
for year, base in SOURCES.items():
    for f in sorted(base.glob('repetition_*/*/criteria_analyzed/output_response_body_properties.json')):
        run_dir = f.parent.parent
        els = json.load(open(f))['required_elements']
        row = {'year': year, 'tech': run_dir.name, 'block': int(run_dir.parent.name.split('_')[1]),
               'n': len(els), 'cov_all': sum(e['covered'] for e in els),
               'cov_list': sum(e['covered'] for e in els if is_list_el(e)),
               'n_list': sum(is_list_el(e) for e in els)}
        per_group = defaultdict(int)
        for e in els:
            if is_list_el(e):
                per_group[e['path']] += e['covered']
        for g, v in per_group.items():
            row['g:' + g] = v
            best[g] = max(best[g], v)
        if year == '2026':
            obs, bad = observed_keys(run_dir)
            row['cov_obs'] = sum((e['path'], e['method'], str(e['status_code']), e['property']) in obs for e in els)
            row['cov_obs_list'] = sum((e['path'], e['method'], str(e['status_code']), e['property']) in obs
                                      for e in els if is_list_el(e))
            row['cov_union'] = sum(e['covered'] or (e['path'], e['method'], str(e['status_code']), e['property'])
                                   in obs for e in els)
            row['bad_json'] = bad
        rows.append(row)
df = pd.DataFrame(rows)
df['RBPC'] = 100 * df.cov_all / df.n
df['RBPC_rest'] = 100 * (df.cov_all - df.cov_list) / (df.n - df.n_list)
df['RBPC_list'] = 100 * df.cov_list / df.n_list
df['RBPC_cf'] = 100 * (df.cov_all - df.cov_list + sum(best.values())) / df.n
df['RBPC_obs'] = 100 * df.cov_obs / df.n
df['RBPC_union'] = 100 * df.cov_union / df.n
df.to_csv(DATA / 'rbpc_sensitivity.csv', index=False)

hr('A. RBPC decomposition: list groups (GET 200) vs. the rest')
print('RBPC elements:', int(df.n.iloc[0]), '| in the list groups:', int(df.n_list.iloc[0]),
      '| best coverage of each group:', dict(best), '=', sum(best.values()))
for year in SOURCES:
    d = df[df.year == year]
    print(f'\n--- {year}')
    print(d.groupby('tech')[['cov_all', 'cov_list']].median().assign(
        rest=lambda x: x.cov_all - x.cov_list).to_string())
    for col in ['RBPC', 'RBPC_list', 'RBPC_rest', 'RBPC_cf']:
        compare(d, col, TECHS[year])

hr('B. RBPC from the responses observed in the re-execution without assertions (2026)')
d = df[df.year == '2026']
print('responses with invalid JSON (total):', int(d.bad_json.sum()))
print(d.groupby('tech')[['cov_all', 'cov_obs', 'cov_union', 'cov_list', 'cov_obs_list']].median().to_string())
for col in ['RBPC', 'RBPC_obs', 'RBPC_union']:
    compare(d, col, TECHS['2026'])
print('\nSpearman between assertion-based RBPC and observed RBPC (per technique):')
for t in TECHS['2026']:
    s = d[d.tech == t]
    r, p = stats.spearmanr(s.RBPC, s.RBPC_obs)
    print(f'  {t}: rho={r:.2f} p={p:.2g}')
