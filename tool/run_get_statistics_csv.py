import csv
import argparse
from pathlib import Path
from helpers import load_json


CRITERIA_FILES = {
    'input_path': 'input_path.json',
    'input_operation': 'input_operation.json',
    'input_parameter': 'input_parameter.json',
    'input_parameter_value': 'input_parameter_value.json',
    'output_status_code_class': 'output_status_code_class.json',
    'output_status_code': 'output_status_code.json',
    'output_response_body_properties': 'output_response_body_properties.json'
}


CRITERIA_COVERAGE_KEYS = [f'{key}_coverage' for key in CRITERIA_FILES]


def get_num_tests(path):
    num_tests = 0
    extracted_test_data = load_json(f'{path}/extracted_test_data.json')
    
    for test_file in extracted_test_data:
        num_tests += len(list(extracted_test_data[test_file].keys()))
    
    return num_tests
    

def generate_statistics_csv(base_directory, experiment_name):
    try:
        experiment_path = f'{base_directory}/data_generated/{experiment_name}'

        setup_experiment_data = load_json(f'{experiment_path}/experiment_data.json')
        number_of_repetitions = setup_experiment_data['number_of_repetitions']
        algorithms = setup_experiment_data['algorithms']
        
        statistics_csv = [
            [
                "algorithm", 
                "repetition", 
                "num_tests"
            ],
        ]
        
        statistics_csv[0].extend(CRITERIA_COVERAGE_KEYS)
    
        for repetition in range(0, number_of_repetitions):
            for algorithm in algorithms:
                algorithm_path = f'{experiment_path}/repetition_{repetition}/{algorithm}'
                
                criteria = {}

                for name, file in CRITERIA_FILES.items():
                    path = Path(f'{algorithm_path}/criteria_analyzed/{file}')
                    if path.exists():
                        criteria[name] = load_json(path)['coverage']
                    else:
                        criteria[name] = None
                
                coverage_values = []
                for criteria_coverage_value in criteria:
                    coverage_values.append(criteria[criteria_coverage_value])
                
                num_tests = get_num_tests(algorithm_path)
                
                statistics_csv.append([
                    algorithm,
                    repetition,
                    num_tests
                ] + coverage_values)

        csv_path = Path(base_directory) / f'statistics/{experiment_name}.csv'
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        with csv_path.open('w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerows(statistics_csv)
            
    except Exception as e:
        print(f'Error saving Statistics CSV: {e}')
        
        
if __name__ == "__main__":
    base_directory = Path(__file__).resolve().parent
    
    parser = argparse.ArgumentParser(description="Generate a CSV file with statistics for a specific experiment.")
    parser.add_argument('-n', '--name', type=str, required=True, help='Name of the experiment folder')
    
    args = parser.parse_args()
    experiment_name = args.name
    
    generate_statistics_csv(base_directory, experiment_name)