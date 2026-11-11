"""Recompute the coverage of the 2025 study (results/official-run) with the corrected measurement tool.

Works on a copy in cache/run2025 (results/official-run is not modified) and writes the coverage of
each execution to data/coverage_2025.csv. rbpc_assertions.py and rbpc_sensitivity.py read the copy.
Usage: python recompute_2025.py [output_dir]
"""
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tool'))
from criteria_analyzer import run_criteria_analyzer  # noqa: E402
from extract_criteria_from_swagger import filter_endpoints  # noqa: E402
from extract_tests_data import run_extract_test_data  # noqa: E402

out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'cache' / 'run2025'
if out.exists():
    shutil.rmtree(out)
shutil.copytree(REPO / 'results/official-run', out)
shutil.rmtree(out / 'criteria')
swagger = json.load(open(out / 'api-docs.json'))
filter_endpoints(swagger, ['Estudantes', 'Profissionais da Educação'], str(out))

rows = []
for rep in sorted(out.glob('repetition_*'), key=lambda p: int(p.name.split('_')[1])):
    for algo in sorted(p for p in rep.iterdir() if p.is_dir()):
        files = sorted(f.name for f in (algo / 'generated_tests').iterdir()
                       if f.name.startswith('EvoMaster') and f.name.endswith('Test.py'))
        run_extract_test_data(str(algo), files, str(out))
        run_criteria_analyzer(str(out), str(algo))
        row = {'block': int(rep.name.split('_')[1]), 'algorithm': algo.name}
        for f in (algo / 'criteria_analyzed').glob('*.json'):
            row[f.stem] = json.load(open(f))['coverage']
        rows.append(row)
(HERE / 'data').mkdir(exist_ok=True)
pd.DataFrame(rows).to_csv(HERE / 'data' / 'coverage_2025.csv', index=False)
print(len(rows), 'executions recomputed')
