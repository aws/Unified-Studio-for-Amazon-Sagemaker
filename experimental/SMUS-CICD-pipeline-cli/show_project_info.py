#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, 'src')

from smus_cicd.helpers.utils import get_datazone_project_info, load_config
from smus_cicd.pipeline import PipelineManifest
import json

# Load the test pipeline
manifest = PipelineManifest.from_file('tests/integration/multi_target_pipeline/multi_target_pipeline.yaml')
target_config = manifest.get_target('test')

# Prepare config
config = load_config()
config["domain"] = {
    "name": target_config.domain.name,
    "region": target_config.domain.region,
}
config["region"] = target_config.domain.region

# Get project info
project_name = target_config.project.name
project_info = get_datazone_project_info(project_name, config)

print("=== PROJECT INFO FOR TEST TARGET ===")
print(json.dumps(project_info, indent=2, default=str))

# Also show current AWS identity
import boto3
try:
    sts = boto3.client('sts', region_name=target_config.domain.region)
    identity = sts.get_caller_identity()
    print("\n=== CURRENT AWS IDENTITY ===")
    print(json.dumps(identity, indent=2, default=str))
except Exception as e:
    print(f"Error getting AWS identity: {e}")
