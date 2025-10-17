#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, 'src')

from smus_cicd.helpers import datazone

# Test with the existing prod-marketing project
project_name = "prod-marketing"
domain_name = "cicd-test-domain"
region = "us-east-2"

print(f"=== TESTING get_project_user_role_arn ===")
print(f"Project: {project_name}")
print(f"Domain: {domain_name}")
print(f"Region: {region}")

user_role_arn = datazone.get_project_user_role_arn(project_name, domain_name, region)

if user_role_arn:
    print(f"✅ Found user role ARN: {user_role_arn}")
else:
    print("❌ No user role ARN found")
