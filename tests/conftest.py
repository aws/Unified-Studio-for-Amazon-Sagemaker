import os
import pytest
import glob

def pytest_configure(config):
    """Configure pytest to use individual log files for each test."""
    # Clean up any existing coverage data to prevent conflicts
    for coverage_file in glob.glob(".coverage*"):
        try:
            os.remove(coverage_file)
        except OSError:
            pass
    
    # Create test-outputs directory if it doesn't exist
    log_dir = "tests/test-outputs"
    os.makedirs(log_dir, exist_ok=True)

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    """Hook to configure a separate log file for each test."""
    # Create test-outputs directory if it doesn't exist
    log_dir = "tests/test-outputs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate log file name based on test name
    log_filename = f"{item.name}.log"
    log_path = os.path.join(log_dir, log_filename)
    
    # Configure logging for this test
    item.config.option.log_file = log_path
    
    # Set current test info for integration test base class
    if hasattr(item.instance, 'setup_debug_logging'):
        item.instance._pytest_current_test = item.name
    
    yield  # Allow the original setup to run
