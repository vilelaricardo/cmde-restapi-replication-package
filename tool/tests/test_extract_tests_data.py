"""Reading the generated tests (extract_tests_data.py): each recorded call with its
request, headers, body and the response properties the test reads."""
from extract_tests_data import (extract_body_parameters, extract_header_parameters, extract_properties_from_test,
                                extract_requests)
from support import generated_test, run_pipeline


def body_block(*lines):
    return 'headers = {}\nbody = {}\nbody = ' + ' + \\\n    '.join(lines) + '\nres_0 = requests.post(...)\n'


def test_each_call_is_paired_with_its_request(tmp_path):
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


def test_request_url_inside_str_and_resolve_location():
    block = 'res_1 = requests.get(resolve_location(location_x, self.baseUrlOfSut + str("/items/7?include=true")))'
    assert extract_requests(block) == '/items/7?include=true'


def test_headers_sent():
    block = 'headers = {}\nheaders["x-api-key"] = "k"\nheaders[\'Accept\'] = "application/json"\n'
    assert extract_header_parameters(block) == [
        {'parameter': 'x-api-key', 'value': ['k'], 'parameter_type': 'header'},
        {'parameter': 'Accept', 'value': ['application/json'], 'parameter_type': 'header'}]


def test_body_fields_of_a_list_of_objects_are_merged():
    block = body_block(r'" [ "', r'" { \"a\": 1, \"b\": {\"c\": true} }, "', r'" { \"a\": 2, \"d\": [1, 2] } "', r'" ] "')
    fields = {p['parameter']: p['value'] for p in extract_body_parameters(block)}
    assert fields == {'a': ['1', '2'], 'b': [], 'b.c': ['true'], 'd': ['1', '2']}


def test_empty_list_body_has_no_fields():
    assert extract_body_parameters(body_block(r'" [] "')) == []


def test_body_that_is_not_valid_json_has_no_fields():
    # EvoMaster sometimes writes escapes such as "Arag\ão"; the API cannot parse them either.
    assert extract_body_parameters(body_block(r'" { \"nome\": \"Arag\\ão\" } "')) == []


def test_reading_a_nested_property_shows_its_parents_are_present():
    assert extract_properties_from_test('assert res_0.json()["data"][0]["meta"]["created"] == "x"') == [
        'data', 'data.meta', 'data.meta.created']
