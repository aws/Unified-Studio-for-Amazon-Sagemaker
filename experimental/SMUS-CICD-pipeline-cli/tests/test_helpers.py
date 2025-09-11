"""Common test helper functions."""

import json
import pytest


def parse_json_or_show_error(output: str, context: str = "command") -> dict:
    """
    Parse JSON output or show the actual error message if parsing fails.
    
    Args:
        output: The output string to parse as JSON
        context: Context description for error messages
        
    Returns:
        Parsed JSON data
        
    Raises:
        pytest.fail: If JSON parsing fails, shows the actual error text
    """
    if not output.strip():
        pytest.fail(f"{context} returned empty output")
    
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        # Show the actual error text instead of generic JSON parsing failure
        pytest.fail(f"{context} returned text error instead of JSON: {output.strip()}")
