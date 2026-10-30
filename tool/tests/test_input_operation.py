"""Operation Coverage (coverage_criteria/input_operation.py)."""
import pytest

from coverage_criteria import input_operation
from support import call, get_items, run_pipeline


def test_required_operations(mini_criteria):
    assert sorted((e['method'], e['path']) for e in mini_criteria['input_operation']['required_elements']) == sorted([
        ('GET', '/items'), ('POST', '/items'), ('GET', '/items/{id}'), ('GET', '/types/{kind}')])


def test_operation_requires_matching_method(tmp_path):
    result = run_pipeline(tmp_path, get_items(''))
    assert {(e['method'], e['path']) for e in result.criteria['input_operation']['required_elements']
            if e['covered']} == {('GET', '/items')}
    assert result.criteria['input_operation']['coverage'] == pytest.approx(25.0)


def test_call_covers_only_its_own_method():
    covered = input_operation.covered_keys(call('/items', method='GET'))
    assert input_operation.element_key({'path': '/items', 'method': 'GET'}) in covered
    assert input_operation.element_key({'path': '/items', 'method': 'POST'}) not in covered
