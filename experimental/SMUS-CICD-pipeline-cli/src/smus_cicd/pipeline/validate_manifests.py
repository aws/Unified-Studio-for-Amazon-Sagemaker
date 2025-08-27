#!/usr/bin/env python3
"""
Validate pipeline manifests against the JSON schema.
"""

import json
import yaml
import sys
from pathlib import Path
from jsonschema import validate, ValidationError, Draft7Validator

def load_schema():
    """Load the pipeline manifest schema."""
    schema_path = Path(__file__).parent / "pipeline-manifest-schema.yaml"
    with open(schema_path, 'r') as f:
        return yaml.safe_load(f)

def load_yaml_manifest(manifest_path):
    """Load a YAML manifest file."""
    with open(manifest_path, 'r') as f:
        return yaml.safe_load(f)

def validate_manifest(manifest_path, schema):
    """Validate a single manifest against the schema."""
    print(f"\n=== Validating {manifest_path} ===")
    
    try:
        manifest = load_yaml_manifest(manifest_path)
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(manifest))
        
        if not errors:
            print("✅ VALID - No schema violations found")
            return True
        else:
            print(f"❌ INVALID - Found {len(errors)} schema violations:")
            for i, error in enumerate(errors, 1):
                path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
                print(f"  {i}. Path: {path}")
                print(f"     Error: {error.message}")
                if error.validator_value:
                    print(f"     Expected: {error.validator_value}")
                print()
            return False
            
    except Exception as e:
        print(f"❌ ERROR - Failed to validate: {e}")
        return False

def main():
    """Main validation function."""
    print("Pipeline Manifest Schema Validation")
    print("=" * 50)
    
    # Load schema
    try:
        schema = load_schema()
        print("✅ Schema loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load schema: {e}")
        sys.exit(1)
    
    # Check if manifest files are provided as arguments
    if len(sys.argv) > 1:
        manifest_files = sys.argv[1:]
    else:
        print("Usage: python validate_manifests.py <manifest_file1> [manifest_file2] ...")
        print("Example: python validate_manifests.py pipeline.yaml")
        sys.exit(1)
    
    # Validate each manifest
    all_valid = True
    for manifest_file in manifest_files:
        manifest_path = Path(manifest_file)
        if manifest_path.exists():
            is_valid = validate_manifest(manifest_path, schema)
            all_valid = all_valid and is_valid
        else:
            print(f"\n❌ File not found: {manifest_file}")
            all_valid = False
    
    # Summary
    print("\n" + "=" * 50)
    if all_valid:
        print("🎉 All manifests are valid!")
        sys.exit(0)
    else:
        print("💥 Some manifests have validation errors")
        sys.exit(1)

if __name__ == "__main__":
    main()
