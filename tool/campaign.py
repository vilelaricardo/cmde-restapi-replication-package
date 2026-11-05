"""Runs an experiment campaign described by a campaign file (configs/campaign-*.json).

The campaign is a sequence of blocks. Each block executes every technique once, in an
order drawn from the campaign seed, so stopping after any block leaves all techniques
with the same number of repetitions. Each execution gets its own EvoMaster seed and
starts from a freshly reset environment:

  1. EvoMaster search;
  2. the API logs of that search (nginx, Laravel, queue worker) are saved;
  3. the generated suite is executed twice, each time on a freshly reset environment and
     with its HTTP traffic recorded (http_capture/capture.py): as generated, and without
     assertions (python -O), so that a test whose assertion no longer holds on the reset
     environment still makes all its requests;
  4. the coverage criteria of the generated tests are computed.

The plan is saved before the first execution. Running the same command again resumes
the campaign: finished executions are skipped and an unfinished one is moved to
incomplete/ and started over. A file named STOP in the campaign directory ends the
campaign before the next block.

The output follows the layout of main.py (repetition_<block>/<technique>), so
run_get_statistics_csv.py reads it unchanged.

    python campaign.py --config configs/campaign-6.2.0.json --output data_generated/campaign-6.2.0
"""
import argparse
import gzip
import hashlib
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from datetime import datetime
from pathlib import Path

import requests

from criteria_analyzer import run_criteria_analyzer
from extract_criteria_from_swagger import run_extract_criteria_from_swagger
from extract_tests_data import run_extract_test_data
from helpers import load_json, load_yaml, save_json, save_log_txt

TOOL_DIRECTORY = Path(__file__).resolve().parent
CAPTURE_SCRIPT = TOOL_DIRECTORY / 'http_capture' / 'capture.py'
TEST_FILE_PATTERN = 'EvoMaster*Test.py'
SEARCH_TIMEOUT_MARGIN = 30 * 60


def make_plan(algorithms, blocks, seed):
    rng = random.Random(seed)
    plan = []
    for block in range(blocks):
        for position, algorithm in enumerate(rng.sample(algorithms, len(algorithms))):
            plan.append({'block': block, 'position': position, 'algorithm': algorithm,
                         'seed': rng.randrange(1, 2 ** 31)})
    return plan


def load_or_create_plan(directory, algorithms, blocks, seed):
    path = Path(directory) / 'plan.json'
    plan = make_plan(algorithms, blocks, seed)
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != plan:
            raise ValueError(f'{path} was made with other settings; use another output directory')
        return plan
    save_json(plan, path)
    return plan


def run_directory(campaign_directory, run):
    return Path(campaign_directory) / f"repetition_{run['block']}" / run['algorithm']


def run_status(directory):
    path = Path(directory) / 'run.json'
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8')).get('status')


def pending_runs(plan, campaign_directory):
    return [run for run in plan if run_status(run_directory(campaign_directory, run)) != 'done']


def set_aside(directory, campaign_directory):
    directory = Path(directory)
    if not directory.exists():
        return None
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    target = Path(campaign_directory) / 'incomplete' / f'{directory.parent.name}-{directory.name}-{stamp}'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(directory), str(target))
    return target


def stop_requested(campaign_directory, run):
    return run['position'] == 0 and (Path(campaign_directory) / 'STOP').exists()


def option_text(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def check_options_not_repeated(em_configs, options):
    repeated = sorted(set(em_configs) & set(options))
    if repeated:
        raise ValueError(f'{", ".join(repeated)}: set in the campaign file only, not in the EvoMaster configuration')


def evomaster_command(java, jar, em_config, options, run, directory):
    options = {**options,
               'algorithm': run['algorithm'],
               'seed': run['seed'],
               'outputFolder': Path(directory) / 'generated_tests',
               'statisticsFile': Path(directory) / 'statistics.csv',
               'coveredTargetFile': Path(directory) / 'covered_targets.txt'}
    command = [str(java), '-jar', str(jar), '--configPath', str(em_config)]
    for name, value in options.items():
        command += [f'--{name}', option_text(value)]
    return command


def seconds_of(max_time):
    units = {'h': 3600, 'm': 60, 's': 1}
    return sum(int(amount) * units[unit] for amount, unit in re.findall(r'(\d+)([hms])', max_time))


def evomaster_summary(output):
    plain = re.sub(r'\x1b\[[0-9;]*m', '', output)
    patterns = {'evaluated_tests': r'Evaluated tests: (\d+)',
                'evaluated_actions': r'Evaluated actions: (\d+)',
                'saved_tests': r'Going to save (\d+) tests'}
    summary = {}
    for key, pattern in patterns.items():
        found = re.findall(pattern, plain)
        summary[key] = int(found[-1]) if found else None
    return summary


def unittest_summary(output):
    ran = re.findall(r'^Ran (\d+) tests? in', output, re.M)
    summary = {'tests_run': int(ran[-1]) if ran else None, 'failures': 0, 'errors': 0}
    failed = re.findall(r'^FAILED \(([^)]*)\)', output, re.M)
    if failed:
        for name, count in re.findall(r'(\w+)=(\d+)', failed[-1]):
            summary[name] = int(count)
    return summary


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def timed(phases, name, action):
    started = time.time()
    phases[name] = {'started': now()}
    try:
        return action()
    finally:
        phases[name].update(finished=now(), seconds=round(time.time() - started, 3))


def command_output(command, cwd=None):
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, errors='replace', timeout=300)
        return (result.stdout + result.stderr).strip()
    except (OSError, subprocess.SubprocessError) as error:
        return f'unavailable: {error}'


