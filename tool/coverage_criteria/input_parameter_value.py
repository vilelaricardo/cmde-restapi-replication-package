"""Request Parameter Value Coverage (RPVC): proportion of the possible values of the
enum and boolean inputs (the same inputs as Request Parameter Coverage) sent in at
least one request.

Values are compared as they travel in HTTP, so 1 and "1", or True and "true", are
the same value."""
from helpers import as_text
from coverage_criteria.common import call_parameters, operation_inputs, parameter_name

NEEDS_RESOLVED_SPEC = True


def possible_values(schema):
    if 'enum' in schema:
        return [(as_text(value), 'enum') for value in schema['enum']]
    if schema.get('type') == 'boolean':
        return [('true', 'boolean'), ('false', 'boolean')]
    return []


def required_elements(operation):
    return [
        {'path': operation.path, 'method': operation.method, 'parameter': name, 'parameter_type': location,
         'value': value, 'value_type': value_type}
        for name, location, schema in operation_inputs(operation)
        for value, value_type in possible_values(schema)
    ]


def element_key(element):
    return (element['path'], element['method'], element['parameter_type'],
            parameter_name(element['parameter'], element['parameter_type']), as_text(element['value']))


def covered_keys(call):
    keys = set()
    for param in call_parameters(call):
        values = param['value'] if isinstance(param['value'], list) else [param['value']]
        name = parameter_name(param['parameter'], param['parameter_type'])
        keys.update((call['path'], call['method'], param['parameter_type'], name, as_text(value)) for value in values)
    return keys
