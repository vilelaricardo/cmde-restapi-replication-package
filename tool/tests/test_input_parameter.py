"""Request Parameter Coverage (coverage_criteria/input_parameter.py): header, query
and path parameters and request-body fields."""
import copy

from coverage_criteria import input_parameter
from support import MINI_SPEC, call, elements, generated_test, get_items, get_path, is_covered, post_items, run_pipeline


def covered_parameters(result, **match):
    return {e['parameter'] for e in elements(result.criteria, 'input_parameter', **match) if e['covered']}


class TestRequiredElements:

    def test_query_and_path_parameters(self, mini_criteria):
        found = sorted((e['method'], e['path'], e['parameter'], e['parameter_type'])
                       for e in mini_criteria['input_parameter']['required_elements']
                       if e['parameter_type'] in ('query', 'path'))
        assert found == sorted([
            ('GET', '/items', 'page', 'query'), ('GET', '/items', 'status', 'query'),
            ('GET', '/items', 'flag', 'query'), ('GET', '/items', 'level', 'query'),
            ('GET', '/items/{id}', 'id', 'path'), ('GET', '/items/{id}', 'include', 'query'),
            ('GET', '/items/{id}', 'per_page', 'query'), ('GET', '/types/{kind}', 'kind', 'path')])

    def test_header_parameter(self, mini_criteria):
        assert len(elements(mini_criteria, 'input_parameter', method='GET', path='/items', parameter='X-Trace')) == 1

    def test_request_body_fields(self, mini_criteria):
        # ItemInput is an allOf of two schemas.
        found = {e['parameter'] for e in elements(mini_criteria, 'input_parameter', method='POST', path='/items')}
        assert found == {'name', 'kind', 'active', 'tags'}

    def test_parameters_declared_on_the_path_item(self, tmp_path):
        spec = copy.deepcopy(MINI_SPEC)
        operation = spec['paths']['/items/{id}']['get']
        spec['paths']['/items/{id}']['parameters'] = [operation['parameters'].pop(0)]
        result = run_pipeline(tmp_path, get_path('/items/{id}', '/items/abc'), spec=spec)
        assert is_covered(result.criteria, 'input_parameter', path='/items/{id}', parameter='id')


class TestCoverage:

    def test_query_parameters_sent(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?page=1&status=A'))
        assert covered_parameters(result, path='/items') == {'page', 'status'}

    def test_path_parameter_and_parameter_declared_by_ref(self, tmp_path):
        result = run_pipeline(tmp_path, get_path('/items/{id}', '/items/abc?per_page=5'))
        assert covered_parameters(result, path='/items/{id}') == {'id', 'per_page'}

    def test_query_string_split_across_lines(self, tmp_path):
        test = generated_test('test_0', [(200, 'GET', '/items')], r'''
            headers = {}
            headers['Accept'] = "application/json"
            res_0 = requests \
                    .get(self.baseUrlOfSut + "/items?" +
                        "status=B&" +
                        "flag=false",
                        headers=headers)

            assert res_0.status_code == 200
        ''')
        result = run_pipeline(tmp_path, test)
        assert covered_parameters(result, path='/items') == {'status', 'flag'}

    def test_declared_header_parameter_sent(self, tmp_path):
        test = get_items('?page=1').replace('headers["x-api-key"] = "key"',
                                            'headers["x-api-key"] = "key"\n        headers["X-Trace"] = "t1"')
        result = run_pipeline(tmp_path, test)
        assert is_covered(result.criteria, 'input_parameter', path='/items', parameter='X-Trace')

    def test_request_body_fields_sent(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(
            r'" \"name\": \"n\", " + " \"kind\": \"x\", " + " \"active\": true "'))
        assert covered_parameters(result, method='POST', path='/items') == {'name', 'kind', 'active'}

    def test_query_parameter_sent_empty(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?page=&status=A'))
        assert is_covered(result.criteria, 'input_parameter', path='/items', parameter='page')

    def test_call_using_resolved_location(self, tmp_path):
        test = generated_test('test_0', [(201, 'POST', '/items'), (200, 'GET', '/items/{id}')], r'''
            headers = {}
            headers["content-type"] = "application/json"
            body = {}
            body = " { " + \
                " \"name\": \"n\" " + \
                " } "
            headers['Accept'] = "application/json"
            res_0 = requests \
                    .post(self.baseUrlOfSut + "/items",
                        headers=headers, data=body)
            location_items = "/items" + "/" + str(res_0.json()['id'])

            assert res_0.status_code == 201

            headers = {}
            headers['Accept'] = "application/json"
            res_1 = requests \
                    .get(resolve_location(location_items, self.baseUrlOfSut + str("/items/7?include=true")),
                        headers=headers)

            assert res_1.status_code == 200
        ''')
        result = run_pipeline(tmp_path, test)
        assert covered_parameters(result, path='/items/{id}') == {'id', 'include'}


def test_header_names_are_case_insensitive():
    element = {'path': '/items', 'method': 'GET', 'parameter': 'X-Trace', 'parameter_type': 'header'}
    sent = call('/items', parameters=[{'parameter': 'x-trace', 'value': ['t1'], 'parameter_type': 'header'}])
    assert input_parameter.element_key(element) in input_parameter.covered_keys(sent)


def test_same_name_in_another_location_is_another_parameter():
    element = {'path': '/items', 'method': 'GET', 'parameter': 'page', 'parameter_type': 'query'}
    sent = call('/items', parameters=[{'parameter': 'page', 'value': ['1'], 'parameter_type': 'body'}])
    assert input_parameter.element_key(element) not in input_parameter.covered_keys(sent)
