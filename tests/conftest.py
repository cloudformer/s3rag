"""Test setup: src/server and client/ on the import path; the compatibility-report hooks.

The report hooks must live in the ROOT conftest so they see the whole run (regression + compat).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))

# lambda_function reads these at import time
os.environ.setdefault("USER_NAME", "admin")
os.environ.setdefault("PASSWORD", "pw")

from compat_report import (pytest_collection_modifyitems, pytest_configure,  # noqa: E402,F401
                           pytest_runtest_logreport, pytest_sessionfinish, pytest_terminal_summary)
