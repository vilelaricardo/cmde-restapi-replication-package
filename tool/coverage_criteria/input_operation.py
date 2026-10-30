"""Operation Coverage (OC): proportion of the operations (path and HTTP method)
declared in the specification that are exercised by at least one request."""

NEEDS_RESOLVED_SPEC = False


def required_elements(operation):
    return [{'path': operation.path, 'method': operation.method}]


def element_key(element):
    return (element['path'], element['method'])


def covered_keys(call):
    return {(call['path'], call['method'])}
