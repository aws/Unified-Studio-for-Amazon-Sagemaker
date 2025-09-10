"""Pytest configuration for integration tests."""
import pytest
import sys
from .base import IntegrationTestBase

def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished, right before returning the exit status to the system."""
    # Force summary to stdout
    sys.stdout.flush()
    IntegrationTestBase.print_test_summary()
    sys.stdout.flush()
