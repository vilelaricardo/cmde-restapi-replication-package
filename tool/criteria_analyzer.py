from helpers import load_json, save_json
import os

def calculate_coverage(criteria):
    num_test_criteria_covered = 0
    
    if(criteria['required_elements']):
        for required_element in criteria['required_elements']:
            if required_element['covered']:
                num_test_criteria_covered += 1
    else:
        return 0.0
            
    return (num_test_criteria_covered / len(criteria['required_elements'])) * 100.0

def run_criteria_analyzer(main_directory, specific_directory):
    extracted_test_data = load_json(f'{specific_directory}/extracted_test_data.json')
    
    criteria_files = {
        'input_path': 'input_path.json',
        'input_operation': 'input_operation.json',
        'output_status_code_class': 'output_status_code_class.json',
        'output_status_code': 'output_status_code.json',
        'input_parameter': 'input_parameter.json',
        'input_parameter_value': 'input_parameter_value.json',
        'output_response_body_properties': 'output_response_body_properties.json'
    }
    
    criteria = {}

    for name, file in criteria_files.items():
        file_path = f'{main_directory}/criteria/{file}'
        if os.path.exists(file_path):
            criteria[name] = load_json(file_path)

    for file in extracted_test_data:
        for test in extracted_test_data[file]:
            for path in extracted_test_data[file][test]['paths']:
                path_info = path['path']
                method = path['method']
                status = path['status']
                     
                # Input Path Coverage Analysis
                if 'input_path' in criteria:
                    for index, element in enumerate(criteria['input_path']['required_elements']):
                        if element['path'] == path_info:
                            criteria['input_path']['required_elements'][index]['covered'] = True
                            break
                
                # Input Operation Coverage Analysis
                if 'input_operation' in criteria:
                    for index, element in enumerate(criteria['input_operation']['required_elements']):
                        if element['path'] == path_info and element['method'] == method:
                            criteria['input_operation']['required_elements'][index]['covered'] = True
                            break
                
                # Output Status Code Class Analysis
                if 'output_status_code_class' in criteria:
                    for index, element in enumerate(criteria['output_status_code_class']['required_elements']):
                        if (element['path'] == path_info and 
                            element['method'] == method and 
                            element['status_code_class'][0] == status[0]
                        ):
                            criteria['output_status_code_class']['required_elements'][index]['covered'] = True
                            break
                
                # Output Status Code Analysis
                if 'output_status_code' in criteria:
                    for index, element in enumerate(criteria['output_status_code']['required_elements']):
                        if (
                            element['path'] == path_info and 
                            element['method'] == method and 
                            element['status_code'] == status
                        ):
                            criteria['output_status_code']['required_elements'][index]['covered'] = True
                            break
                
                # Input Parameter and Input Parameter Value Analysis
                if 'input_parameter' in criteria and 'input_parameter_value' in criteria and 'parameters' in path:
                    for param in path['parameters']:
                        for index, element in enumerate(criteria['input_parameter']['required_elements']):
                            if (
                                element['path'] == path_info and 
                                element['method'] == method and 
                                element['parameter'] == param['parameter'] and 
                                element['parameter_type'] == param['parameter_type']
                            ):
                                criteria['input_parameter']['required_elements'][index]['covered'] = True
                                break
                        
                        for value in param['value']:
                            for index, element in enumerate(criteria['input_parameter_value']['required_elements']):
                                if (
                                    element['path'] == path_info and 
                                    element['method'] == method and 
                                    element['parameter'] == param['parameter'] and 
                                    element['parameter_type'] == param['parameter_type'] and 
                                    element['value'] == value
                                ):
                                    criteria['input_parameter_value']['required_elements'][index]['covered'] = True
                                    break
                
                # Output Response Body Properties Analysis (novo)
                if 'output_response_body_properties' in criteria and 'properties' in path:
                    for property in path['properties']:
                        for index, element in enumerate(criteria['output_response_body_properties']['required_elements']):
                            if (
                                element['path'] == path_info and 
                                element['method'] == method and 
                                element['status_code'] == status and 
                                element['property'] == property
                            ):
                                criteria['output_response_body_properties']['required_elements'][index]['covered'] = True
                                break
    
    for name in criteria:
        criteria[name]['coverage'] = calculate_coverage(criteria[name])
        save_json(criteria[name], f'{specific_directory}/criteria_analyzed/{name}.json')