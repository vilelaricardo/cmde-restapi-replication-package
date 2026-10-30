"""Request Parameter Value Coverage (coverage_criteria/input_parameter_value.py):
enum and boolean values of the inputs, compared as they travel in HTTP."""
import pytest

from coverage_criteria import input_parameter_value
from support import as_text, covered_set, elements, get_items, get_path, post_items, run_pipeline, value_coverage


class TestRequiredElements:

    def test_query_and_path_values(self, mini_criteria):
        found = sorted((e['method'], e['path'], e['parameter'], as_text(e['value']))
                       for e in mini_criteria['input_parameter_value']['required_elements']
                       if e['parameter_type'] in ('query', 'path'))
        assert found == sorted([
            ('GET', '/items', 'status', 'A'), ('GET', '/items', 'status', 'B'),
            ('GET', '/items', 'flag', 'true'), ('GET', '/items', 'flag', 'false'),
            ('GET', '/items', 'level', '1'), ('GET', '/items', 'level', '2'),
            ('GET', '/items/{id}', 'include', 'true'), ('GET', '/items/{id}', 'include', 'false'),
            ('GET', '/types/{kind}', 'kind', 'alpha'), ('GET', '/types/{kind}', 'kind', 'beta')])

    def test_request_body_values(self, mini_criteria):
        found = {(e['parameter'], as_text(e['value']))
                 for e in elements(mini_criteria, 'input_parameter_value', method='POST', path='/items')}
        assert found == {('kind', 'x'), ('kind', 'y'), ('active', 'true'), ('active', 'false')}


class TestCoverage:

    def test_enum_value_sent_in_query(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?status=A'))
        assert value_coverage(result.criteria, path='/items', parameter='status') == {'A': True, 'B': False}

    def test_value_outside_enum_covers_nothing(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?status=EVOMASTER'))
        assert not covered_set(result.criteria, 'input_parameter_value', 'value')

    @pytest.mark.parametrize('sent, not_sent', [('true', 'false'), ('false', 'true')])
    def test_boolean_value_sent_in_query(self, tmp_path, sent, not_sent):
        result = run_pipeline(tmp_path, get_items(f'?flag={sent}'))
        assert value_coverage(result.criteria, path='/items', parameter='flag') == {sent: True, not_sent: False}

    def test_numeric_enum_value_sent_in_query(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?level=1'))
        assert value_coverage(result.criteria, path='/items', parameter='level') == {'1': True, '2': False}

    def test_enum_value_sent_in_path(self, tmp_path):
        result = run_pipeline(tmp_path, get_path('/types/{kind}', '/types/alpha'))
        assert value_coverage(result.criteria, path='/types/{kind}', parameter='kind') == {'alpha': True, 'beta': False}

    def test_enum_value_in_request_body(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(r'" \"kind\": \"x\" "'))
        assert value_coverage(result.criteria, method='POST', path='/items', parameter='kind') == {'x': True, 'y': False}

    def test_boolean_value_in_request_body(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(r'" \"active\": false "'))
        assert value_coverage(result.criteria, method='POST', path='/items', parameter='active') == {
            'false': True, 'true': False}


@pytest.mark.parametrize('schema, values', [
    ({'type': 'string', 'enum': ['A', 'B']}, [('A', 'enum'), ('B', 'enum')]),
    ({'type': 'integer', 'enum': [1, 2]}, [('1', 'enum'), ('2', 'enum')]),
    # The CMDE request bodies declare integer enums with string values, e.g. genero.
    ({'type': 'integer', 'enum': ['0', '1']}, [('0', 'enum'), ('1', 'enum')]),
    ({'type': 'boolean'}, [('true', 'boolean'), ('false', 'boolean')]),
    ({'type': 'string'}, []),
])
def test_possible_values(schema, values):
    assert input_parameter_value.possible_values(schema) == values


def test_json_number_sent_in_body_matches_enum_declared_as_string():
    element = {'path': '/p', 'method': 'POST', 'parameter': 'genero', 'parameter_type': 'body', 'value': '3'}
    sent = {'path': '/p', 'method': 'POST', 'status': '201',
            'parameters': [{'parameter': 'genero', 'value': ['3'], 'parameter_type': 'body'}]}
    assert input_parameter_value.element_key(element) in input_parameter_value.covered_keys(sent)