def docker(*arguments, cwd=None):
    return subprocess.run(['docker', *arguments], cwd=cwd, capture_output=True, text=True, errors='replace',
                          timeout=600, check=True)


def wait_until_up(url, timeout=300):
    deadline = time.monotonic() + timeout
    while True:
        try:
            if requests.get(url, timeout=10).status_code == 200:
                return
        except requests.RequestException:
            pass
        if time.monotonic() > deadline:
            raise TimeoutError(f'{url} did not answer within {timeout} s')
        time.sleep(2)


def run_sql(settings, *statements):
    """Connects to template1 because the statements replace the database the API uses."""
    commands = [argument for statement in statements for argument in ('-c', statement)]
    docker('exec', settings['db_container'], 'psql', '-v', 'ON_ERROR_STOP=1', '-U', settings['db_user'],
           '-d', 'template1', *commands)


def check_database_loaded(settings):
    """When a dump fails to load, the container restarts and Postgres comes up healthy with
    what it had loaded so far, so a healthy database does not show that the load worked."""
    check = settings['database_check']
    result = docker('exec', settings['db_container'], 'psql', '-U', settings['db_user'], '-d', settings['database'],
                    '-Atc', check['query'])
    if result.stdout.strip() != str(check['expected']):
        raise RuntimeError(f"database not loaded: {check['query']} gave {result.stdout.strip()!r}, "
                           f"expected {check['expected']}")


def build_database_base(settings):
    """Creates the database from its dumps and keeps a copy of it, the base that every reset
    restores. Runs once per invocation of the runner."""
    directory = Path(settings['compose_dir']).expanduser()
    compose = ['compose', '-f', settings['compose_file']]
    docker(*compose, 'down', '-v', cwd=directory)
    docker(*compose, 'up', '-d', '--wait', settings['db_service'], cwd=directory)
    check_database_loaded(settings)
    run_sql(settings, f"CREATE DATABASE {settings['database_base']} TEMPLATE {settings['database']}")


def reset_environment(settings):
    """Undoes what the requests changed, without loading the records again: the database goes
    back to its base and the API containers are recreated, with empty queues and buckets and
    empty Laravel log and cache. Records changed by a request are restored too, which deleting
    the rows it created would not do."""
    directory = Path(settings['compose_dir']).expanduser()
    compose = ['compose', '-f', settings['compose_file']]
    docker(*compose, 'rm', '--stop', '--force', *settings['api_services'], cwd=directory)
    docker('volume', 'rm', '--force', settings['queue_volume'])
    docker(*compose, 'up', '-d', '--wait', settings['db_service'], cwd=directory)
    run_sql(settings, f"DROP DATABASE {settings['database']} WITH (FORCE)",
            f"CREATE DATABASE {settings['database']} TEMPLATE {settings['database_base']}")
    docker(*compose, 'up', '-d', cwd=directory)
    wait_until_up(settings['health_url'])
    docker('exec', settings['php_container'], 'sh', '-c', ': > storage/logs/laravel.log && php artisan cache:clear')


def write_gzip(path, text):
    with gzip.open(path, 'wt', encoding='utf-8') as out:
        out.write(text)


