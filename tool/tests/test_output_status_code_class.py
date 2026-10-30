"""Status Code Class Coverage (coverage_criteria/output_status_code_class.py): one
correct (2XX) and one erroneous (4XX or 5XX) class per operation."""
import pytest

from coverage_criteria.output_status_code_class import class_covers
from support import covered_set, elements, get_items, get_path, post_items, run_pipeline


def classes_of(result, path):
    return {e['status_code_class']: e['covered']
            for e in elements(result.criteria, 'output_status_code_class', path=path)}


def test_two_classes_per_operation_whatever_it_documents(mini_criteria):
    assert sorted((e['method'], e['path'], e['status_code_class'])
                  for e in mini_criteria['output_status_code_class']['required_elements']) == sorted(
        (method, path, cls)
        for method, path in [('GET', '/items'), ('POST', '/items'), ('GET', '/items/{id}'), ('GET', '/types/{kind}')]
        for cls in ('2XX', '4XX/5XX'))


def test_success_and_client_error(tmp_path):
    result = run_pipeline(tmp_path,
                          get_items('', status=200),
                          get_items('', status=404).replace('test_0', 'test_1'),
                          post_items(r'" \"name\": \"n\" "').replace('test_0', 'test_2'))
    covered = {(e['method'], e['path'], e['status_code_class'])
               for e in result.criteria['output_status_code_class']['required_elements'] if e['covered']}
    assert covered == {('GET', '/items', '2XX'), ('GET', '/items', '4XX/5XX'), ('POST', '/items', '2XX')}


def test_server_error_covers_only_the_erroneous_class(tmp_path):
    result = run_pipeline(tmp_path, get_path('/items/{id}', '/items/abc', status=500))
    assert classes_of(result, '/items/{id}') == {'2XX': False, '4XX/5XX': True}


def test_operation_documenting_only_5xx_errors_can_reach_full_coverage(tmp_path):
    # Reviewer 1: /items/{id} documents 200 and 500 but no 4XX.
    result = run_pipeline(tmp_path,
                          get_path('/items/{id}', '/items/abc', status=200),
                          get_path('/items/{id}', '/items/abc', status=500, name='test_1'))
    assert classes_of(result, '/items/{id}') == {'2XX': True, '4XX/5XX': True}


def test_redirect_covers_no_class(tmp_path):
    result = run_pipeline(tmp_path, get_items('', status=302))
    assert not covered_set(result.criteria, 'output_status_code_class', 'status_code_class')


@pytest.mark.parametrize('status_code_class, status, covers', [
    ('2XX', '200', True), ('2XX', '204', True), ('2XX', '404', False), ('2XX', '500', False),
    ('4XX/5XX', '400', True), ('4XX/5XX', '422', True), ('4XX/5XX', '500', True),
    ('4XX/5XX', '201', False), ('4XX/5XX', '302', False),
])
def test_class_covers(status_code_class, status, covers):
    assert class_covers(status_code_class, status) is covers
