#!/usr/bin/env python3
"""Test creating a group profile for a role that doesn't exist."""

import sys
sys.path.insert(0, '/Users/amirbo/code/smus/experimental/SMUS-CICD-pipeline-cli/src')

from smus_cicd.helpers.datazone import get_group_id_for_role_arn

# Test with a role that might not have a group profile yet
TEST_ROLE_ARN = "arn:aws:iam::198737698272:role/Admin"
DOMAIN_ID = "dzd-614fzsz5nulxm1"
REGION = "us-east-2"

print("Testing get_group_id_for_role_arn with create capability\n")
group_id = get_group_id_for_role_arn(TEST_ROLE_ARN, DOMAIN_ID, REGION)

if group_id:
    print(f"\n✅ SUCCESS: Group ID = {group_id}")
else:
    print(f"\n❌ FAILED: Could not get/create group ID")
    sys.exit(1)
