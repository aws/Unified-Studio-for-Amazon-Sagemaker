"""Pytest configuration for integration tests."""

import os
import pytest
import sys
from pathlib import Path
from .base import IntegrationTestBase


def pytest_configure(config):
    """Configure pytest for integration tests."""
    # All configuration comes from environment variables
    # Use env-<account>.env files sourced before running pytest
    pass


def pytest_runtest_logreport(report):
    """Capture test failures after report is logged."""
    # Only process call phase failures
    if report.when == "call" and report.outcome == "failed":
        # Extract test name from nodeid (format: path::Class::method)
        parts = report.nodeid.split("::")
        if len(parts) >= 2:
            class_name = parts[-2]
            method_name = parts[-1]
            test_name = f"{class_name}__{method_name}"
            
            # Find and update the test result
            for result in IntegrationTestBase._test_results:
                if result["name"] == test_name:
                    result["success"] = False
                    break


def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished, right before returning the exit status to the system."""
    # Force summary to stdout
    sys.stdout.flush()
    IntegrationTestBase.print_test_summary()
    sys.stdout.flush()
