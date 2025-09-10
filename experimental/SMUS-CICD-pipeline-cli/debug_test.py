#!/usr/bin/env python3
"""Debug script to reproduce the 'str' object has no attribute 'get' error."""

import sys
import os
sys.path.insert(0, 'src')

from smus_cicd.commands.run import _get_workflow_connections

def debug_workflow_connections():
    """Debug the workflow connections issue."""
    
    # Test case 1: Normal dictionary structure
    print("=== Test 1: Normal dictionary structure ===")
    project_info_normal = {
        "connections": {
            "project.workflow_mwaa": {
                "type": "WORKFLOWS_MWAA",
                "s3Uri": "s3://some-bucket"
            },
            "project.athena": {
                "type": "ATHENA",
                "database": "default"
            }
        }
    }
    
    try:
        result = _get_workflow_connections(project_info_normal)
        print(f"✅ Normal case result: {result}")
    except Exception as e:
        print(f"❌ Normal case error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test case 2: String values instead of dictionaries
    print("\n=== Test 2: String values (problematic case) ===")
    project_info_strings = {
        "connections": {
            "project.workflow_mwaa": "WORKFLOWS_MWAA",  # String instead of dict
            "project.athena": "ATHENA"  # String instead of dict
        }
    }
    
    try:
        result = _get_workflow_connections(project_info_strings)
        print(f"✅ String case result: {result}")
    except Exception as e:
        print(f"❌ String case error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test case 3: Empty connections
    print("\n=== Test 3: Empty connections ===")
    project_info_empty = {
        "connections": {}
    }
    
    try:
        result = _get_workflow_connections(project_info_empty)
        print(f"✅ Empty case result: {result}")
    except Exception as e:
        print(f"❌ Empty case error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_workflow_connections()
