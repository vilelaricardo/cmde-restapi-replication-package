"""Response Body Properties Coverage (coverage_criteria/output_response_body_properties.py).

A property counts as covered when a generated test reads it from the response,
together with the enclosing properties that reading proves present. The tests record
only what they assert on, so this is a lower bound of the properties the responses
actually contained."""
from coverage_criteria import output_response_body_properties
from support import call, elements, generated_test, get_items, is_covered, post_items, run_pipeline


def covered_properties(result, **match):
    return {e['property'] for e in elements(result.criteria, 'output_response_body_properties', **match)
            if e['covered']}


def test_required_properties(mini_criteria):
    found = sorted((e['method'], e['path'], e['status_code'], e['property'])
                   for e in mini_criteria['output_response_body_properties']['required_elements'])
    expected = (
        [('GET', '/items', '200', p) for p in ('data', 'data.id', 'data.name', 'data.meta', 'data.meta.created', 'total')]
        + [('GET', '/items', '404', 'message'), ('POST', '/items', '201', 'id')]
        + [('POST', '/items', '422', p) for p in ('message', 'errors', 'errors.field')]
        + [('GET', '/items/{id}', '200', p) for p in ('id', 'name', 'meta', 'meta.created')]
        + [('GET', '/items/{id}', '500', 'message')])
    assert found == sorted(expected)


def test_asserted_properties_including_nested_ones(tmp_path):
    result = run_pipeline(tmp_path, get_items('', asserts='\n        '.join([
        'assert res_0.json()["total"] == 1',
        'assert res_0.json()["data"][0]["id"] == 3',
        'assert res_0.json()["data"][0]["meta"]["created"] == "2025-05-03"',
    ])))
    covered = covered_properties(result, method='GET', path='/items', status_code='200')
    assert {'total', 'data.id', 'data.meta.created'} <= covered
    assert 'data.name' not in covered


def test_parents_of_asserted_nested_property(tmp_path):
    result = run_pipeline(tmp_path, get_items('', asserts='assert res_0.json()["data"][0]["meta"]["created"] == "x"'))
    assert covered_properties(result, method='GET', path='/items', status_code='200') == {
        'data', 'data.meta', 'data.meta.created'}


def test_properties_attributed_to_the_call_that_returned_them(tmp_path):
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


def test_properties_inside_array_items(tmp_path):
    result = run_pipeline(tmp_path, post_items(r'" \"name\": 1 "', status=422,
                                               asserts='assert res_0.json()["errors"][0]["field"] == "name"'))
    assert is_covered(result.criteria, 'output_response_body_properties',
                      method='POST', path='/items', status_code='422', property='errors.field')


def test_properties_of_undocumented_status_code_cover_nothing(tmp_path):
    result = run_pipeline(tmp_path, post_items(r'" \"name\": 1 "', status=400,
                                               asserts='assert res_0.json()["message"] == "bad"'))
    assert result.criteria['output_response_body_properties']['coverage'] == 0.0


def test_property_is_tied_to_the_status_code():
    element = {'path': '/items', 'method': 'GET', 'status_code': '200', 'property': 'message'}
    read_on_404 = call('/items', status='404', properties=['message'])
    assert output_response_body_properties.element_key(element) not in \
        output_response_body_properties.covered_keys(read_on_404)
