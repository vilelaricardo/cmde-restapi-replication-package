"""Status Code Class Coverage (SCCC): each operation should produce a correct (2XX)
and an erroneous (4XX or 5XX) response, whatever classes the operation documents."""

NEEDS_RESOLVED_SPEC = False

STATUS_CODE_CLASSES = ['2XX', '4XX/5XX']


def class_covers(status_code_class, status):
    # '2XX' is covered by any 2xx status, '4XX/5XX' by any 4xx or 5xx status.
    return status[:1] in {cls[0] for cls in status_code_class.split('/')}


def required_elements(operation):
    return [
        {'path': operation.path, 'method': operation.method, 'status_code_class': status_code_class}
        for status_code_class in STATUS_CODE_CLASSES
    ]


def element_key(element):
    return (element['path'], element['method'], element['status_code_class'])


def covered_keys(call):
    return {
        (call['path'], call['method'], status_code_class)
        for status_code_class in STATUS_CODE_CLASSES
        if class_covers(status_code_class, call['status'])
    }
