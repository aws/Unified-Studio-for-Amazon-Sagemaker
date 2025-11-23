#!/usr/bin/env python3
"""
Extract and validate all YAML manifests from documentation files.
Ensures documentation examples remain consistent with actual manifest structure.
"""

import os
import re
import sys
import yaml
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent.parent / "docs"


def extract_yaml_blocks(file_path):
    """Extract all YAML code blocks from a markdown file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find all ```yaml ... ``` blocks
    pattern = r'```yaml\n(.*?)```'
    matches = re.findall(pattern, content, re.DOTALL)
    return matches


def is_complete_manifest(yaml_content):
    """Check if YAML content is a complete manifest (not a snippet)."""
    try:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            return False
        # Must have applicationName AND stages to be considered complete
        return "applicationName" in data and "stages" in data
    except:
        return False


def validate_manifest(yaml_content, source_file, block_num):
    """Validate complete manifest structure."""
    errors = []
    
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return [f"Invalid YAML syntax: {e}"]
    
    if not isinstance(data, dict):
        return ["Manifest must be a dictionary"]
    
    # Check for outdated fields
    if "bundleName" in data:
        errors.append("❌ Uses outdated 'bundleName' (should be 'applicationName')")
    
    if "targets" in data:
        errors.append("❌ Uses outdated 'targets' (should be 'stages')")
    
    if "bundle" in data and "content" not in data:
        errors.append("❌ Uses outdated 'bundle' section (should be 'content')")
    
    if "activation" in data:
        errors.append("⚠️  Uses 'activation' section (deprecated, workflows should be in content.workflows)")
    
    # Check stages structure
    if "stages" in data:
        stages = data["stages"]
        if isinstance(stages, dict):
            for stage_name, stage_config in stages.items():
                if not isinstance(stage_config, dict):
                    continue
                
                # Check required stage fields
                if "domain" in stage_config:
                    domain = stage_config["domain"]
                    if isinstance(domain, dict) and "region" not in domain:
                        errors.append(f"❌ Stage '{stage_name}' domain missing 'region'")
                
                if "project" in stage_config:
                    project = stage_config["project"]
                    if isinstance(project, dict) and "name" not in project:
                        errors.append(f"❌ Stage '{stage_name}' project missing 'name'")
    
    return errors


def main():
    """Extract and validate all complete manifests from documentation."""
    print("🔍 Scanning documentation for complete YAML manifests...\n")
    
    all_manifests = []
    total_errors = 0
    
    # Find all markdown files
    for md_file in DOCS_DIR.rglob("*.md"):
        yaml_blocks = extract_yaml_blocks(md_file)
        
        for i, yaml_content in enumerate(yaml_blocks, 1):
            if is_complete_manifest(yaml_content):
                rel_path = md_file.relative_to(DOCS_DIR.parent)
                manifest_info = {
                    "file": str(rel_path),
                    "block": i,
                    "content": yaml_content
                }
                all_manifests.append(manifest_info)
                
                # Validate
                errors = validate_manifest(yaml_content, str(rel_path), i)
                
                if errors:
                    print(f"📄 {rel_path} (block #{i})")
                    for error in errors:
                        print(f"   {error}")
                    print()
                    total_errors += len(errors)
    
    # Summary
    print("=" * 70)
    print(f"📊 Summary:")
    print(f"   Found {len(all_manifests)} complete manifest(s) in documentation")
    print(f"   Total validation errors: {total_errors}")
    
    if total_errors > 0:
        print("\n❌ Documentation manifests need updates!")
        return 1
    else:
        print("\n✅ All documentation manifests are valid!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