def save_api_logs(settings, directory):
    """The containers were created by the last reset, so their logs cover this phase only."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    nginx = docker('logs', settings['nginx_container'])
    write_gzip(directory / 'nginx_access.log.gz', nginx.stdout)
    write_gzip(directory / 'nginx_error.log.gz', nginx.stderr)
    worker = docker('logs', settings['worker_container'])
    write_gzip(directory / 'worker.log.gz', worker.stdout + worker.stderr)
    laravel = docker('exec', settings['php_container'], 'cat', 'storage/logs/laravel.log')
    write_gzip(directory / 'laravel.log.gz', laravel.stdout)


def run_search(command, directory, timeout):
    output_path = Path(directory) / 'execution_output.txt'
    with output_path.open('w', encoding='utf-8') as out:
        result = subprocess.run(command, cwd=directory, stdout=out, stderr=subprocess.STDOUT, timeout=timeout)
    output = output_path.read_text(encoding='utf-8', errors='replace')
    return {'exit_code': result.returncode, **evomaster_summary(output)}


def run_suite(directory, name, timeout, assertions=True):
    """Executes the generated suite and records its HTTP traffic in <name>_http.jsonl.gz.
    Without assertions (python -O) a test goes on after an assertion that no longer holds,
    so every request it contains is made."""
    directory = Path(directory)
    capture = directory / f'{name}_http.jsonl'
    python = [sys.executable] if assertions else [sys.executable, '-O']
    command = [*python, str(CAPTURE_SCRIPT), str(capture),
               'discover', '-s', str(directory / 'generated_tests'), '-p', TEST_FILE_PATTERN, '-v']
    result = subprocess.run(command, cwd=directory, capture_output=True, text=True, errors='replace', timeout=timeout)
    output = result.stdout + result.stderr
    (directory / f'{name}_output.txt').write_text(output, encoding='utf-8')
    exchanges = 0
    if capture.exists():
        text = capture.read_text(encoding='utf-8')
        exchanges = len(text.splitlines())
        write_gzip(directory / f'{name}_http.jsonl.gz', text)
        capture.unlink()
    return {'exit_code': result.returncode, **unittest_summary(output), 'http_exchanges': exchanges}


def generated_test_files(directory):
    folder = Path(directory) / 'generated_tests'
    return sorted(f.name for f in folder.iterdir()
                  if f.is_file() and f.name.startswith('EvoMaster') and f.name.endswith('Test.py'))


def compute_criteria(directory, campaign_directory):
    run_extract_test_data(str(directory), generated_test_files(directory), str(campaign_directory))
    run_criteria_analyzer(str(campaign_directory), str(directory))


def execute_run(run, context):
    directory = run_directory(context['output'], run)
    set_aside(directory, context['output'])
    directory.mkdir(parents=True)
    environment = context['environment']
    info = {**run, 'status': 'running', 'phases': {}}
    phases = info['phases']
    save_json(info, directory / 'run.json')
    try:
        timed(phases, 'reset_before_search', lambda: reset_environment(environment))
        command = evomaster_command(context['java'], context['jar'], context['em_config'],
                                    context['evomaster_options'], run, directory)
        info['evomaster_command'] = command
        info['search'] = timed(phases, 'search', lambda: run_search(command, directory, context['search_timeout']))
        timed(phases, 'save_search_logs', lambda: save_api_logs(environment, directory / 'search_logs'))
        if info['search']['exit_code'] != 0:
            raise RuntimeError(f"EvoMaster exited with code {info['search']['exit_code']}")
        for name, assertions in (('suite', True), ('suite_without_assertions', False)):
            timed(phases, f'reset_before_{name}', lambda: reset_environment(environment))
            info[name] = timed(phases, name,
                               lambda: run_suite(directory, name, context['suite_timeout'], assertions))
            timed(phases, f'save_{name}_logs', lambda: save_api_logs(environment, directory / f'{name}_logs'))
        timed(phases, 'criteria', lambda: compute_criteria(directory, context['output']))
        info['status'] = 'done'
    except Exception:
        info['status'] = 'failed'
        info['error'] = traceback.format_exc()
    finally:
        save_json(info, directory / 'run.json')
    return info


def read_text(path):
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def jar_version(jar):
    with zipfile.ZipFile(jar) as archive:
        manifest = archive.read('META-INF/MANIFEST.MF').decode('utf-8', errors='replace')
    found = re.search(r'^Implementation-Version:\s*(\S+)', manifest, re.M)
    return found.group(1) if found else None


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def describe_environment(java, jar, settings):
    cpu_models = re.findall(r'^model name\s*:\s*(.+)$', read_text('/proc/cpuinfo'), re.M)
    memory = re.search(r'^MemTotal:\s*(\d+) kB', read_text('/proc/meminfo'), re.M)
    os_name = re.search(r'^PRETTY_NAME="?([^"\n]*)', read_text('/etc/os-release'), re.M)
    compose_directory = Path(settings['compose_dir']).expanduser()
    container_ids = command_output(['docker', 'compose', '-f', settings['compose_file'], 'ps', '-q'],
                                   cwd=compose_directory).split()
    containers = command_output(['docker', 'inspect', '--format', '{{.Name}} {{.Config.Image}} {{.Image}}',
                                 *container_ids]).splitlines() if container_ids else []
    return {
        'recorded_at': now(),
        'host': platform.node(),
        'platform': platform.platform(),
        'os': os_name.group(1) if os_name else None,
        'cpu': cpu_models[0] if cpu_models else platform.processor(),
        'logical_cpus': os.cpu_count(),
        'memory_kb': int(memory.group(1)) if memory else None,
        'java': command_output([str(java), '-version']),
        'evomaster_jar': {'path': str(jar), 'version': jar_version(jar), 'sha256': sha256(jar)},
        'python': sys.version,
        'python_packages': command_output([sys.executable, '-m', 'pip', 'freeze']).splitlines(),
        'docker': command_output(['docker', 'version', '--format', '{{.Server.Version}}']),
        'containers': containers,
        'database_files': {name: sha256(compose_directory / name) for name in settings['database_files']},
        'replication_package': {
            'commit': command_output(['git', 'rev-parse', 'HEAD'], cwd=TOOL_DIRECTORY),
            'uncommitted_changes': command_output(['git', 'status', '--porcelain'], cwd=TOOL_DIRECTORY).splitlines(),
        },
    }


def experiment_data(config, em_configs):
    """The fields main.py records, which run_get_statistics_csv.py and the criteria extraction read."""
    tags = [tag.strip() for tag in em_configs.get('endpointTagFilter', '').split(',') if tag.strip()]
    return {'algorithms': config['algorithms'],
            'number_of_repetitions': config['blocks'],
            'swagger_url': em_configs['bbSwaggerUrl'],
            'max_time': config['evomaster_options']['maxTime'],
            'target_tags': tags}


def log(message, output):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)
    save_log_txt(message, Path(output) / 'campaign.log')


def parse_arguments():
    parser = argparse.ArgumentParser(description='Runs an experiment campaign (see the module docstring).')
    parser.add_argument('--config', required=True, help='campaign file, e.g. configs/campaign-6.2.0.json')
    parser.add_argument('--output', required=True, help='campaign directory, e.g. data_generated/campaign-6.2.0')
    parser.add_argument('--em-config', default=str(TOOL_DIRECTORY / 'configs' / 'em.yaml'),
                        help='EvoMaster configuration with the connection to the API (default: configs/em.yaml)')
    parser.add_argument('--blocks', type=int, help='number of blocks, for pilots (default: the campaign file)')
    parser.add_argument('--max-time', help='search budget per execution, for pilots, e.g. 2m (default: the campaign file)')
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    config = load_json(arguments.config)
    if arguments.blocks:
        config['blocks'] = arguments.blocks
    if arguments.max_time:
        config['evomaster_options']['maxTime'] = arguments.max_time

    output = Path(arguments.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    java = Path(config['java']).expanduser()
    jar = Path(config['jar']).expanduser()
    em_config = Path(arguments.em_config).resolve()
    em_configs = load_yaml(em_config)['configs']
    check_options_not_repeated(em_configs, config['evomaster_options'])
    if jar_version(jar) != config['evomaster_version']:
        sys.exit(f"{jar} is EvoMaster {jar_version(jar)}, the campaign file asks for {config['evomaster_version']}")

    plan = load_or_create_plan(output, config['algorithms'], config['blocks'], config['seed'])
    build_database_base(config['environment'])
    reset_environment(config['environment'])
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    save_json({'config': config, 'arguments': vars(arguments),
               'environment': describe_environment(java, jar, config['environment'])},
              output / 'invocations' / f'{stamp}.json')
    data = experiment_data(config, em_configs)
    save_json(data, output / 'experiment_data.json')
    if not (output / 'criteria').exists():
        run_extract_criteria_from_swagger(str(output), data)

    context = {'output': output, 'java': java, 'jar': jar, 'em_config': em_config,
               'evomaster_options': config['evomaster_options'], 'environment': config['environment'],
               'search_timeout': seconds_of(config['evomaster_options']['maxTime']) + SEARCH_TIMEOUT_MARGIN,
               'suite_timeout': config['suite_timeout_minutes'] * 60}
    pending = pending_runs(plan, output)
    log(f'{len(plan) - len(pending)} of {len(plan)} executions already done', output)
    failed = []
    for run in pending:
        if stop_requested(output, run):
            log(f"STOP found: stopping before block {run['block']}", output)
            break
        label = f"repetition {run['block']} {run['algorithm']} (seed {run['seed']})"
        log(f'start {label}', output)
        info = execute_run(run, context)
        log(f"{info['status']} {label}", output)
        if info['status'] != 'done':
            failed.append(label)
    if failed:
        log(f'{len(failed)} execution(s) failed; run the same command again to redo them: {failed}', output)


if __name__ == '__main__':
    main()
