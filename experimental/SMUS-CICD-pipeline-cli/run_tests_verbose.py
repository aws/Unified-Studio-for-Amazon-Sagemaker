#!/usr/bin/env python3
import subprocess
import sys
import os

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_tests_with_progress():
    os.chdir(SCRIPT_DIR)
    
    # Run pytest with live output
    cmd = [
        sys.executable, '-m', 'pytest', 
        'tests/integration/', 
        '-v', 
        '--capture=no',  # Don't capture output
        '--tb=short',
        '--durations=10',  # Show slowest 10 tests
        '-x'  # Stop on first failure
    ]
    
    print("Starting integration tests...")
    print("=" * 50)
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # Print output line by line as it comes
    for line in process.stdout:
        print(line, end='', flush=True)
    
    process.wait()
    return process.returncode

if __name__ == "__main__":
    exit_code = run_tests_with_progress()
    sys.exit(exit_code)
