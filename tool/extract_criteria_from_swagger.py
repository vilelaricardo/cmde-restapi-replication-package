from prance import ResolvingParser
from helpers import save_json, fetch_swagger
from coverage_criteria import CRITERIA
from coverage_criteria.common import HTTP_METHODS, Operation


def create_criteria():
    return {
        "coverage": 0.0,
        "required_elements": []
    }


def target_operations(specification, target_tags):
    for path, path_item in specification.get('paths', {}).items():
        for method, details in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue

            current_tags = details.get('tags', [])
            if not target_tags or any(tag in target_tags for tag in current_tags):
                yield Operation(path, method, details, path_item)


def filter_endpoints(specification, target_tags, directory):
    was_resolved = False

    try:
        parser = ResolvingParser(f"{directory}/api-docs.json")
        specification = parser.specification
        was_resolved = True
    except Exception as e:
        print('Alert: Unable to generate criteria for Input Parameter Coverage, Input Parameter Value Coverage, and Output Response Body Properties Coverage due to errors in the Swagger specification.')

    criteria = {
        name: create_criteria()
        for name, criterion in CRITERIA.items()
        if was_resolved or not criterion.NEEDS_RESOLVED_SPEC
    }

    for operation in target_operations(specification, target_tags):
        for name, criterion in criteria.items():
            for element in CRITERIA[name].required_elements(operation):
                element = {**element, 'covered': False}
                # An element is required once, e.g. a path shared by several operations.
                if element not in criterion['required_elements']:
                    criterion['required_elements'].append(element)

    for name, criterion in criteria.items():
        save_json(criterion, f"{directory}/criteria/{name}.json")


def run_extract_criteria_from_swagger(experiment_directory, experiment_data):
    swagger_data = fetch_swagger(experiment_data['swagger_url'])

    if not swagger_data: exit(1)

    json_path = f"{experiment_directory}/api-docs.json"
    save_json(swagger_data, json_path)

    filter_endpoints(swagger_data, experiment_data['target_tags'], experiment_directory)
