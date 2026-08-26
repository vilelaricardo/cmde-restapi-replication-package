import yaml
import json
import requests
from pathlib import Path
from exceptions import SwaggerUrlNotFoundError
from datetime import datetime

def load_json(json_path) -> dict:
    try:
        with open(json_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f'JSON file not found: {json_path}')
        return None
    except json.JSONDecodeError as e:
        print(f'Error reading the JSON file: {e}')
        return None


def save_json(data, json_path):
    try:
        json_path = Path(json_path)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with json_path.open("w", encoding="utf-8") as out_f:
            json.dump(data, out_f, indent=2)
    except Exception as e:
        print(f'Error saving JSON: {e}')


def save_log_txt(log_message, log_path):
    try:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {log_message}\n"
        
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(log_entry)
            
    except Exception as e:
        print(f"Error saving log {log_path}: {e}")


def load_yaml(yaml_path):
    try:
        with open(yaml_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f'YAML file not found: {yaml_path}')
        return None
    except yaml.YAMLError as e:
        print(f'Error reading the YAML file: {e}')
        return None
    
    
def fetch_swagger(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        content_type = response.headers.get('Content-Type', '').lower()
        
        # Se for JSON, retorna diretamente
        if 'application/json' in content_type:
            return response.json()
        # Se for YAML, converte para JSON
        elif 'application/yaml' in content_type or 'application/x-yaml' in content_type or 'text/yaml' in content_type:
            yaml_content = yaml.safe_load(response.text)
            return yaml_content
        # Se não for nenhum dos tipos conhecidos, tenta interpretar como JSON ou YAML
        else:
            try:
                return response.json()
            except ValueError:
                try:
                    return yaml.safe_load(response.text)
                except yaml.YAMLError:
                    raise ValueError("O conteúdo retornado não é um JSON ou YAML válido")
                    
    except requests.exceptions.RequestException as err:
        print(f'HTTP request error: {err}')
        return None
    except (ValueError, yaml.YAMLError) as err:
        print(f'Error parsing content: {err}')
        return None
    

def extract_experiment_data(base_directory):
    target_tags = []
    yaml_data = load_yaml(f'{base_directory}/configs/em.yaml')
    experiment_data = load_json(f'{base_directory}/configs/setup_experiment.json')
    
    if not yaml_data or not experiment_data: return None

    max_time = yaml_data.get('configs', {}).get('maxTime')
    swagger_url = yaml_data.get('configs', {}).get('bbSwaggerUrl')
    endpoint_tag_filter = yaml_data.get('configs', {}).get('endpointTagFilter')
    
    if endpoint_tag_filter: target_tags = [tag.strip() for tag in endpoint_tag_filter.split(",")]

    if not swagger_url:
        raise SwaggerUrlNotFoundError("bbSwaggerUrl not found in the YAML file.")
    
    experiment_data.update(
        {
            'swagger_url': swagger_url,
            'max_time': max_time,
            'target_tags': target_tags
        }
    )
    
    return experiment_data


def is_integer(s):
    try:
        int(s)  
        return True
    except ValueError:
        return False
