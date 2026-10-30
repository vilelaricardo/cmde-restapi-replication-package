"""Path Coverage (PC): proportion of the paths declared in the specification that
are exercised by at least one request."""

NEEDS_RESOLVED_SPEC = False


def required_elements(operation):
    return [{'path': operation.path}]


def element_key(element):
    return element['path']


def covered_keys(call):
    return {call['path']}
