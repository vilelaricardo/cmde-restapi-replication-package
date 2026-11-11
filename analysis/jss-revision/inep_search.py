"""During the search: how often each technique called the /inep/{inep} lists and got a non-empty one (response size).

Writes data/inep_search.csv (read by low_budget.py).
Usage: python inep_search.py > output/inep_search.txt   (after rbpc_assertions.py)
"""
import gzip
import re

import pandas as pd

from main_campaign import DATA, OFFICIAL

LINE = re.compile(r'"GET (/v1/(profissionais|estudantes)/inep/[^/? ]+)(\?\S*)? HTTP/[\d.]+" (\d{3}) (\d+)')
cov = pd.read_csv(DATA / 'rbpc_assertions.csv')
cov = cov[cov.year == 2026]
rows = []
for d in sorted(OFFICIAL.glob('repetition_*/*')):
    if not d.is_dir():
        continue
    b, t = int(d.parent.name.split('_')[1]), d.name
    n = {'prof': [0, 0, 0], 'est': [0, 0, 0]}   # calls, 200, 200 with body > 400 bytes
    total = 0
    with gzip.open(d / 'search_logs/nginx_access.log.gz', 'rt') as fh:
        for line in fh:
            if 'Jersey' not in line:
                continue
            total += 1
            m = LINE.search(line)
            if not m:
                continue
            g = 'prof' if m.group(2) == 'profissionais' else 'est'
            n[g][0] += 1
            if m.group(4) == '200':
                n[g][1] += 1
                n[g][2] += int(m.group(5)) > 400
    row = {'block': b, 'tech': t, 'requests': total}
    for g, op in (('prof', '/v1/profissionais/inep/{inep}'), ('est', '/v1/estudantes/inep/{inep}')):
        row[g + '_calls'], row[g + '_200'], row[g + '_nonempty'] = n[g]
        c = cov[(cov.block == b) & (cov.tech == t) & (cov.op == op)]
        row[g + '_kept_nonempty'] = bool((c.max_len.fillna(0) > 0).any())
    rows.append(row)
df = pd.DataFrame(rows)
df.to_csv(DATA / 'inep_search.csv', index=False)
pd.set_option('display.width', 200)
for g in ('prof', 'est'):
    print(f'\n=== {g}/inep: calls during the search, 200 responses, 200 with a non-empty list (median [min, max])')
    for t, s in df.groupby('tech'):
        f = lambda c: f'{s[c].median():.0f} [{s[c].min()}, {s[c].max()}]'
        print(f'  {t:7s} calls {f(g + "_calls"):16s} 200 {f(g + "_200"):16s} non-empty {f(g + "_nonempty"):14s}'
              f' | executions with none non-empty: {int((s[g + "_nonempty"] == 0).sum())}'
              f' | suite kept a non-empty one: {int(s[g + "_kept_nonempty"].sum())}')
    m = df[df.tech == 'MIO']
    print('  MIO: cross-tabulation "saw a non-empty list during the search" x "suite kept a non-empty list"')
    print(pd.crosstab(m[g + '_nonempty'] > 0, m[g + '_kept_nonempty']).to_string())
