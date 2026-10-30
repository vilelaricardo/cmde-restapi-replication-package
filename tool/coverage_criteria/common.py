HTTP_METHODS = {'get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace'}

PARAMETER_LOCATIONS = {'query', 'path', 'header'}


class Operation:
    """One operation of the specification: a path and one of its HTTP methods."""

    def __init__(self, path, method, details, path_item):
        self.path = path
        self.method = method.upper()
        self.details = details
        self.path_item = path_item


def property_schemas(schema, prefix=""):
    # Dotted property names (array items share the name of the array) mapped to their schemas.
    properties = {}

    if "properties" in schema:
        for key, value in schema["properties"].items():
            prop_name = f"{prefix}.{key}" if prefix else key
            properties[prop_name] = value

            if value.get("type") == "object":
                properties.update(property_schemas(value, prop_name))
            elif value.get("type") == "array" and "items" in value:
                properties.update(property_schemas(value["items"], prop_name))

    elif schema.get("type") == "array" and "items" in schema:
        properties.update(property_schemas(schema["items"], prefix))

    for key in ["oneOf", "anyOf", "allOf"]:
        if key in schema:
            for sub_schema in schema[key]:
                properties.update(property_schemas(sub_schema, prefix))

    return properties


def operation_parameters(operation):
    # Parameters declared on the path item apply to every operation, unless the
    # operation redeclares one with the same name and location.
    parameters = {(p['name'], p['in']): p for p in operation.path_item.get('parameters', [])}
    parameters.update({(p['name'], p['in']): p for p in operation.details.get('parameters', [])})
    return list(parameters.values())


def request_body_fields(operation):
    content = operation.details.get('requestBody', {}).get('content', {})
    if 'application/json' not in content:
        return {}
    return property_schemas(content['application/json'].get('schema', {}))


def operation_inputs(operation):
    """(name, location, schema) of every input of the operation: header, query and
    path parameters, and request-body fields (location 'body')."""
    inputs = [(p['name'], p['in'], p.get('schema', {}))
              for p in operation_parameters(operation) if p['in'] in PARAMETER_LOCATIONS]
    inputs += [(field, 'body', schema) for field, schema in request_body_fields(operation).items()]
    return inputs


def parameter_name(name, location):
    # HTTP header names are case-insensitive.
    return name.lower() if location == 'header' else name


def call_parameters(call):
    return call.get('parameters') or []
