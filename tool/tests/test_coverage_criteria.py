"""The registry of criteria and the extraction that builds their required elements
(coverage_criteria/__init__.py, extract_criteria_from_swagger.py)."""
import copy
import csv
from pathlib import Path

import pytest

from coverage_criteria import CRITERIA
from support import MINI_SPEC, elements, get_items, run_pipeline

PUBLISHED_CSV = Path(__file__).resolve().parents[2] / 'results' / 'statistics' / \
    'experiment-date-03-05-25-time-21-29-51-725.csv'


def test_registry_follows_the_columns_of_the_statistics_csv():
    with PUBLISHED_CSV.open(newline='', encoding='utf-8') as f:
        columns = next(csv.reader(f))
    assert [f'{name}_coverage' for name in CRITERIA] == [c for c in columns if c.endswith('_coverage')]


@pytest.mark.parametrize('name', list(CRITERIA))
def test_each_criterion_implements_the_interface(name):
    criterion = CRITERIA[name]
    assert isinstance(criterion.NEEDS_RESOLVED_SPEC, bool)
    for function in ('required_elements', 'element_key', 'covered_keys'):
        assert callable(getattr(criterion, function)), function
    assert criterion.__doc__, 'each criterion module documents its definition'


def test_operations_outside_target_tags_are_left_out(mini_criteria):
    for name in mini_criteria:
        assert not elements(mini_criteria, name, path='/other'), name


def test_unresolvable_specification_keeps_only_criteria_that_do_not_need_it(tmp_path):
    spec = copy.deepcopy(MINI_SPEC)
    spec['paths']['/items']['get']['responses']['200']['content']['application/json']['schema'] = {
        '$ref': '#/components/schemas/Missing'}
    result = run_pipeline(tmp_path, get_items(''), spec=spec)
    assert set(result.criteria) == {name for name, c in CRITERIA.items() if not c.NEEDS_RESOLVED_SPEC}
