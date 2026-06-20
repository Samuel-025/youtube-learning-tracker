"""Pytest fixtures for YouTube Learning Tracker test suite.

Factory helpers (make_video, make_collection) live in tests/helpers.py.
This file only contains pytest fixtures so conftest is never imported directly.
"""

import sys
import os

# Ensure the project root is on sys.path so `from models...` / `from core...`
# work when pytest is run from the project root directory.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Also put tests/ on sys.path so `from helpers import ...` works.
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

import pytest
from helpers import make_video, make_collection
from core.storage import Storage


@pytest.fixture
def storage(tmp_path):
    """Isolated Storage instance backed by a temp directory — never touches data/."""
    return Storage(str(tmp_path / "videos.json"))


@pytest.fixture
def video():
    """A default unsaved Video object."""
    return make_video()


@pytest.fixture
def collection():
    """A default unsaved Collection object."""
    return make_collection()
