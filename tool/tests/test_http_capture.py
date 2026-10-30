"""Recording the HTTP traffic of a generated suite (http_capture/capture.py): every
exchange, with the test that made it, and without the API key."""
import json
import socket
import subprocess
import sys
import textwrap
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

CAPTURE_SCRIPT = Path(__file__).resolve().parents[1] / 'http_capture' / 'capture.py'


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.reply(200, {'data': [{'id': 1}]})

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        self.reply(422, {'received': json.loads(self.rfile.read(length))})

    def reply(self, status, body):
        content = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{httpd.server_address[1]}'
    httpd.shutdown()


def closed_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def run_suite(tmp_path, base_url, methods, python_options=()):
    tests = tmp_path / 'generated_tests'
    tests.mkdir(exist_ok=True)
    (tests / 'EvoMaster_successes_Test.py').write_text(
        'import unittest\nimport requests\n\n\n'
        'class EvoMaster_successes_Test(unittest.TestCase):\n'
        f'    baseUrlOfSut = "{base_url}"\n\n'
        + textwrap.indent(textwrap.dedent(methods), '    '))
    capture = tmp_path / 'http.jsonl'
    capture.unlink(missing_ok=True)
    result = subprocess.run(
        [sys.executable, *python_options, str(CAPTURE_SCRIPT), str(capture),
         'discover', '-s', str(tests), '-p', 'EvoMaster*Test.py'],
        capture_output=True, text=True, timeout=60)
    records = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
    return result, records, capture


def test_each_exchange_is_recorded_with_the_test_that_made_it(tmp_path, server):
    result, records, _ = run_suite(tmp_path, server, '''
        def test_0(self):
            res_0 = requests.get(self.baseUrlOfSut + "/v1/items?page=2")
            assert res_0.status_code == 200

        def test_1(self):
            headers = {"content-type": "application/json"}
            res_0 = requests.post(self.baseUrlOfSut + "/v1/items", headers=headers, data=' { "name": "n" } ')
            assert res_0.status_code == 422
    ''')
    assert result.returncode == 0, result.stderr
    assert [(r['test_file'], r['test'], r['method'], r['url'], r['status']) for r in records] == [
        ('EvoMaster_successes_Test.py', 'test_0', 'GET', f'{server}/v1/items?page=2', 200),
        ('EvoMaster_successes_Test.py', 'test_1', 'POST', f'{server}/v1/items', 422)]
    assert json.loads(records[0]['response_body']) == {'data': [{'id': 1}]}
    assert records[1]['request_body'] == ' { "name": "n" } '
    assert json.loads(records[1]['response_body']) == {'received': {'name': 'n'}}
    assert all(r['elapsed_seconds'] >= 0 and r['error'] is None for r in records)


def test_api_key_is_not_recorded(tmp_path, server):
    _, records, capture = run_suite(tmp_path, server, '''
        def test_0(self):
            headers = {}
            headers["x-api-key"] = "secret-key"
            requests.get(self.baseUrlOfSut + "/v1/items", headers=headers)
    ''')
    assert records[0]['request_headers']['x-api-key'] == '<redacted>'
    assert 'secret-key' not in capture.read_text()


def test_without_assertions_the_requests_after_a_failed_assertion_are_made(tmp_path, server):
    # Replayed on a reset environment, a test may fail on a value that depended on the
    # state left by the search; python -O drops the assertions, so every request is made.
    methods = '''
        def test_0(self):
            res_0 = requests.get(self.baseUrlOfSut + "/v1/items")
            assert res_0.json()["total"] == 41
            res_1 = requests.get(self.baseUrlOfSut + "/v1/items/1")
    '''
    result, records, _ = run_suite(tmp_path, server, methods)
    assert result.returncode != 0
    assert [r['url'] for r in records] == [f'{server}/v1/items']
    result, records, _ = run_suite(tmp_path, server, methods, python_options=['-O'])
    assert result.returncode == 0, result.stderr
    assert [r['url'] for r in records] == [f'{server}/v1/items', f'{server}/v1/items/1']


def test_failed_request_is_recorded_and_still_fails_the_test(tmp_path):
    result, records, _ = run_suite(tmp_path, f'http://127.0.0.1:{closed_port()}', '''
        def test_0(self):
            requests.get(self.baseUrlOfSut + "/v1/items", timeout=5)
    ''')
    assert result.returncode != 0
    assert len(records) == 1
    assert records[0]['test'] == 'test_0'
    assert records[0]['status'] is None
    assert 'ConnectionError' in records[0]['error']
