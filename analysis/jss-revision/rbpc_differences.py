"""Which RBPC groups differ between assertion-based and observed-response coverage (main campaign).

Usage: python rbpc_differences.py > output/rbpc_differences.txt
"""
import gzip
import json
from collections import Counter, defaultdict

from main_campaign import OFFICIAL, operation


def flatten(obj, prefix=''):
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


lost, gained = defaultdict(Counter), defaultdict(Counter)
for f in sorted(OFFICIAL.glob('repetition_*/*/criteria_analyzed/output_response_body_properties.json')):
    run = f.parent.parent
    t = run.name
    obs = set()
    with gzip.open(run / 'suite_without_assertions_http.jsonl.gz', 'rt') as fh:
        for line in fh:
            x = json.loads(line)
            if not x.get('response_body') or x.get('status') is None:
                continue
            m, p = operation(x['method'], x['url'].replace('http://localhost:8000', '')).split(' ', 1)
            obs |= {(p, m, str(x['status']), q) for q in flatten(json.loads(x['response_body']))}
    for e in json.load(open(f))['required_elements']:
        k = (e['path'], e['method'], str(e['status_code']), e['property'])
        g = f"{e['method']} {e['path']} {e['status_code']}"
        if e['covered'] and k not in obs:
            lost[t][g] += 1
        if not e['covered'] and k in obs:
            gained[t][g] += 1
for t in ['MIO', 'RANDOM', 'SMARTS', 'WTS']:
    print(t, 'covered through assertions and not observed in the re-execution (sum over 30 executions):')
    for g, n in lost[t].most_common(6):
        print(f'   {n:5d}  {g}')
    print(t, 'observed in the re-execution and not covered through assertions:')
    for g, n in gained[t].most_common(6):
        print(f'   {n:5d}  {g}')
