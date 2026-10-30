"""Request Parameter Coverage (RPC): proportion of the input parameters, in headers,
body, query or path, used in at least one request.

Request-body fields count as parameters, with dotted names for nested fields and
array items under the array's name."""
from coverage_criteria.common import call_parameters, operation_inputs, parameter_name

NEEDS_RESOLVED_SPEC = True


def required_elements(operation):
    return [
        {'path': operation.path, 'method': operation.method, 'parameter': name, 'parameter_type': location}
        for name, location, _ in operation_inputs(operation)
    ]


def element_key(element):
    return (element['path'], element['method'], element['parameter_type'],
            parameter_name(element['parameter'], element['parameter_type']))


def covered_keys(call):
    return {
        (call['path'], call['method'], param['parameter_type'], parameter_name(param['parameter'], param['parameter_type']))
        for param in call_parameters(call)
    }
