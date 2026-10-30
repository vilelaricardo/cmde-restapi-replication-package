"""Status Code Coverage (SCC): proportion of the status codes documented for each
operation that are obtained in at least one response."""
from helpers import is_integer

NEEDS_RESOLVED_SPEC = False


def required_elements(operation):
    return [
        {'path': operation.path, 'method': operation.method, 'status_code': status_code}
        for status_code in operation.details.get('responses', {})
        if is_integer(status_code)
    ]


def element_key(element):
    return (element['path'], element['method'], element['status_code'])


def covered_keys(call):
    return {(call['path'], call['method'], call['status'])}
