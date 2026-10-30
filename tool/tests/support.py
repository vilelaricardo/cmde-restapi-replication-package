import json
import textwrap
from types import SimpleNamespace

import coverage_criteria
from extract_criteria_from_swagger import filter_endpoints
from extract_tests_data import run_extract_test_data
from criteria_analyzer import run_criteria_analyzer

CRITERIA = list(coverage_criteria.CRITERIA)

TARGET_TAG = 'Items'


def json_content(schema_ref):
    return {'application/json': {'schema': {'$ref': f'#/components/schemas/{schema_ref}'}}}


# Small OpenAPI 3 specification whose required elements can be listed by hand.
# Under the definitions given in the paper (Section 2.1) it has:
#   paths 3, operations 4, parameters 13 (6 query, 2 path, 1 header, 4 body fields),
#   enum/boolean values 14 (10 in query/path, 4 in the body), status codes 7,
#   status code classes 8 (2 per operation), response body properties 16.
# /other is tagged differently and must be left out by the tag filter.
MINI_SPEC = {
    'openapi': '3.0.0',
    'info': {'title': 'mini', 'version': '1.0.0'},
    'servers': [{'url': 'http://localhost:8000'}],
    'paths': {
        '/items': {
            'get': {
                'tags': [TARGET_TAG],
                'parameters': [
                    {'name': 'page', 'in': 'query', 'schema': {'type': 'integer'}},
                    {'name': 'status', 'in': 'query', 'schema': {'type': 'string', 'enum': ['A', 'B']}},
                    {'name': 'flag', 'in': 'query', 'schema': {'type': 'boolean'}},
                    {'name': 'level', 'in': 'query', 'schema': {'type': 'integer', 'enum': [1, 2]}},
                    {'name': 'X-Trace', 'in': 'header', 'schema': {'type': 'string'}},
                ],
                'responses': {
                    '200': {'description': 'ok', 'content': json_content('ItemList')},
                    '404': {'description': 'not found', 'content': json_content('Error')},
                },
            },
            'post': {
                'tags': [TARGET_TAG],
                'requestBody': {'content': json_content('ItemInput')},
                'responses': {
                    '201': {'description': 'created', 'content': json_content('Created')},
                    '422': {'description': 'invalid', 'content': json_content('ValidationError')},
                },
            },
        },
        '/items/{id}': {
            'get': {
                'tags': [TARGET_TAG],
                'parameters': [
                    {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'string'}},
                    {'name': 'include', 'in': 'query', 'schema': {'type': 'boolean'}},
                    {'$ref': '#/components/parameters/PerPage'},
                ],
                'responses': {
                    '200': {'description': 'ok', 'content': json_content('ItemOut')},
                    '500': {'description': 'error', 'content': json_content('Error')},
                },
            },
        },
        '/types/{kind}': {
            'get': {
                'tags': [TARGET_TAG],
                'parameters': [
                    {'name': 'kind', 'in': 'path', 'required': True,
                     'schema': {'type': 'string', 'enum': ['alpha', 'beta']}},
                ],
                'responses': {'200': {'description': 'ok'}},
            },
        },
        '/other': {
            'get': {
                'tags': ['Other'],
                'parameters': [{'name': 'q', 'in': 'query', 'schema': {'type': 'string'}}],
                'responses': {'200': {'description': 'ok'}},
            },
        },
    },
    'components': {
        'parameters': {
            'PerPage': {'name': 'per_page', 'in': 'query', 'schema': {'type': 'integer'}},
        },
        'schemas': {
            'Error': {'type': 'object', 'properties': {'message': {'type': 'string'}}},
            'Created': {'type': 'object', 'properties': {'id': {'type': 'integer'}}},
            'ItemOut': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'name': {'type': 'string'},
                    'meta': {'type': 'object', 'properties': {'created': {'type': 'string'}}},
                },
            },
            'ItemList': {
                'type': 'object',
                'properties': {
                    'data': {'type': 'array', 'items': {'$ref': '#/components/schemas/ItemOut'}},
                    'total': {'type': 'integer'},
                },
            },
            'ItemInput': {
                'type': 'object',
                'allOf': [{'$ref': '#/components/schemas/Base'}, {'$ref': '#/components/schemas/Extra'}],
            },
            'Base': {
                'type': 'object',
                'properties': {'name': {'type': 'string'}, 'kind': {'type': 'string', 'enum': ['x', 'y']}},
            },
            'Extra': {
                'type': 'object',
                'properties': {'active': {'type': 'boolean'}, 'tags': {'type': 'array', 'items': {'type': 'string'}}},
            },
            'ValidationError': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'errors': {
                        'type': 'array',
                        'items': {'type': 'object', 'properties': {'field': {'type': 'string'}}},
                    },
                },
            },
        },
    },
}


