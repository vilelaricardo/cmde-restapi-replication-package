import re
from helpers import save_json, load_json
from urllib.parse import urlparse, parse_qs


def extract_parameters(path, request):
    if isinstance(path, bytes):
        print(path)
        path = path.decode('utf-8')
    if isinstance(request, bytes):
        print(request)
        request = request.decode('utf-8')
    
    parsed_url = urlparse(request)
    url_path = parsed_url.path
    if isinstance(url_path, bytes):
        url_path = url_path.decode('utf-8')
    
    path_params = re.findall(r"\{(\w+)\}", path)
    path_regex = re.sub(r"\{(\w+)\}", r"([^/]+)", path)
    
    path_match = re.match(path_regex, url_path)
    path_values = path_match.groups() if path_match else []
    
    path_params_dict = dict(zip(path_params, path_values))

    query_string = parsed_url.query
    if isinstance(query_string, bytes):
        query_string = query_string.decode('utf-8')
    query_params = parse_qs(query_string)
    
    parameters = {"parameters": []}
    
    for path_param in path_params_dict:
        parameters["parameters"].append({
            "parameter": path_param,
            "value": path_params_dict[path_param],
            "parameter_type": "path"
        })
        
    for query_param in query_params:
        parameters["parameters"].append({
            "parameter": query_param,
            "value": query_params[query_param],
            "parameter_type": "query"
        })

    return parameters


def extract_properties_from_test(test_code_str):
    properties = set()
    
    pattern = r'(?:res_\d+|response|req_\d+)\.json\(\)((?:\[["\'][^"\']+["\']\]|\[\d+\]|\.\w+)+)'
    
    for match in re.finditer(pattern, test_code_str):
        path = match.group(1)
        path = re.sub(r'\[\d+\]', '', path)
        path = re.sub(r'\[["\']([^"\']+)["\']\]', r'.\1', path)
        path = path.strip('.')
        
        if path:
            properties.add(path)
    
    return sorted(properties)


def extract_requests(block):
    baseurl_pattern = re.compile(r'self\.baseUrlOfSut\s*\+\s*(?:(?:"[^"]*")|(?:\w+))(?:(?:\s*\+\s*(?:"[^"]*"|\w+))*)')
    
    resolve_pattern = re.compile(r'resolve_location\([^,]+,\s*(self\.baseUrlOfSut\s*\+.+?)\)')

    match = baseurl_pattern.search(block)
    if not match:
        match = resolve_pattern.search(block)

    if not match:
        return None

    expression = match.group(0)

    expression = re.sub(r'self\.baseUrlOfSut\s*\+\s*', '', expression)
    
    parts = re.findall(r'"([^"]+)"', expression)
    
    full_path = ''.join(parts)
    return full_path if full_path else None


def extract_def_name(block):
    def_name = None
    pattern = re.compile(r'def\s+(\w+)\s*\(')
    groups = pattern.search(block)
    
    if(groups):
        def_name = groups.group(1)

    return def_name


def extract_function_lines(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    full_function_lines = [] 
    current_block = []   
    create_block = False
    base_url = ''

    for line in lines:
        if line.strip().startswith("baseUrlOfSut"):
            regex = r'baseUrlOfSut\s*=\s*"([^"]+)"'
            match = re.search(regex, line.strip())
            base_url = match.group(1)
            
        if line.strip().startswith("# Calls:"):
            create_block = True
            if current_block:
                full_function_lines.append(current_block)
                current_block = []

        if create_block:
            current_block.append(line)

    if current_block:
        full_function_lines.append(current_block)
    
    return { 'base_url': base_url, 'lines': full_function_lines }


def extract_request_lines_blocks(lines):
    blocks = []
    request_block = []
    create_request_block = False

    for line in lines:
        if line.strip().startswith("headers = {}"):
            create_request_block = True
            if request_block:
                block = "".join(request_block).strip()
                blocks.append(block)
                request_block = []

        if create_request_block:
            request_block.append(line)

    if request_block:
        block = "".join(request_block).strip()
        blocks.append(block)

    return blocks


def normalize_path(path, base_path):
    if base_path and path.startswith(base_path):
        return path[len(base_path):] or "/"
    return path


def extract_calls(block, base_path):
    matches = re.findall(r'#(?: \d+ -)? \((\w+)\) (\w+):([/\w{}.-]+)', block)

    paths = [{
        "status": status, 
        "method": method, 
        "path": normalize_path(path.strip(), base_path), 
        "request": None, 
        "properties": None,
    } for status, method, path in matches]

    return paths
    

def extract_base_path(servers, base_url):
    if base_url:
        parsed_base = urlparse(base_url)
        if parsed_base.path:
            return parsed_base.path

    for server in servers:
        url = server.get("url", "").strip()
        if url:
            parsed_url = urlparse(url)
            if parsed_url.path:
                return parsed_url.path
    
    return "" 


def run_extract_test_data(experiment_directory, test_file_names, specification_directory):
    all_extracted_data = {}
    extracted_data = {}

    for test_file in test_file_names:
        path = f'{experiment_directory}/generated_tests/{test_file}'
        extracted_lines = extract_function_lines(path)
        line_blocks = extracted_lines['lines']
        base_url = extracted_lines['base_url']
        specification = load_json(f'{specification_directory}/api-docs.json')
        servers = specification.get('servers', [])
        base_path = extract_base_path(servers, base_url)

        for line_block in line_blocks:
            block = "".join(line_block).strip()
            def_name = extract_def_name(block)
            paths = extract_calls(block, base_path)
            
            extracted_data[def_name] = {
                'paths': paths,
            }
            request_blocks_lines = extract_request_lines_blocks(line_block)

            for index, request_block_line in enumerate(request_blocks_lines):
                request = extract_requests(request_block_line)
                normalized_request = normalize_path(request, base_path)
                extracted_data[def_name]['paths'][index]['request'] = normalized_request
                extracted_data[def_name]['paths'][index]['properties'] = extract_properties_from_test(request_block_line)
                parameters = extract_parameters(extracted_data[def_name]['paths'][index]['path'], normalized_request)
                extracted_data[def_name]['paths'][index].update(parameters)
        
        all_extracted_data[test_file] = extracted_data
        extracted_data = {}

    save_json(all_extracted_data, f'{experiment_directory}/extracted_test_data.json')