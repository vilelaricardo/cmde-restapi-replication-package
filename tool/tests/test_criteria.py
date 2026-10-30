"""Checks each coverage criterion against hand-computed results on MINI_SPEC.

Expected values follow the definitions in the paper (Section 2.1). A test marked
xfail documents one known divergence between those definitions and the current
implementation, and only the exception that divergence raises is accepted; once the
divergence is fixed the test passes and strict xfail turns that into a failure.
"""
import copy

import pytest

from support import (MINI_SPEC, as_text, covered_set, elements, generated_test, is_covered, run_pipeline,
                     value_coverage)


def known_defect(reason, raises=AssertionError):
    return pytest.mark.xfail(reason=reason, raises=raises)


def get_items(query, status=200, asserts=''):
    return generated_test('test_0', [(status, 'GET', '/items')], fr'''
        headers = {{}}
        headers["x-api-key"] = "key"
        headers['Accept'] = "application/json"
        res_0 = requests \
                .get(self.baseUrlOfSut + "/items{query}",
                    headers=headers)

        assert res_0.status_code == {status}
        {asserts}
    ''')


def post_items(body, status=201, asserts=''):
    return generated_test('test_0', [(status, 'POST', '/items')], fr'''
        headers = {{}}
        headers["x-api-key"] = "key"
        headers["content-type"] = "application/json"
        body = {{}}
        body = " {{ " + \
            {body} + \
            " }} "
        headers['Accept'] = "application/json"
        res_0 = requests \
                .post(self.baseUrlOfSut + "/items",
                    headers=headers, data=body)

        assert res_0.status_code == {status}
        {asserts}
    ''')


def get_path(template, url, status=200, name='test_0'):
    return generated_test(name, [(status, 'GET', template)], fr'''
        headers = {{}}
        headers["x-api-key"] = "key"
        headers['Accept'] = "application/json"
        res_0 = requests \
                .get(self.baseUrlOfSut + "{url}",
                    headers=headers)

        assert res_0.status_code == {status}
    ''')


