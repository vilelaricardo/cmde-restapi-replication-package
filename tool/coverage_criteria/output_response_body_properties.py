"""Response Body Properties Coverage (RBPC): proportion of the properties declared in
the JSON response schema of each documented status code that are present in at
least one response.

A property counts when a generated test reads it from a response with that status
code; reading a.b.c also shows that a and a.b are present (see
extract_tests_data.extract_properties_from_test). The tests record only what they
assert on, so this is a lower bound of the properties the responses contained."""
from helpers import is_integer
from coverage_criteria.common import property_schemas

NEEDS_RESOLVED_SPEC = True


def required_elements(operation):
    elements = []
    for status_code, response in operation.details.get('responses', {}).items():
        content = response.get('content')
        if is_integer(status_code) and isinstance(content, dict) and 'application/json' in content:
            elements += [
                {'path': operation.path, 'method': operation.method, 'status_code': status_code, 'property': prop}
                for prop in property_schemas(content['application/json']['schema'])
            ]
    return elements


def element_key(element):
    return (element['path'], element['method'], element['status_code'], element['property'])


def covered_keys(call):
    return {(call['path'], call['method'], call['status'], prop) for prop in call.get('properties') or []}
