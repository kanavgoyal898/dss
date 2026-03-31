"""
Purpose: DSS test suite launcher — run this script to execute all pytest tests.
Responsibilities:
    - Add the parent directory to sys.path so the dss package is importable.
    - Invoke pytest programmatically on the tests/ directory.
Dependencies: pytest
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

if __name__ == "__main__":
    sys.exit(pytest.main([os.path.join(os.path.dirname(__file__), "tests"), "-v"]))
