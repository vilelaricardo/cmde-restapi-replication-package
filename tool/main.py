import traceback
import subprocess
from pathlib import Path
from datetime import datetime
from extract_tests_data import run_extract_test_data
from helpers import extract_experiment_data, save_json, save_log_txt
from extract_criteria_from_swagger import run_extract_criteria_from_swagger
from criteria_analyzer import run_criteria_analyzer

evo_master_path = Path(__file__).resolve().parent
result_path = f'data_generated/experiment-{datetime.now().strftime("date-%d-%m-%y-time-%H-%M-%S-%f")[:-3]}'

Path(result_path).mkdir(parents=True, exist_ok=True)

experiment_data = extract_experiment_data(evo_master_path)
if not experiment_data: exit(1)
json_experiment_directory = f"{result_path}/experiment_data.json"
save_json(experiment_data, json_experiment_directory)

if experiment_data:
  run_extract_criteria_from_swagger(result_path, experiment_data)
  
  for repetition in range(experiment_data['number_of_repetitions']):
    try:
      for algorithm in experiment_data['algorithms']:
        current_path = f'{result_path}/repetition_{repetition}/{algorithm}'

        command = f'''
          java -jar evomaster.jar --algorithm {algorithm} \
          --outputFolder {current_path}/generated_tests \
          --coveredTargetFile {current_path}/covered_targets.txt \
          --statisticsFile {result_path}/statistics.csv \
          --configPath {evo_master_path}/configs/em.yaml
        '''

        result = subprocess.run(
          command, 
          capture_output=True, 
          text=True,
          cwd=evo_master_path,  
          shell=True
        )

        with open(f'{current_path}/execution_output.txt', "w") as out_f:
          out_f.write(result.stdout)

        if result.stderr:
          with open(f'{current_path}/execution_error.txt', "w") as err_f:
              err_f.write(result.stderr)
        
        folder = Path(f'{current_path}/generated_tests')
        filtered_files = [
            file.name for file in folder.iterdir()
            if file.is_file() and file.name.startswith("EvoMaster") and file.name.endswith("Test.py")
        ]
        
        run_extract_test_data(current_path, filtered_files, result_path)
        run_criteria_analyzer(result_path, current_path)
        
    except Exception as e:
      print(f'Error: An error occurred in repetition {repetition} and algorithm {algorithm}. More details in {result_path}/logs')
      error_details = traceback.format_exc()  
      save_log_txt(error_details, f'{result_path}/logs/error_rep_{repetition}_algorithm_{algorithm}.txt')
      continue