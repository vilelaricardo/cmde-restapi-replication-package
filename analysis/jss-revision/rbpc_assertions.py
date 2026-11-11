"""RBPC: an RBPC group of a list operation is covered only when a kept test asserted a non-empty list.

For every execution (2025 recomputed and 2026 main campaign) and every GET 200 operation, read the
generated tests and record the largest list length asserted on `data` (assert len(res_k.json()["data"]) == N).
Then join with the RBPC coverage of that operation's group. Only lengths and counts are printed,
never asserted values. Writes data/rbpc_assertions.csv.
Usage: python rbpc_assertions.py > output/rbpc_assertions.txt   (after recompute_2025.py)
"""
import json
import re
from collections import Counter, defaultdict

import pandas as pd

from main_campaign import DATA, OFFICIAL, RUN2025

SOURCES = {
    '2025': RUN2025,     # 2025 tests, criteria recomputed with the corrected tool
    '2026': OFFICIAL,
}
pd.set_option('display.width', 250, 'display.max_rows', 500, 'display.max_columns', 40)

DEF = re.compile(r'^\s*def (test_\w+)\(self\):', re.M)
REQ = re.compile(r'\bres_(\d+)\s*=\s*requests\b')
LEN_DATA = re.compile(r'assert len\(res_(\d+)\.json\(\)\["data"\]\) == (\d+)')
ITEM = re.compile(r'res_(\d+)\.json\(\)\["data"\]\[\d+\]')


def asserted_lengths(run_dir):
    """(method, path, status) -> list of asserted data lengths, one per call that asserted one."""
    extracted = json.load(open(run_dir / 'extracted_test_data.json'))
    out = defaultdict(list)
    mismatches = 0
    for fname, tests in extracted.items():
        src = (run_dir / 'generated_tests' / fname).read_text()
        bodies = {}
        marks = list(DEF.finditer(src))
        for i, m in enumerate(marks):
            bodies[m.group(1)] = src[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(src)]
        for tname, t in tests.items():
            body = bodies[tname]
            calls = t['paths']
            n_req = len(set(REQ.findall(body)))
            if n_req != len(calls):
                mismatches += 1
                continue
            lens = {int(k): int(v) for k, v in LEN_DATA.findall(body)}
            items = Counter(int(k) for k in ITEM.findall(body))
            for k, c in enumerate(calls):
                if c['method'] == 'GET' and c['status'] == '200' and k in lens:
                    out[(c['method'], c['path'], c['status'])].append((lens[k], items.get(k, 0)))
    return out, mismatches


rows = []
for year, base in SOURCES.items():
    for run_file in sorted(base.glob('repetition_*/*/criteria_analyzed/output_response_body_properties.json')):
        run_dir = run_file.parent.parent
        block, tech = int(run_dir.parent.name.split('_')[1]), run_dir.name
        crit = json.load(open(run_file))
        groups = defaultdict(lambda: [0, 0])
        for e in crit['required_elements']:
            g = (e['method'], e['path'], str(e['status_code']))
            groups[g][0] += 1
            groups[g][1] += int(bool(e['covered']))
        lens, mism = asserted_lengths(run_dir)
        for g, (n, cov) in groups.items():
            if g[0] != 'GET' or g[2] != '200':
                continue
            L = lens.get(g, [])
            rows.append({'year': year, 'tech': tech, 'block': block, 'op': g[1], 'n_el': n, 'covered': cov,
                         'calls_len_asserted': len(L), 'max_len': max((x for x, _ in L), default=None),
                         'item_asserts': sum(i for _, i in L), 'mismatch_tests': mism})
df = pd.DataFrame(rows)
df.to_csv(DATA / 'rbpc_assertions.csv', index=False)

print('tests whose number of requests does not match extracted_test_data:',
      df.groupby('year').mismatch_tests.max().to_dict())

# List operations: those where some run asserted a data length
list_ops = sorted(df[df.calls_len_asserted > 0].op.unique())
print('\nGET 200 operations with a list length asserted in some test:', list_ops)

print('\n=== Group coverage vs. largest asserted list (per operation, year, technique) ===')
for op in list_ops:
    sub = df[df.op == op]
    print(f'\n--- {op} (elements in the group: {sub.n_el.iloc[0]})')
    for (y, t), s in sub.groupby(['year', 'tech']):
        nonempty = s.max_len.fillna(0) > 0
        print(f'  {y} {t:7s} executions={len(s):2d}  non-empty list asserted={int(nonempty.sum()):2d}  '
              f'coverage with a non-empty list={sorted(Counter(s[nonempty].covered).items())}  '
              f'without={sorted(Counter(s[~nonempty].covered).items())}')

print('\n=== Hypothesis test: coverage above the group minimum <=> some non-empty list asserted ===')
for op in list_ops:
    sub = df[df.op == op].copy()
    floor = sub.covered.min()
    sub['above_floor'] = sub.covered > floor
    sub['nonempty'] = sub.max_len.fillna(0) > 0
    tab = pd.crosstab(sub.nonempty, sub.above_floor)
    print(f'\n{op}  (group minimum = {floor} of {sub.n_el.iloc[0]})')
    print(tab.to_string())
