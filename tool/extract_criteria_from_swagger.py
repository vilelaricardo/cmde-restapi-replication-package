from prance import ResolvingParser
from helpers import save_json, fetch_swagger, is_integer, as_text

HTTP_METHODS = {'get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace'}

# One correct and one erroneous class per operation; the erroneous class is
# covered by a 4XX or a 5XX response.
STATUS_CODE_CLASSES = ['2XX', '4XX/5XX']

PARAMETER_LOCATIONS = {'query', 'path', 'header'}


def create_criteria():
    return {
        "coverage": 0.0,
        "required_elements": []
    }


def extract_property_schemas(schema, prefix=""):
    # Dotted property names (array items share the name of the array) mapped to their schemas.
    properties = {}

    if "properties" in schema:
        for key, value in schema["properties"].items():
            prop_name = f"{prefix}.{key}" if prefix else key
            properties[prop_name] = value

            if value.get("type") == "object":
                properties.update(extract_property_schemas(value, prop_name))
            elif value.get("type") == "array" and "items" in value:
                properties.update(extract_property_schemas(value["items"], prop_name))

    elif schema.get("type") == "array" and "items" in schema:
        properties.update(extract_property_schemas(schema["items"], prefix))

    for key in ["oneOf", "anyOf", "allOf"]:
        if key in schema:
            for sub_schema in schema[key]:
                properties.update(extract_property_schemas(sub_schema, prefix))

    return properties


def extract_properties(schema, prefix=""):
    return set(extract_property_schemas(schema, prefix))


def possible_values(schema):
    if 'enum' in schema:
        return [(as_text(value), 'enum') for value in schema['enum']]
    if schema.get('type') == 'boolean':
        return [('true', 'boolean'), ('false', 'boolean')]
    return []


def operation_parameters(path_item, details):
    # Parameters declared on the path item apply to every operation, unless the
    # operation redeclares one with the same name and location.
    parameters = {(p['name'], p['in']): p for p in path_item.get('parameters', [])}
    parameters.update({(p['name'], p['in']): p for p in details.get('parameters', [])})
    return list(parameters.values())


def request_body_fields(details):
    content = details.get('requestBody', {}).get('content', {})
    if 'application/json' not in content:
        return {}
    return extract_property_schemas(content['application/json'].get('schema', {}))


def filter_endpoints(specification, target_tags, directory):
    
    criteria = {
        "input_path": create_criteria(),
        "input_operation": create_criteria(),
        "input_parameter": create_criteria(),
        "input_parameter_value": create_criteria(),
        "output_status_code": create_criteria(),
        "output_status_code_class": create_criteria(),
        "output_response_body_properties": create_criteria(),
    }
    
    seen_paths = set()
    was_resolved = False
    
    try:
        parser = ResolvingParser(f"{directory}/api-docs.json")
        specification = parser.specification 
        was_resolved = True
    except Exception as e:
        print('Alert: Unable to generate criteria for Input Parameter Coverage, Input Parameter Value Coverage, and Output Response Body Properties Coverage due to errors in the Swagger specification.')
    
    for path, path_item in specification.get('paths', {}).items():
        for method, details in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue

            current_tags = details.get('tags', [])
            
            if not target_tags or any(tag in target_tags for tag in current_tags):
                if path not in seen_paths:
                    criteria['input_path']['required_elements'].append({
                        'path': path,
                        'covered': False
                    })
                    seen_paths.add(path)
                
                criteria['input_operation']['required_elements'].append({
                    'path': path,
                    'method': method.upper(),
                    'covered': False
                })
                
                for status_code_class in STATUS_CODE_CLASSES:
                    criteria['output_status_code_class']['required_elements'].append(
                        {
                            'path': path,
                            'method': method.upper(),
                            'status_code_class': status_code_class,
                            'covered': False
                        }
                    ) 
                
                for status_code, response in details.get("responses", {}).items():
                    if is_integer(status_code):
                        criteria['output_status_code']['required_elements'].append({
                            'path': path,
                            'method': method.upper(),
                            'status_code': status_code,
                            'covered': False
                        })

                        content = response.get('content')
                        if isinstance(content, dict) and 'application/json' in content:
                            properties = extract_properties(content['application/json']['schema'])
                            for property in properties:
                                criteria['output_response_body_properties']['required_elements'].append({
                                    'path': path,
                                    'method': method.upper(),
                                    'status_code': status_code,
                                    'property': property,
                                    'covered': False
                                })
                
                if was_resolved:
                    inputs = [(p['name'], p['in'], p.get('schema', {}))
                              for p in operation_parameters(path_item, details) if p['in'] in PARAMETER_LOCATIONS]
                    inputs += [(field, 'body', schema) for field, schema in request_body_fields(details).items()]

                    for name, location, schema in inputs:
                        param_info = {
                            'path': path,
                            'method': method.upper(),
                            'parameter': name,
                            'parameter_type': location,
                            'covered': False
                        }

                        criteria['input_parameter']['required_elements'].append(param_info.copy())
                        criteria['input_parameter_value']['required_elements'].extend([
                            {**param_info, 'value': value, 'value_type': value_type}
                            for value, value_type in possible_values(schema)
                        ])

    for key, value in criteria.items():
        if was_resolved or key in {"input_path", "input_operation", "output_status_code", "output_status_code_class"}:
            save_json(value, f"{directory}/criteria/{key}.json")


def run_extract_criteria_from_swagger(experiment_directory, experiment_data):
    swagger_data = fetch_swagger(experiment_data['swagger_url'])
    
    if not swagger_data: exit(1)

    json_path = f"{experiment_directory}/api-docs.json"
    save_json(swagger_data, json_path)

    filter_endpoints(swagger_data, experiment_data['target_tags'], experiment_directory)
