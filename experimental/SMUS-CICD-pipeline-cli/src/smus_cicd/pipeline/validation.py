"""
Manifest validation utilities for SMUS CI/CD bundle manifests.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import jsonschema

from ..helpers.utils import load_yaml


def load_schema() -> Dict[str, Any]:
    """Load the bundle manifest schema."""
    schema_path = Path(__file__).parent / "bundle-manifest-schema.yaml"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    return load_yaml(str(schema_path))


def validate_yaml_syntax(manifest_path: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validate YAML syntax of manifest file.

    Returns:
        Tuple of (is_valid, error_message, parsed_data)
    """
    try:
        data = load_yaml(manifest_path)
        return True, "", data
    except FileNotFoundError:
        return False, f"File not found: {manifest_path}", {}
    except Exception as e:
        return False, f"YAML syntax error: {e}", {}


def validate_manifest_schema(
    manifest_data: Dict[str, Any], schema: Dict[str, Any] = None
) -> Tuple[bool, List[str]]:
    """
    Validate manifest data against the schema.

    Args:
        manifest_data: Parsed manifest data
        schema: Schema to validate against (loads default if None)

    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    if schema is None:
        try:
            schema = load_schema()
        except Exception as e:
            return False, [f"Failed to load schema: {e}"]

    try:
        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(manifest_data))

        if not errors:
            return True, []

        error_messages = []
        for error in errors:
            path = (
                " -> ".join(str(p) for p in error.absolute_path)
                if error.absolute_path
                else "root"
            )
            error_messages.append(f"Path '{path}': {error.message}")

        return False, error_messages

    except Exception as e:
        return False, [f"Schema validation error: {e}"]


def validate_manifest_file(
    manifest_path: str,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validate a manifest file completely (YAML syntax + schema).

    Args:
        manifest_path: Path to the manifest file

    Returns:
        Tuple of (is_valid, list_of_error_messages, parsed_data)
    """
    # First validate YAML syntax
    yaml_valid, yaml_error, manifest_data = validate_yaml_syntax(manifest_path)
    if not yaml_valid:
        return False, [yaml_error], {}

    # Then validate against schema
    schema_valid, schema_errors = validate_manifest_schema(manifest_data)
    if not schema_valid:
        return False, schema_errors, manifest_data

    return True, [], manifest_data
