"""Why MIO covers fewer RBPC elements of the /inep/{inep} lists: list length in the 200 responses of the kept tests.

Usage: python inep_lists.py > output/inep_lists.txt   (after main_campaign.py)
"""
import gzip
import json
import re
from collections import Counter

import pandas as pd

from main_campaign import CACHE, OFFICIAL

elements, _ = pd.read_pickle(CACHE / 'elements_allocation.pkl')
pd.set_option('display.width', 220, 'display.max_rows', 300)

GROUPS = {'prof_inep': ('/v1/profissionais/inep/{inep}', r'/v1/profissionais/inep/[^/?]+'),
          'est_inep': ('/v1/estudantes/inep/{inep}', r'/v1/estudantes/inep/[^/?]+')}
rows = []
for run_file in sorted(OFFICIAL.glob('repetition_*/*/run.json')):
    r = json.load(open(run_file))
    d = run_file.parent
    row = {'block': r['block'], 'tech': r['algorithm']}
    els = elements[(r['block'], r['algorithm'], 'RBPC')]
    for g, (path, rx) in GROUPS.items():
        grp = [e for e in els if e['path'] == path and e['method'] == 'GET' and e['status_code'] == '200']
        row[g + '_cov%'] = round(100 * sum(e['covered'] for e in grp) / len(grp), 1)
        lengths = []
        with gzip.open(d / 'suite_http.jsonl.gz', 'rt') as fh:   # suite as generated, the one RBPC is read from
            for line in fh:
                x = json.loads(line)
                if x['method'] == 'GET' and re.search(rx + r'($|\?)', x['url'].replace('http://localhost:8000', '')) \
                        and x['status'] == 200:
                    try:
                        body = json.loads(x['response_body'])
                        data = body.get('data')
                        lengths.append(len(data) if isinstance(data, list) else ('obj' if data else 0))
                    except Exception:
                        lengths.append('?')
        row[g + '_200'] = len(lengths)
        row[g + '_lists'] = ','.join(map(str, sorted(lengths, key=str)))
    rows.append(row)
df = pd.DataFrame(rows)
for g in GROUPS:
    print('\n===', g)
    for t in ['MIO', 'RANDOM', 'SMARTS', 'WTS']:
        sub = df[df.tech == t]
        print(t, 'group coverage per execution:', Counter(sub[g + '_cov%']))
    sub = df[(df.tech == 'MIO')].sort_values(g + '_cov%')
    print(sub[['block', g + '_cov%', g + '_200', g + '_lists']].to_string(index=False))
    print('other techniques, list sizes in the 200 responses:')
    for t in ['RANDOM', 'SMARTS', 'WTS']:
        print(' ', t, Counter(df[df.tech == t][g + '_lists']).most_common(4))
