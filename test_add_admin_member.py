#!/usr/bin/env python3
"""Test adding Admin role as project member."""

import sys
sys.path.insert(0, '/Users/amirbo/code/smus/experimental/SMUS-CICD-pipeline-cli/src')

from smus_cicd.helpers.datazone import manage_project_memberships

# Configuration
DOMAIN_ID = "dzd-614fzsz5nulxm1"
PROJECT_ID = "buh47o22sg5ui1"  # test-project-basic (NOT test-marketing!)
REGION = "us-east-2"
ADMIN_ROLE_ARN = "arn:aws:iam::198737698272:role/Admin"

print("=" * 60)
print("Testing: Add Admin role as project owner")
print("=" * 60)
print(f"Domain: {DOMAIN_ID}")
print(f"Project: test-project-basic")
print(f"Project ID: {PROJECT_ID}")
print(f"Region: {REGION}")
print(f"Admin Role: {ADMIN_ROLE_ARN}")
print("=" * 60)
print()

# Add Admin role as owner
print("Adding Admin role as project owner...")
manage_project_memberships(
    project_id=PROJECT_ID,
    domain_id=DOMAIN_ID,
    region=REGION,
    owners=[ADMIN_ROLE_ARN],
    contributors=[]
)

print("\n" + "=" * 60)
print("✅ Test completed!")
print("=" * 60)
