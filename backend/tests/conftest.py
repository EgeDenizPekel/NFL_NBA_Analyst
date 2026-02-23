"""
Shared fixtures for the test suite.

Run all fast tests (no network):
    pytest -m "not integration"

Run integration tests (real ESPN / bref / nfl_data_py calls):
    pytest -m integration
"""
import sys
import os

# Ensure backend root is on sys.path so imports like `from utils.cache import cache` work.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
