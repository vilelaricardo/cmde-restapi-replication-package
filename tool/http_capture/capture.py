"""Runs a generated unittest suite while recording every HTTP exchange made through
requests, one JSON object per line: the test that made the call, the request and the
response (or the error). The API key is not recorded.

    python capture.py <capture.jsonl> discover -s <generated_tests> -p 'EvoMaster*Test.py'

It lives in its own directory so that running it puts nothing else on sys.path.
"""
import json
import os
import sys
import time
import unittest

import requests

REDACTED_HEADERS = {'x-api-key', 'authorization'}


def calling_test():
    frame = sys._getframe(1)
    while frame:
        if frame.f_code.co_name.startswith('test'):
            return os.path.basename(frame.f_code.co_filename), frame.f_code.co_name
        frame = frame.f_back
    return None, None


def as_text(content):
    if isinstance(content, bytes):
        return content.decode('utf-8', errors='replace')
    return content


def visible_headers(headers):
    return {name: '<redacted>' if name.lower() in REDACTED_HEADERS else value for name, value in headers.items()}


def exchange_record(request, response, error, elapsed):
    test_file, test = calling_test()
    return {
        'test_file': test_file,
        'test': test,
        'method': request.method,
        'url': request.url,
        'request_headers': visible_headers(request.headers),
        'request_body': as_text(request.body),
        'status': response.status_code if response is not None else None,
        'response_headers': visible_headers(response.headers) if response is not None else None,
        'response_body': response.text if response is not None else None,
        'error': repr(error) if error is not None else None,
        'elapsed_seconds': elapsed,
    }


def install(capture_path):
    send = requests.Session.send

    def recording_send(session, request, **kwargs):
        started = time.perf_counter()
        response, error = None, None
        try:
            response = send(session, request, **kwargs)
            return response
        except Exception as e:
            error = e
            raise
        finally:
            record = exchange_record(request, response, error, time.perf_counter() - started)
            with open(capture_path, 'a', encoding='utf-8') as capture:
                capture.write(json.dumps(record, ensure_ascii=False) + '\n')

    requests.Session.send = recording_send


if __name__ == '__main__':
    install(sys.argv[1])
    unittest.main(module=None, argv=['unittest'] + sys.argv[2:])
