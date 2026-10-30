"""Coverage criteria of Martín-López et al. (2019) used in the study, one module per
criterion. Each module defines:

  NEEDS_RESOLVED_SPEC    whether its required elements need the specification's $refs resolved
  required_elements(op)  the elements one operation of the specification requires
  element_key(element)   what identifies a required element
  covered_keys(call)     the elements a call recorded in a generated test covers

extract_criteria_from_swagger builds the required elements and criteria_analyzer
marks the covered ones; neither knows the criteria beyond this interface.
"""
from coverage_criteria import (
    input_operation,
    input_parameter,
    input_parameter_value,
    input_path,
    output_response_body_properties,
    output_status_code,
    output_status_code_class,
)

# In the order of the columns of the statistics CSV.
CRITERIA = {
    'input_path': input_path,
    'input_operation': input_operation,
    'input_parameter': input_parameter,
    'input_parameter_value': input_parameter_value,
    'output_status_code_class': output_status_code_class,
    'output_status_code': output_status_code,
    'output_response_body_properties': output_response_body_properties,
}
