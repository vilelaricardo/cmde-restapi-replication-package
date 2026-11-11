"""Element level and request allocation of the main campaign (reads the cache written by main_campaign.py).

Writes data/elements_<criterion>.csv: for each required element, in how many of the 30 executions
each technique covered it.
Usage: python element_allocation.py > output/element_allocation.txt
"""
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA, CACHE = HERE / 'data', HERE / 'cache'
TECHS = ['MIO', 'RANDOM', 'SMARTS', 'WTS']
KEYS = {'RPC': ('path', 'method', 'parameter', 'parameter_type'),
        'RPVC': ('path', 'method', 'parameter', 'parameter_type', 'value'),
        'SCCC': ('path', 'method', 'status_code_class'), 'SCC': ('path', 'method', 'status_code'),
        'RBPC': ('path', 'method', 'status_code', 'property')}
pd.set_option('display.width', 250, 'display.max_columns', 40, 'display.max_rows', 400, 'display.max_colwidth', 110)

elements, allocation = pd.read_pickle(CACHE / 'elements_allocation.pkl')
runs = pd.read_csv(DATA / 'runs_main.csv')


def hr(t):
    print('\n' + '=' * 90 + '\n' + t + '\n' + '=' * 90)


def key(c, e):
    return ' | '.join(str(e.get(k)) for k in KEYS[c])


freq = {c: defaultdict(Counter) for c in KEYS}
per_run = defaultdict(dict)  # (block, tech) -> set of covered keys per criterion
for (b, t, c), els in elements.items():
    if c not in KEYS:
        continue
    covered = set()
    for e in els:
        k = key(c, e)
        freq[c][k][t] += int(bool(e['covered']))
        if e['covered']:
            covered.add(k)
    per_run[(b, t)][c] = covered

hr('F. Elements: how many vary and which separate the techniques (frequency in 30 executions)')
tables = {}
for c in KEYS:
    tb = pd.DataFrame({k: {t: v[t] for t in TECHS} for k, v in freq[c].items()}).T.fillna(0).astype(int)
    tables[c] = tb
    never = (tb.sum(axis=1) == 0).sum()
    always = (tb.min(axis=1) == 30).sum()
    print(f'{c}: elements={len(tb)} never covered={never} always covered by all={always} vary={len(tb) - never - always}')
    print('    covered at least once:', {t: int((tb[t] > 0).sum()) for t in TECHS})
    tb.to_csv(DATA / f'elements_{c}.csv')

for c in ['RPVC', 'SCCC', 'SCC']:
    tb = tables[c]
    tb = tb[(tb.max(axis=1) - tb.min(axis=1)) >= 10]
    print(f'\n{c}: elements with a difference >= 10 executions between techniques ({len(tb)})')
    print(tb.sort_values(TECHS, ascending=False).to_string())

hr('F2. RBPC per group (path, method, status): % of elements covered, mean over the 30 executions')
tb = tables['RBPC'].copy()
tb['group'] = [' | '.join(k.split(' | ')[:3]) for k in tb.index]
agg = tb.groupby('group').agg(n=('MIO', 'size'), **{t: (t, 'sum') for t in TECHS})
for t in TECHS:
    agg[t] = (agg[t] / (agg.n * 30) * 100).round(1)
print(agg.sort_values('n', ascending=False).to_string())

hr('F3. RBPC: what explains the dispersion of MIO')
rb = runs[runs.algorithm == 'MIO'][['block', 'RBPC']].copy()
errors = [k for k in tables['RBPC'].index if '/erros' in k]   # batch-error operations (.../lote/{id}/erros)
rb['errors_covered'] = [len(per_run[(b, 'MIO')]['RBPC'] & set(errors)) for b in rb.block]
print(f'RBPC elements in /erros: {len(errors)}')
print(rb.sort_values('RBPC').to_string(index=False))
for t in TECHS:
    v = [len(per_run[(b, t)]['RBPC'] & set(errors)) for b in range(30)]
    print(t, 'elements of /erros covered per execution:', Counter(v))

hr('F4. RBPC elements that separate MIO/SMARTS from RANDOM/WTS (difference >= 15 executions)')
tb = tables['RBPC']
sep = tb[(tb[['MIO', 'SMARTS']].min(axis=1) - tb[['RANDOM', 'WTS']].max(axis=1)) >= 15]
print(len(sep), 'elements;', Counter(' | '.join(k.split(' | ')[:3]) for k in sep.index))
sep2 = tb[(tb.SMARTS - tb.MIO) >= 10]
print('SMARTS >= MIO + 10:', len(sep2), Counter(' | '.join(k.split(' | ')[:3]) for k in sep2.index))

hr('G. Allocation of the search requests per operation (% of the technique total, mean over the 30 executions)')
share = defaultdict(lambda: defaultdict(list))
method_share = defaultdict(lambda: defaultdict(list))
for (b, t), ops in allocation.items():
    total = sum(ops.values())
    for op, n in ops.items():
        share[op][t].append(100 * n / total)
    by_method = Counter()
    for op, n in ops.items():
        by_method[op.split()[0]] += n
    for m, n in by_method.items():
        method_share[m][t].append(100 * n / total)
rows = []
for op, d in share.items():
    rows.append({'operation': op, **{t: round(sum(d.get(t, [])) / 30, 1) for t in TECHS}})
print(pd.DataFrame(rows).sort_values('SMARTS', ascending=False).to_string(index=False))
print('\nby method:')
print(pd.DataFrame({m: {t: round(sum(v.get(t, [])) / 30, 1) for t in TECHS} for m, v in method_share.items()}).T.to_string())