def generated_test(name, calls, code):
    """One test method as EvoMaster writes it: the '# Calls:' header listing
    (status, METHOD, path template) for each request, then the method body."""
    if len(calls) == 1:
        status, method, path = calls[0]
        comments = [f'    # ({status}) {method}:{path}']
    else:
        comments = [f'    # {i} - ({status}) {method}:{path}' for i, (status, method, path) in enumerate(calls, 1)]
    body = textwrap.indent(textwrap.dedent(code).strip('\n'), ' ' * 8)
    return '\n'.join(['    # Calls:', *comments, '    @timeout_decorator.timeout(60)',
                      f'    def {name}(self):', '        ', body, ''])


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


def call(path, method='GET', status='200', parameters=(), properties=()):
    """A call as extract_tests_data records it, for testing a criterion module directly."""
    return {'path': path, 'method': method, 'status': status,
            'parameters': list(parameters), 'properties': list(properties)}


def evomaster_file(*tests, class_name='EvoMaster_successes_Test'):
    """Wraps test methods in the layout of a Python test file written by EvoMaster 3.4.0."""
    header = (
        '#!/usr/bin/env python\n\n'
        'import json\nimport unittest\nimport requests\nimport timeout_decorator\n'
        'from em_test_utils import *\n\n\n'
        f'class {class_name}(unittest.TestCase):\n\n    \n'
        '    baseUrlOfSut = "http://localhost:8000"\n    \n    \n'
    )
    footer = "\n\nif __name__ == '__main__':\n    unittest.main()\n"
    return header + '\n'.join(tests) + footer


def run_pipeline(tmp_path, *tests, spec=MINI_SPEC, target_tags=(TARGET_TAG,)):
    """Runs criteria extraction, test parsing and analysis exactly as main.py does.
    Returns the analysed criteria keyed by name and the data extracted from the tests."""
    main_dir = tmp_path / 'experiment'
    run_dir = main_dir / 'repetition_0' / 'TECHNIQUE'
    (run_dir / 'generated_tests').mkdir(parents=True)
    (main_dir / 'api-docs.json').write_text(json.dumps(spec))
    (run_dir / 'generated_tests' / 'EvoMaster_successes_Test.py').write_text(evomaster_file(*tests))

    filter_endpoints(spec, list(target_tags), str(main_dir))
    run_extract_test_data(str(run_dir), ['EvoMaster_successes_Test.py'], str(main_dir))
    run_criteria_analyzer(str(main_dir), str(run_dir))

    criteria = {
        name: json.loads((run_dir / 'criteria_analyzed' / f'{name}.json').read_text())
        for name in CRITERIA
        if (run_dir / 'criteria_analyzed' / f'{name}.json').exists()
    }
    extracted = json.loads((run_dir / 'extracted_test_data.json').read_text())
    return SimpleNamespace(criteria=criteria, extracted=extracted)


def elements(result, criterion, **match):
    return [
        element for element in result[criterion]['required_elements']
        if all(element.get(key) == value for key, value in match.items())
    ]


def is_covered(result, criterion, **match):
    found = elements(result, criterion, **match)
    assert len(found) == 1, f'{criterion}: expected one required element matching {match}, found {len(found)}'
    return found[0]['covered']


def covered_set(result, criterion, key):
    return {element[key] for element in result[criterion]['required_elements'] if element['covered']}


def as_text(value):
    """Spec values may be stored as Python True/1 or as the strings sent in a URL."""
    return str(value).lower() if isinstance(value, bool) else str(value)


def value_coverage(result, **match):
    """{value as text: covered} for the Request Parameter Value Coverage elements matching `match`."""
    return {as_text(e['value']): e['covered'] for e in elements(result, 'input_parameter_value', **match)}
