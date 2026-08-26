from prance import ResolvingParser
from helpers import save_json, fetch_swagger, is_integer


def create_criteria():
    return {
        "coverage": 0.0,
        "required_elements": []
    }


def extract_properties(schema, prefix=""):
    properties = set()

    if "properties" in schema:
        for key, value in schema["properties"].items():
            prop_name = f"{prefix}.{key}" if prefix else key
            properties.add(prop_name)

            if value.get("type") == "object":
                properties.update(extract_properties(value, prop_name))
            elif value.get("type") == "array" and "items" in value:
                properties.update(extract_properties(value["items"], prop_name))

    elif schema.get("type") == "array" and "items" in schema:
        properties.update(extract_properties(schema["items"], prefix))

    for key in ["oneOf", "anyOf", "allOf"]:
        if key in schema:
            for sub_schema in schema[key]:
                properties.update(extract_properties(sub_schema, prefix))

    return properties


def filter_endpoints(specification, target_tags, directory):
    allowed_status_code_classes = ['200', '400']
    
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
    
    for path, methods in specification.get('paths', {}).items():
        for method, details in methods.items():
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
                
                for status_code_class in allowed_status_code_classes:
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
                
                if was_resolved and 'parameters' in details:
                    for parameter in details['parameters']:
                        param_info = {
                            'path': path,
                            'method': method.upper(),
                            'parameter': parameter['name'],
                            'parameter_type': parameter['in'],
                            'covered': False
                        }

                        if parameter['in'] in {'query', 'path'}:
                            criteria['input_parameter']['required_elements'].append(param_info.copy())

                        schema = parameter.get('schema', {})

                        if 'enum' in schema:
                            criteria['input_parameter_value']['required_elements'].extend([
                                {**param_info, 'value': enum, 'value_type': 'enum'} for enum in schema['enum']
                            ])

                        if schema.get('type') == 'boolean':
                            criteria['input_parameter_value']['required_elements'].extend([
                                {**param_info, 'value': value, 'value_type': 'boolean'} for value in [True, False]
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
