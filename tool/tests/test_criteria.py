"""Checks each coverage criterion against hand-computed results on MINI_SPEC.

Expected values follow the definitions in the paper (Section 2.1). Tests marked
xfail document a known divergence between those definitions and the current
implementation; they start passing (and strict xfail fails them) once fixed.
"""
import pytest

from support import covered_set, elements, generated_test, is_covered, run_pipeline


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
    """Number of required elements each criterion derives from MINI_SPEC."""

    @pytest.mark.parametrize('criterion, expected', [
        ('input_path', 3),
        ('input_operation', 4),
        pytest.param('input_parameter', 12, marks=pytest.mark.xfail(
            reason='only query and path parameters are extracted; the header parameter and the 4 request-body '
                   'fields are missing (7 instead of 12)')),
        pytest.param('input_parameter_value', 12, marks=pytest.mark.xfail(
            reason='enum/boolean fields of the request body are not extracted (8 instead of 12)')),
        ('output_status_code', 7),
        ('output_status_code_class', 8),
        ('output_response_body_properties', 16),
    ])
    def test_count(self, tmp_path, criterion, expected):
        result = run_pipeline(tmp_path, get_items(''))
        assert len(result.criteria[criterion]['required_elements']) == expected

    def test_operations_outside_target_tags_are_left_out(self, tmp_path):
        result = run_pipeline(tmp_path, get_items(''))
        for criterion, found in result.criteria.items():
            assert not elements(result.criteria, criterion, path='/other'), criterion


class TestPathAndOperationCoverage:

    def test_path_covered_by_any_operation_on_it(self, tmp_path):
        result = run_pipeline(tmp_path, get_items(''), post_items(r'" \"name\": \"n\" "').replace('test_0', 'test_1'))
        assert covered_set(result.criteria, 'input_path', 'path') == {'/items'}
        assert result.criteria['input_path']['coverage'] == pytest.approx(100 / 3)

    def test_operation_requires_matching_method(self, tmp_path):
        result = run_pipeline(tmp_path, get_items(''))
        assert is_covered(result.criteria, 'input_operation', path='/items', method='GET')
        assert not is_covered(result.criteria, 'input_operation', path='/items', method='POST')
        assert result.criteria['input_operation']['coverage'] == pytest.approx(25.0)


