"""Recomputes the official run (03/05/2025) from the archived specification and the
generated tests, and compares it with the published results. Passing tests mean the
tool in this repository reproduces the numbers reported in the paper; the xfail
tests measure, on the real suites, defects also covered by test_criteria.py.
"""
import csv
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest

from criteria_analyzer import run_criteria_analyzer
from extract_criteria_from_swagger import filter_endpoints
from extract_tests_data import extract_calls, extract_function_lines, extract_request_lines_blocks, run_extract_test_data
from support import CRITERIA

pytestmark = pytest.mark.published

REPO_DIR = Path(__file__).resolve().parents[2]
OFFICIAL_RUN = REPO_DIR / 'results' / 'official-run'
PUBLISHED_CSV = REPO_DIR / 'results' / 'statistics' / 'experiment-date-03-05-25-time-21-29-51-725.csv'
TARGET_TAGS = ['Estudantes', 'Profissionais da Educação']
TECHNIQUES = ['RANDOM', 'SMARTS', 'WTS']
RUNS = [(repetition, technique) for repetition in range(10) for technique in TECHNIQUES]


def generated_test_files(run_dir):
    folder = run_dir / 'generated_tests'
    return sorted(f.name for f in folder.iterdir() if f.name.startswith('EvoMaster') and f.name.endswith('Test.py'))


@pytest.fixture(scope='module')
def criteria_dir(tmp_path_factory):
    main_dir = tmp_path_factory.mktemp('official-run')
    shutil.copy(OFFICIAL_RUN / 'api-docs.json', main_dir / 'api-docs.json')
    filter_endpoints(json.loads((main_dir / 'api-docs.json').read_text()), TARGET_TAGS, str(main_dir))
    return main_dir


@pytest.fixture(scope='module')
def published():
    with PUBLISHED_CSV.open(newline='', encoding='utf-8') as f:
        return {(row['algorithm'], int(row['repetition'])): row for row in csv.DictReader(f)}


def as_multiset(criterion_file):
    # Response body properties come out of a Python set, so their order varies between runs.
    return Counter(json.dumps(e, sort_keys=True) for e in json.loads(criterion_file.read_text())['required_elements'])


@pytest.mark.parametrize('criterion', CRITERIA)
def test_required_elements_match_the_archived_ones(criteria_dir, criterion):
    recomputed = as_multiset(criteria_dir / 'criteria' / f'{criterion}.json')
    archived = as_multiset(OFFICIAL_RUN / 'criteria' / f'{criterion}.json')
    assert recomputed == archived


@pytest.mark.parametrize('repetition, technique', RUNS)
def test_recomputed_coverage_matches_the_published_csv(criteria_dir, published, tmp_path, repetition, technique):
    source = OFFICIAL_RUN / f'repetition_{repetition}' / technique
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    (run_dir / 'generated_tests').symlink_to(source / 'generated_tests')

    run_extract_test_data(str(run_dir), generated_test_files(source), str(criteria_dir))
    run_criteria_analyzer(str(criteria_dir), str(run_dir))

    row = published[(technique, repetition)]
    extracted = json.loads((run_dir / 'extracted_test_data.json').read_text())
    assert sum(len(tests) for tests in extracted.values()) == int(row['num_tests'])
    for criterion in CRITERIA:
        coverage = json.loads((run_dir / 'criteria_analyzed' / f'{criterion}.json').read_text())['coverage']
        assert coverage == pytest.approx(float(row[f'{criterion}_coverage']), abs=1e-9), criterion


def official_calls():
    """Every recorded call of the 30 official suites, as extracted by the tool."""
    for repetition, technique in RUNS:
        data = json.loads((OFFICIAL_RUN / f'repetition_{repetition}' / technique / 'extracted_test_data.json').read_text())
        for tests in data.values():
            for test in tests.values():
                for call in test['paths']:
                    yield technique, call


def test_every_call_comment_has_its_request_block():
    mismatches = []
    for repetition, technique in RUNS:
        source = OFFICIAL_RUN / f'repetition_{repetition}' / technique
        for name in generated_test_files(source):
            for block in extract_function_lines(source / 'generated_tests' / name)['lines']:
                calls = extract_calls(''.join(block), '')
                requests = extract_request_lines_blocks(block)
                if len(calls) != len(requests):
                    mismatches.append((repetition, technique, name, len(calls), len(requests)))
    assert not mismatches


@pytest.mark.xfail(reason='calls whose URL is written with resolve_location(...) or str(...) lose their '
                          'request, so their parameters are not counted (mostly SMARTS suites)')
def test_no_call_loses_its_request_url():
    lost = Counter(technique for technique, call in official_calls() if not call['request'])
    assert not lost, dict(lost)


@pytest.mark.xfail(reason='boolean query values are sent but never counted by Request Parameter Value Coverage')
def test_boolean_values_sent_are_counted():
    sent = Counter()
    for technique, call in official_calls():
        for parameter in call.get('parameters', []):
            for value in parameter['value'] if isinstance(parameter['value'], list) else [parameter['value']]:
                if re.fullmatch(r'true|false', str(value)):
                    sent[technique] += 1
    covered = Counter()
    for repetition, technique in RUNS:
        analyzed = json.loads((OFFICIAL_RUN / f'repetition_{repetition}' / technique / 'criteria_analyzed'
                               / 'input_parameter_value.json').read_text())
        covered[technique] += sum(e['covered'] for e in analyzed['required_elements'] if e['value_type'] == 'boolean')
    assert all(covered[t] > 0 for t in sent), {'boolean values sent': dict(sent), 'boolean elements covered': dict(covered)}
