"""Status Code Coverage (coverage_criteria/output_status_code.py)."""
import pytest

from coverage_criteria import output_status_code
from coverage_criteria.common import Operation
from support import get_items, post_items, run_pipeline


def test_required_status_codes(mini_criteria):
    assert sorted((e['method'], e['path'], e['status_code'])
                  for e in mini_criteria['output_status_code']['required_elements']) == sorted([
        ('GET', '/items', '200'), ('GET', '/items', '404'), ('POST', '/items', '201'), ('POST', '/items', '422'),
        ('GET', '/items/{id}', '200'), ('GET', '/items/{id}', '500'), ('GET', '/types/{kind}', '200')])


def test_default_response_is_not_a_status_code():
    operation = Operation('/p', 'get', {'responses': {'200': {}, 'default': {}}}, {})
    assert [e['status_code'] for e in output_status_code.required_elements(operation)] == ['200']


def test_documented_status_codes_obtained(tmp_path):
    result = run_pipeline(tmp_path,
                          get_items('', status=200),
                          get_items('', status=404).replace('test_0', 'test_1'),
                          post_items(r'" \"name\": \"n\" "').replace('test_0', 'test_2'))
    covered = {(e['method'], e['path'], e['status_code'])
               for e in result.criteria['output_status_code']['required_elements'] if e['covered']}
    assert covered == {('GET', '/items', '200'), ('GET', '/items', '404'), ('POST', '/items', '201')}
    assert result.criteria['output_status_code']['coverage'] == pytest.approx(300 / 7)


def test_undocumented_status_code_covers_nothing(tmp_path):
    result = run_pipeline(tmp_path, post_items(r'" \"name\": \"n\" "', status=400))
    assert result.criteria['output_status_code']['coverage'] == 0.0
