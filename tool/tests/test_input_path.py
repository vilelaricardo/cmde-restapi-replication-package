"""Path Coverage (coverage_criteria/input_path.py)."""
import pytest

from coverage_criteria import input_path
from support import call, covered_set, get_items, post_items, run_pipeline


def test_each_path_is_required_once(mini_criteria):
    # /items has two operations but is a single path.
    assert sorted(e['path'] for e in mini_criteria['input_path']['required_elements']) == [
        '/items', '/items/{id}', '/types/{kind}']


def test_path_covered_by_any_operation_on_it(tmp_path):
    result = run_pipeline(tmp_path, get_items(''), post_items(r'" \"name\": \"n\" "').replace('test_0', 'test_1'))
    assert covered_set(result.criteria, 'input_path', 'path') == {'/items'}
    assert result.criteria['input_path']['coverage'] == pytest.approx(100 / 3)


def test_call_covers_its_path_whatever_the_method_and_status():
    assert input_path.covered_keys(call('/items', method='POST', status='500')) == {
        input_path.element_key({'path': '/items'})}
