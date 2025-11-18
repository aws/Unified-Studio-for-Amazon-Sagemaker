"""Pytest configuration for integration tests."""

import os
import pytest
import sys
import yaml
from pathlib import Path
from .base import IntegrationTestBase


def pytest_configure(config):
    """Load test configuration and set environment variables."""
    # Look for config file in tests/scripts directory
    config_dir = Path(__file__).parent.parent / "scripts"
    print(f"🔧 Looking for config in: {config_dir}")
    
    # Try to find config file (prefer account-specific config)
    config_files = list(config_dir.glob("config-*.yaml"))
    print(f"🔧 Found {len(config_files)} config files: {[f.name for f in config_files]}")
    
    if config_files:
        config_file = config_files[0]  # Use first found config
        print(f"🔧 Loading config from: {config_file.name}")
        with open(config_file) as f:
            test_config = yaml.safe_load(f)
        
        # Set service endpoint environment variables
        if "service_endpoints" in test_config:
            endpoints = test_config["service_endpoints"]
            if "datazone" in endpoints:
                os.environ["DATAZONE_ENDPOINT_URL"] = endpoints["datazone"]
                print(f"✓ Set DATAZONE_ENDPOINT_URL={endpoints['datazone']}")
        else:
            print("⚠️  No service_endpoints found in config")


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
