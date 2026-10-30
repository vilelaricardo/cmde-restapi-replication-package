import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent))
sys.path.insert(0, str(TESTS_DIR))


@pytest.fixture(scope='session')
def mini_criteria(tmp_path_factory):
    """Required elements of every criterion for MINI_SPEC (support.py)."""
    from support import get_items, run_pipeline
    return run_pipeline(tmp_path_factory.mktemp('mini-spec'), get_items('')).criteria