class TestRequestParameterCoverage:

    def test_query_parameters_sent_are_covered(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?page=1&status=A'))
        assert is_covered(result.criteria, 'input_parameter', path='/items', parameter='page')
        assert is_covered(result.criteria, 'input_parameter', path='/items', parameter='status')
        assert not is_covered(result.criteria, 'input_parameter', path='/items', parameter='flag')

    def test_path_parameter_and_parameter_declared_by_ref(self, tmp_path):
        result = run_pipeline(tmp_path, get_path('/items/{id}', '/items/abc?per_page=5'))
        assert is_covered(result.criteria, 'input_parameter', path='/items/{id}', parameter='id')
        assert is_covered(result.criteria, 'input_parameter', path='/items/{id}', parameter='per_page')
        assert not is_covered(result.criteria, 'input_parameter', path='/items/{id}', parameter='include')

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
        assert is_covered(result.criteria, 'input_parameter', path='/items', parameter='status')
        assert is_covered(result.criteria, 'input_parameter', path='/items', parameter='flag')

    @pytest.mark.xfail(reason='header parameters declared in the specification are not extracted')
    def test_declared_header_parameter_sent_is_covered(self, tmp_path):
        test = get_items('?page=1').replace('headers["x-api-key"] = "key"',
                                            'headers["x-api-key"] = "key"\n        headers["X-Trace"] = "t1"')
        result = run_pipeline(tmp_path, test)
        assert is_covered(result.criteria, 'input_parameter', path='/items', parameter='X-Trace')

    @pytest.mark.xfail(reason='request-body fields are neither required elements nor read from the tests')
    def test_request_body_fields_sent_are_covered(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(
            r'" \"name\": \"n\", " + " \"kind\": \"x\", " + " \"active\": true "'))
        for field in ('name', 'kind', 'active'):
            assert is_covered(result.criteria, 'input_parameter', path='/items', method='POST', parameter=field)
        assert not is_covered(result.criteria, 'input_parameter', path='/items', method='POST', parameter='tags')

    @pytest.mark.xfail(reason='parse_qs drops parameters sent with an empty value')
    def test_query_parameter_sent_empty_is_covered(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?page=&status=A'))
        assert is_covered(result.criteria, 'input_parameter', path='/items', parameter='page')

    @pytest.mark.xfail(reason='URLs written as resolve_location(..., self.baseUrlOfSut + str("...")) are not '
                              'recovered, so the parameters of the call are lost')
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
        assert is_covered(result.criteria, 'input_parameter', path='/items/{id}', parameter='id')
        assert is_covered(result.criteria, 'input_parameter', path='/items/{id}', parameter='include')


class TestRequestParameterValueCoverage:

    def test_enum_value_sent_in_query_is_covered(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?status=A'))
        assert is_covered(result.criteria, 'input_parameter_value', parameter='status', value='A')
        assert not is_covered(result.criteria, 'input_parameter_value', parameter='status', value='B')

    def test_value_outside_enum_covers_nothing(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?status=EVOMASTER'))
        assert not covered_set(result.criteria, 'input_parameter_value', 'value')

    @pytest.mark.xfail(reason="boolean values are stored as Python True/False but compared with the "
                              "strings 'true'/'false' read from the URL, so they can never be covered")
    def test_boolean_value_sent_in_query_is_covered(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('?flag=true'))
        flag_values = {repr(e['value']): e['covered']
                       for e in elements(result.criteria, 'input_parameter_value', parameter='flag')}
        assert sorted(flag_values.values()) == [False, True], flag_values

    @pytest.mark.xfail(reason='a path parameter value is a string, and the analyser iterates over its '
                              'characters instead of comparing the whole value')
    def test_enum_value_sent_in_path_is_covered(self, tmp_path):
        result = run_pipeline(tmp_path, get_path('/types/{kind}', '/types/alpha'))
        assert is_covered(result.criteria, 'input_parameter_value', parameter='kind', value='alpha')
        assert not is_covered(result.criteria, 'input_parameter_value', parameter='kind', value='beta')

    @pytest.mark.xfail(reason='enum/boolean fields of the request body are not considered')
    def test_enum_and_boolean_values_in_request_body_are_covered(self, tmp_path):
        result = run_pipeline(tmp_path, post_items(r'" \"kind\": \"x\", " + " \"active\": true "'))
        assert is_covered(result.criteria, 'input_parameter_value', parameter='kind', value='x')
        assert not is_covered(result.criteria, 'input_parameter_value', parameter='kind', value='y')


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
        assert is_covered(result.criteria, 'output_status_code_class', path='/items', method='GET', status_code_class='200')
        assert is_covered(result.criteria, 'output_status_code_class', path='/items', method='GET', status_code_class='400')
        assert is_covered(result.criteria, 'output_status_code_class', path='/items', method='POST', status_code_class='200')
        assert not is_covered(result.criteria, 'output_status_code_class', path='/items', method='POST', status_code_class='400')

    def test_server_error_does_not_cover_the_client_error_class(self, tmp_path):
        # Matches the definition currently stated in the paper (2XX and 4XX). Reviewer 1
        # questions it for operations that document 5XX but no 4XX, such as /items/{id}.
        result = run_pipeline(tmp_path, get_path('/items/{id}', '/items/abc', status=500))
        assert not is_covered(result.criteria, 'output_status_code_class', path='/items/{id}', status_code_class='400')

    @pytest.mark.skip(reason='pending decision on how the erroneous class is defined (Reviewer 1); this test '
                             'encodes the option "erroneous = 4XX or 5XX"')
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

    @pytest.mark.xfail(reason='only the asserted path itself is counted; the enclosing properties it proves '
                              'present (data, data.meta) are not')
    def test_parents_of_asserted_nested_property(self, tmp_path):
        result = run_pipeline(tmp_path, get_items('', asserts='assert res_0.json()["data"][0]["meta"]["created"] == "x"'))
        for prop in ('data', 'data.meta'):
            assert is_covered(result.criteria, 'output_response_body_properties',
                              method='GET', path='/items', status_code='200', property=prop)

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
        assert is_covered(result.criteria, 'output_response_body_properties',
                          method='POST', path='/items', status_code='201', property='id')
        assert is_covered(result.criteria, 'output_response_body_properties',
                          method='GET', path='/items', status_code='404', property='message')
        assert not any(e['covered'] for e in elements(result.criteria, 'output_response_body_properties',
                                                      method='GET', path='/items', status_code='200'))

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