class TestRequiredElements:
    """Exact set of required elements each criterion derives from MINI_SPEC."""

    @pytest.fixture(scope='class')
    def criteria(self, tmp_path_factory):
        return run_pipeline(tmp_path_factory.mktemp('required'), get_items('')).criteria

    def test_paths(self, criteria):
        assert {e['path'] for e in criteria['input_path']['required_elements']} == {
            '/items', '/items/{id}', '/types/{kind}'}
        assert len(criteria['input_path']['required_elements']) == 3

    def test_operations(self, criteria):
        assert sorted((e['method'], e['path']) for e in criteria['input_operation']['required_elements']) == sorted([
            ('GET', '/items'), ('POST', '/items'), ('GET', '/items/{id}'), ('GET', '/types/{kind}')])

    def test_query_and_path_parameters(self, criteria):
        found = sorted((e['method'], e['path'], e['parameter'], e['parameter_type'])
                       for e in criteria['input_parameter']['required_elements']
                       if e['parameter_type'] in ('query', 'path'))
        assert found == sorted([
            ('GET', '/items', 'page', 'query'), ('GET', '/items', 'status', 'query'),
            ('GET', '/items', 'flag', 'query'), ('GET', '/items', 'level', 'query'),
            ('GET', '/items/{id}', 'id', 'path'), ('GET', '/items/{id}', 'include', 'query'),
            ('GET', '/items/{id}', 'per_page', 'query'), ('GET', '/types/{kind}', 'kind', 'path')])

    @known_defect('header parameters declared in the specification are not extracted')
    def test_header_parameter(self, criteria):
        assert len(elements(criteria, 'input_parameter', method='GET', path='/items', parameter='X-Trace')) == 1

    @known_defect('request-body fields are not extracted as parameters')
    def test_request_body_fields(self, criteria):
        found = {e['parameter'] for e in elements(criteria, 'input_parameter', method='POST', path='/items')}
        assert found == {'name', 'kind', 'active', 'tags'}

    def test_query_and_path_values(self, criteria):
        found = sorted((e['method'], e['path'], e['parameter'], as_text(e['value']))
                       for e in criteria['input_parameter_value']['required_elements']
                       if e['parameter_type'] in ('query', 'path'))
        assert found == sorted([
            ('GET', '/items', 'status', 'A'), ('GET', '/items', 'status', 'B'),
            ('GET', '/items', 'flag', 'true'), ('GET', '/items', 'flag', 'false'),
            ('GET', '/items', 'level', '1'), ('GET', '/items', 'level', '2'),
            ('GET', '/items/{id}', 'include', 'true'), ('GET', '/items/{id}', 'include', 'false'),
            ('GET', '/types/{kind}', 'kind', 'alpha'), ('GET', '/types/{kind}', 'kind', 'beta')])

    @known_defect('enum/boolean fields of the request body are not extracted')
    def test_request_body_values(self, criteria):
        found = {(e['parameter'], as_text(e['value']))
                 for e in elements(criteria, 'input_parameter_value', method='POST', path='/items')}
        assert found == {('kind', 'x'), ('kind', 'y'), ('active', 'true'), ('active', 'false')}

    def test_status_codes(self, criteria):
        assert sorted((e['method'], e['path'], e['status_code'])
                      for e in criteria['output_status_code']['required_elements']) == sorted([
            ('GET', '/items', '200'), ('GET', '/items', '404'), ('POST', '/items', '201'), ('POST', '/items', '422'),
            ('GET', '/items/{id}', '200'), ('GET', '/items/{id}', '500'), ('GET', '/types/{kind}', '200')])

    def test_status_code_classes(self, criteria):
        # Definition currently stated in the paper: one 2XX and one 4XX target per operation.
        assert sorted((e['method'], e['path'], e['status_code_class'])
                      for e in criteria['output_status_code_class']['required_elements']) == sorted(
            (method, path, cls)
            for method, path in [('GET', '/items'), ('POST', '/items'), ('GET', '/items/{id}'), ('GET', '/types/{kind}')]
            for cls in ('200', '400'))

    def test_response_body_properties(self, criteria):
        found = sorted((e['method'], e['path'], e['status_code'], e['property'])
                       for e in criteria['output_response_body_properties']['required_elements'])
        expected = (
            [('GET', '/items', '200', p) for p in ('data', 'data.id', 'data.name', 'data.meta', 'data.meta.created', 'total')]
            + [('GET', '/items', '404', 'message'), ('POST', '/items', '201', 'id')]
            + [('POST', '/items', '422', p) for p in ('message', 'errors', 'errors.field')]
            + [('GET', '/items/{id}', '200', p) for p in ('id', 'name', 'meta', 'meta.created')]
            + [('GET', '/items/{id}', '500', 'message')])
        assert found == sorted(expected)

    def test_operations_outside_target_tags_are_left_out(self, criteria):
        for criterion in criteria:
            assert not elements(criteria, criterion, path='/other'), criterion

    @known_defect('a "parameters" list declared on the path item is taken for an HTTP method',
                  raises=AttributeError)
    def test_parameters_declared_on_the_path_item(self, tmp_path):
        spec = copy.deepcopy(MINI_SPEC)
        operation = spec['paths']['/items/{id}']['get']
        spec['paths']['/items/{id}']['parameters'] = [operation['parameters'].pop(0)]
        result = run_pipeline(tmp_path, get_path('/items/{id}', '/items/abc'), spec=spec)
        assert is_covered(result.criteria, 'input_parameter', path='/items/{id}', parameter='id')


class TestPathAndOperationCoverage:

    def test_path_covered_by_any_operation_on_it(self, tmp_path):
        result = run_pipeline(tmp_path, get_items(''), post_items(r'" \"name\": \"n\" "').replace('test_0', 'test_1'))
        assert covered_set(result.criteria, 'input_path', 'path') == {'/items'}
        assert result.criteria['input_path']['coverage'] == pytest.approx(100 / 3)

    def test_operation_requires_matching_method(self, tmp_path):
        result = run_pipeline(tmp_path, get_items(''))
        assert {(e['method'], e['path']) for e in result.criteria['input_operation']['required_elements']
                if e['covered']} == {('GET', '/items')}
        assert result.criteria['input_operation']['coverage'] == pytest.approx(25.0)


