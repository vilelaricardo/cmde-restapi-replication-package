from helpers import load_json, save_json
from coverage_criteria import CRITERIA
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


def recorded_calls(extracted_test_data):
    for tests in extracted_test_data.values():
        for test in tests.values():
            yield from test['paths']


def run_criteria_analyzer(main_directory, specific_directory):
    extracted_test_data = load_json(f'{specific_directory}/extracted_test_data.json')
    calls = list(recorded_calls(extracted_test_data))

    for name, criterion in CRITERIA.items():
        file_path = f'{main_directory}/criteria/{name}.json'
        if not os.path.exists(file_path):
            continue

        criteria = load_json(file_path)
        covered = set()
        for call in calls:
            covered.update(criterion.covered_keys(call))

        for element in criteria['required_elements']:
            element['covered'] = criterion.element_key(element) in covered

        criteria['coverage'] = calculate_coverage(criteria)
        save_json(criteria, f'{specific_directory}/criteria_analyzed/{name}.json')
