"""Recomputes the official run (03/05/2025) from the archived specification and the
generated tests, using the tool as it is now.

The archived criteria/ and the published CSV come from the version of the tool used in
the paper (tag pre-revisao-jss). The revision changed Request Parameter, Request
Parameter Value and Status Code Class Coverage, and the coverage of Response Body
Properties, so only the remaining criteria are expected to reproduce them exactly.
"""
import csv
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from criteria_analyzer import run_criteria_analyzer
from extract_criteria_from_swagger import filter_endpoints
from extract_tests_data import (concatenated_string, extract_calls, extract_function_lines,
                                extract_request_lines_blocks, run_extract_test_data)
from support import CRITERIA, as_text

pytestmark = pytest.mark.published

# Criteria whose required elements or coverage the revision did not change.
UNCHANGED_ELEMENTS = ['input_path', 'input_operation', 'output_status_code', 'output_response_body_properties']
UNCHANGED_COVERAGE = ['input_path', 'input_operation', 'output_status_code']

REPO_DIR = Path(__file__).resolve().parents[2]
OFFICIAL_RUN = REPO_DIR / 'results' / 'official-run'
PUBLISHED_CSV = REPO_DIR / 'results' / 'statistics' / 'experiment-date-03-05-25-time-21-29-51-725.csv'
TARGET_TAGS = ['Estudantes', 'Profissionais da Educação']
TECHNIQUES = ['RANDOM', 'SMARTS', 'WTS']
RUNS = [(repetition, technique) for repetition in range(10) for technique in TECHNIQUES]


def generated_test_files(run_dir):
    folder = run_dir / 'generated_tests'
    return sorted(f.name for f in folder.iterdir() if f.name.startswith('EvoMaster') and f.name.endswith('Test.py'))


def as_multiset(criterion_file):
    # Response body properties come out of a Python set, so their order varies between runs.
    return Counter(json.dumps(e, sort_keys=True) for e in json.loads(criterion_file.read_text())['required_elements'])


@pytest.fixture(scope='module')
def criteria_dir(tmp_path_factory):
    main_dir = tmp_path_factory.mktemp('official-run')
    shutil.copy(OFFICIAL_RUN / 'api-docs.json', main_dir / 'api-docs.json')
    filter_endpoints(json.loads((main_dir / 'api-docs.json').read_text()), TARGET_TAGS, str(main_dir))
    return main_dir


@pytest.fixture(scope='module')
def recomputed(criteria_dir, tmp_path_factory):
    """The 30 official runs analysed again by the current tool, keyed by (repetition, technique)."""
    runs = {}
    for repetition, technique in RUNS:
        source = OFFICIAL_RUN / f'repetition_{repetition}' / technique
        run_dir = tmp_path_factory.mktemp(f'rep{repetition}-{technique}')
        (run_dir / 'generated_tests').symlink_to(source / 'generated_tests')
        run_extract_test_data(str(run_dir), generated_test_files(source), str(criteria_dir))
        run_criteria_analyzer(str(criteria_dir), str(run_dir))
        runs[(repetition, technique)] = SimpleNamespace(
            extracted=json.loads((run_dir / 'extracted_test_data.json').read_text()),
            criteria={name: json.loads((run_dir / 'criteria_analyzed' / f'{name}.json').read_text())
                      for name in CRITERIA})
    return runs


@pytest.fixture(scope='module')
def published():
    with PUBLISHED_CSV.open(newline='', encoding='utf-8') as f:
        return {(row['algorithm'], int(row['repetition'])): row for row in csv.DictReader(f)}


@pytest.mark.parametrize('criterion', UNCHANGED_ELEMENTS)
def test_required_elements_match_the_archived_ones(criteria_dir, criterion):
    recomputed_elements = as_multiset(criteria_dir / 'criteria' / f'{criterion}.json')
    archived_elements = as_multiset(OFFICIAL_RUN / 'criteria' / f'{criterion}.json')
    assert recomputed_elements == archived_elements


def test_required_elements_of_the_revised_criteria(criteria_dir):
    def by(criterion, key):
        elements = json.loads((criteria_dir / 'criteria' / f'{criterion}.json').read_text())['required_elements']
        return Counter(e[key] for e in elements)

    # The 43 query/path parameters and 12 query values of the paper, plus the request-body fields.
    assert by('input_parameter', 'parameter_type') == {'query': 35, 'path': 8, 'body': 158}
    assert by('input_parameter_value', 'parameter_type') == {'query': 12, 'body': 120}
    assert by('output_status_code_class', 'status_code_class') == {'2XX': 19, '4XX/5XX': 19}


@pytest.mark.parametrize('repetition, technique', RUNS)
def test_recomputed_coverage_matches_the_published_csv(recomputed, published, repetition, technique):
    run = recomputed[(repetition, technique)]
    row = published[(technique, repetition)]
    assert sum(len(tests) for tests in run.extracted.values()) == int(row['num_tests'])
    for criterion in UNCHANGED_COVERAGE:
        assert run.criteria[criterion]['coverage'] == pytest.approx(
            float(row[f'{criterion}_coverage']), abs=1e-9), criterion


def recomputed_calls(recomputed):
    for (repetition, technique), run in recomputed.items():
        for tests in run.extracted.values():
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


def test_no_call_loses_its_request_url(recomputed):
    # Before the revision, 130 SMARTS calls written with resolve_location(...) lost their URL.
    lost = Counter(technique for technique, call in recomputed_calls(recomputed) if not call['request'])
    assert not lost, dict(lost)


def test_every_request_body_expression_is_read():
    # Bodies are read when the API could parse them too: of the 3114 bodies sent,
    # 333 are empty lists and 11 are invalid JSON as sent (e.g. "Arag\ão").
    unread, outcome = [], Counter()
    for repetition, technique in RUNS:
        source = OFFICIAL_RUN / f'repetition_{repetition}' / technique
        for name in generated_test_files(source):
            for block in extract_function_lines(source / 'generated_tests' / name)['lines']:
                for request in extract_request_lines_blocks(block):
                    match = re.search(r'^\s*body = ((?!\{\})(?:.*\\\n)*.*)', request, re.MULTILINE)
                    if not match:
                        continue
                    body = concatenated_string(match.group(1).replace('\\\n', ' '))
                    if body is None:
                        unread.append((repetition, technique, name))
                        continue
                    try:
                        outcome['empty' if json.loads(body) in ([], {}) else 'fields'] += 1
                    except ValueError:
                        outcome['invalid JSON'] += 1
    assert not unread
    assert outcome == {'fields': 2770, 'empty': 333, 'invalid JSON': 11}


def test_boolean_values_sent_are_counted(recomputed):
    # Before the revision, no boolean value was ever counted.
    sent = Counter()
    for technique, call in recomputed_calls(recomputed):
        for parameter in call.get('parameters', []):
            values = parameter['value'] if isinstance(parameter['value'], list) else [parameter['value']]
            sent[technique] += sum(bool(re.fullmatch(r'true|false', str(v))) for v in values)
    covered = Counter()
    for (repetition, technique), run in recomputed.items():
        covered[technique] += sum(e['covered'] for e in run.criteria['input_parameter_value']['required_elements']
                                  if as_text(e['value']) in ('true', 'false'))
    techniques_that_sent = [t for t in TECHNIQUES if sent[t]]
    assert techniques_that_sent and all(covered[t] > 0 for t in techniques_that_sent), {
        'boolean values sent': dict(sent), 'boolean elements covered': dict(covered)}