class TestRequestParameterCoverage:

    def test_query_parameters_sent_are_covered(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?page=1&status=A'))
        assert {e['parameter'] for e in elements(result.criteria, 'input_parameter', path='/items')
                if e['covered']} == {'page', 'status'}

    def test_path_parameter_and_parameter_declared_by_ref(self, tmp_path):
        result = run_pipeline(tmp_path, get_path('/items/{id}', '/items/abc?per_page=5'))
        assert {e['parameter'] for e in elements(result.criteria, 'input_parameter', path='/items/{id}')
                if e['covered']} == {'id', 'per_page'}

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
        assert {e['parameter'] for e in elements(result.criteria, 'input_parameter', path='/items')
                if e['covered']} == {'status', 'flag'}

    @known_defect('header parameters declared in the specification are not extracted')
    def test_declared_header_parameter_sent_is_covered(self, tmp_path):
        test = get_items('?page=1').replace('headers["x-api-key"] = "key"',
                                            'headers["x-api-key"] = "key"\n        headers["X-Trace"] = "t1"')
        result = run_pipeline(tmp_path, test)
        assert is_covered(result.criteria, 'input_parameter', path='/items', parameter='X-Trace')

    @known_defect('request-body fields are neither required elements nor read from the tests')
    def test_request_body_fields_sent_are_covered(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(
            r'" \"name\": \"n\", " + " \"kind\": \"x\", " + " \"active\": true "'))
        assert {e['parameter'] for e in elements(result.criteria, 'input_parameter', method='POST', path='/items')
                if e['covered']} == {'name', 'kind', 'active'}

    @known_defect('parse_qs drops parameters sent with an empty value')
    def test_query_parameter_sent_empty_is_covered(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?page=&status=A'))
        assert is_covered(result.criteria, 'input_parameter', path='/items', parameter='page')

    @known_defect('URLs written as resolve_location(..., self.baseUrlOfSut + str("...")) are not recovered, '
                  'so the parameters of the call are lost')
    def test_parameters_of_call_using_resolved_location(self, tmp_path):
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
        assert {e['parameter'] for e in elements(result.criteria, 'input_parameter', path='/items/{id}')
                if e['covered']} == {'id', 'include'}


class TestRequestParameterValueCoverage:

    def test_enum_value_sent_in_query_is_covered(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?status=A'))
        assert value_coverage(result.criteria, path='/items', parameter='status') == {'A': True, 'B': False}

    def test_value_outside_enum_covers_nothing(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?status=EVOMASTER'))
        assert not covered_set(result.criteria, 'input_parameter_value', 'value')

    @pytest.mark.parametrize('sent, not_sent', [('true', 'false'), ('false', 'true')])
    @known_defect("boolean values are stored as Python True/False but compared with the strings "
                  "'true'/'false' read from the URL, so they can never be covered")
    def test_boolean_value_sent_in_query_is_covered(self, tmp_path, sent, not_sent):
        result = run_pipeline(tmp_path, get_items(f'?flag={sent}'))
        assert value_coverage(result.criteria, path='/items', parameter='flag') == {sent: True, not_sent: False}

    @known_defect('numeric enum values are stored as integers but compared with the strings read from the URL')
    def test_numeric_enum_value_sent_in_query_is_covered(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?level=1'))
        assert value_coverage(result.criteria, path='/items', parameter='level') == {'1': True, '2': False}

    @known_defect('a path parameter value is a string, and the analyser iterates over its characters '
                  'instead of comparing the whole value')
    def test_enum_value_sent_in_path_is_covered(self, tmp_path):
        result = run_pipeline(tmp_path, get_path('/types/{kind}', '/types/alpha'))
        assert value_coverage(result.criteria, path='/types/{kind}', parameter='kind') == {'alpha': True, 'beta': False}

    @known_defect('enum fields of the request body are not considered')
    def test_enum_value_in_request_body_is_covered(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(r'" \"kind\": \"x\" "'))
        assert value_coverage(result.criteria, method='POST', path='/items', parameter='kind') == {'x': True, 'y': False}

    @known_defect('boolean fields of the request body are not considered')
    def test_boolean_value_in_request_body_is_covered(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(r'" \"active\": false "'))
        assert value_coverage(result.criteria, method='POST', path='/items', parameter='active') == {
            'false': True, 'true': False}


class TestStatusCodeCoverage:

    def test_documented_status_codes_obtained_are_covered(self, tmp_path):
        result = run_pipeline(tmp_path,
                              get_items('', status=200),
                              get_items('', status=404).replace('test_0', 'test_1'),
                              post_items(r'" \"name\": \"n\" "').replace('test_0', 'test_2'))
        covered = {(e['method'], e['path'], e['status_code'])
                   for e in result.criteria['output_status_code']['required_elements'] if e['covered']}
        assert covered == {('GET', '/items', '200'), ('GET', '/items', '404'), ('POST', '/items', '201')}
        assert result.criteria['output_status_code']['coverage'] == pytest.approx(300 / 7)

    def test_undocumented_status_code_covers_nothing(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(r'" \"name\": \"n\" "', status=400))
        assert result.criteria['output_status_code']['coverage'] == 0.0


class TestStatusCodeClassCoverage:

    def test_success_and_client_error_classes(self, tmp_path):
        result = run_pipeline(tmp_path,
                              get_items('', status=200),
                              get_items('', status=404).replace('test_0', 'test_1'),
                              post_items(r'" \"name\": \"n\" "').replace('test_0', 'test_2'))
        covered = {(e['method'], e['path'], e['status_code_class'])
                   for e in result.criteria['output_status_code_class']['required_elements'] if e['covered']}
        assert covered == {('GET', '/items', '200'), ('GET', '/items', '400'), ('POST', '/items', '200')}

    def test_server_error_does_not_cover_the_client_error_class(self, tmp_path):
        # Matches the definition currently stated in the paper (2XX and 4XX). Reviewer 1
        # questions it for operations that document 5XX but no 4XX, such as /items/{id}.
        result = run_pipeline(tmp_path, get_path('/items/{id}', '/items/abc', status=500))
        assert not covered_set(result.criteria, 'output_status_code_class', 'status_code_class')

    @pytest.mark.skip(reason='pending decision on how the erroneous class is defined (Reviewer 1); once settled, '
                             'this test must list the exact classes required and covered for /items/{id}')
    def test_operation_documenting_only_5xx_errors_can_reach_full_coverage(self, tmp_path):
        result = run_pipeline(tmp_path,
                              get_path('/items/{id}', '/items/abc', status=200),
                              get_path('/items/{id}', '/items/abc', status=500, name='test_1'))
        classes = elements(result.criteria, 'output_status_code_class', path='/items/{id}')
        assert classes and all(e['covered'] for e in classes)


class TestResponseBodyPropertiesCoverage:
    """In the current implementation a property counts as covered when a generated
    test asserts on it; the paper describes properties present in the responses."""

    def test_asserted_properties_including_nested_ones(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('', asserts='\n        '.join([
            'assert res_0.json()["total"] == 1',
            'assert res_0.json()["data"][0]["id"] == 3',
            'assert res_0.json()["data"][0]["meta"]["created"] == "2025-05-03"',
        ])))
        covered = {e['property'] for e in elements(result.criteria, 'output_response_body_properties',
                                                   method='GET', path='/items', status_code='200') if e['covered']}
        assert {'total', 'data.id', 'data.meta.created'} <= covered
        assert 'data.name' not in covered

    @known_defect('only the asserted path itself is counted; the enclosing properties it proves present '
                  '(data, data.meta) are not')
    def test_parents_of_asserted_nested_property(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('', asserts='assert res_0.json()["data"][0]["meta"]["created"] == "x"'))
        covered = {e['property'] for e in elements(result.criteria, 'output_response_body_properties',
                                                   method='GET', path='/items', status_code='200') if e['covered']}
        assert covered == {'data', 'data.meta', 'data.meta.created'}

    def test_properties_attributed_to_the_call_that_returned_them(self, tmp_path):
        test = generated_test('test_0', [(201, 'POST', '/items'), (404, 'GET', '/items')], r'''
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

            assert res_0.status_code == 201
            assert res_0.json()["id"] == 10

            headers = {}
            headers['Accept'] = "application/json"
            res_1 = requests \
                    .get(self.baseUrlOfSut + "/items",
                        headers=headers)

            assert res_1.status_code == 404
            assert res_1.json()["message"] == "not found"
        ''')
        result = run_pipeline(tmp_path, test)
        covered = {(e['method'], e['path'], e['status_code'], e['property'])
                   for e in result.criteria['output_response_body_properties']['required_elements'] if e['covered']}
        assert covered == {('POST', '/items', '201', 'id'), ('GET', '/items', '404', 'message')}

    def test_properties_inside_array_items(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(r'" \"name\": 1 "', status=422,
                                                   asserts='assert res_0.json()["errors"][0]["field"] == "name"'))
        assert is_covered(result.criteria, 'output_response_body_properties',
                          method='POST', path='/items', status_code='422', property='errors.field')

    def test_properties_of_undocumented_status_code_cover_nothing(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(r'" \"name\": 1 "', status=400,
                                                   asserts='assert res_0.json()["message"] == "bad"'))
        assert result.criteria['output_response_body_properties']['coverage'] == 0.0


class TestTestParsing:

    def test_each_call_is_paired_with_its_request(self, tmp_path):
        test = generated_test('test_0', [(200, 'GET', '/items'), (200, 'GET', '/items/{id}')], r'''
            headers = {}
            res_0 = requests \
                    .get(self.baseUrlOfSut + "/items?page=2",
                        headers=headers)

            assert res_0.status_code == 200

            headers = {}
            res_1 = requests \
                    .get(self.baseUrlOfSut + "/items/9",
                        headers=headers)

            assert res_1.status_code == 200
        ''')
        result = run_pipeline(tmp_path, test)
        calls = result.extracted['EvoMaster_successes_Test.py']['test_0']['paths']
        assert [(c['path'], c['request']) for c in calls] == [('/items', '/items?page=2'), ('/items/{id}', '/items/9')]
