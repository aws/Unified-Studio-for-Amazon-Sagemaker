#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, "src")

from smus_cicd.helpers.utils import load_config, _get_region_from_config
from smus_cicd.pipeline import PipelineManifest


def debug_region_resolution():
    print("=== Debug Region Resolution ===")

    # Test 1: Load pipeline manifest
    manifest_file = "tests/integration/multi_target_pipeline/multi_target_pipeline.yaml"
    print(f"Loading manifest: {manifest_file}")

    try:
        manifest = PipelineManifest.from_file(manifest_file)
        print(f"✅ Manifest loaded successfully")
        print(f"   Domain name: {manifest.domain.name}")
        print(f"   Domain region: {manifest.domain.region}")
    except Exception as e:
        print(f"❌ Failed to load manifest: {e}")
        return

    # Test 2: Set up config like the test command does
    print("\n=== Config Setup (Fixed Version) ===")
    config = load_config()
    config["domain"] = {"name": manifest.domain.name, "region": manifest.domain.region}
    config["region"] = manifest.domain.region
    config["domain_name"] = manifest.domain.name

    print(f"Config structure:")
    print(f"  config['domain']: {config.get('domain')}")
    print(f"  config['region']: {config.get('region')}")
    print(f"  config['domain_name']: {config.get('domain_name')}")

    # Test 3: Region resolution
    print("\n=== Region Resolution ===")
    try:
        resolved_region = _get_region_from_config(config)
        print(f"✅ Region resolved: {resolved_region}")
    except Exception as e:
        print(f"❌ Region resolution failed: {e}")
        return

    # Test 4: Check environment variables
    print("\n=== Environment Variables ===")
    aws_region = os.environ.get("AWS_DEFAULT_REGION")
    aws_region_env = os.environ.get("AWS_REGION")
    print(f"AWS_DEFAULT_REGION: {aws_region}")
    print(f"AWS_REGION: {aws_region_env}")

    # Test 5: Simulate DataZone client creation
    print("\n=== DataZone Client Simulation ===")
    print(f"Would create DataZone client with region_name='{resolved_region}'")

    if resolved_region != manifest.domain.region:
        print(
            f"❌ MISMATCH: Resolved region ({resolved_region}) != Manifest region ({manifest.domain.region})"
        )
    else:
        print(f"✅ MATCH: Resolved region matches manifest region")


if __name__ == "__main__":
    debug_region_resolution()
