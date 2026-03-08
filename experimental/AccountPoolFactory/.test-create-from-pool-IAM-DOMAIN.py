#!/usr/bin/env python3
"""Test create-project from pool account to verify same-account PassRole works."""
import json
import subprocess
import time
import sys
import os
import yaml

# Load config
with open(os.path.join(os.path.dirname(__file__) or '.', 'config.yaml')) as f:
    config = yaml.safe_load(f)

DOMAIN_ID = config['datazone']['domain_id']

# Step 1: Get domain account creds
print("Step 1: Getting domain account creds...")
result = subprocess.run(
    ["isengardcli", "credentials", "amirbo+3@amazon.com", "--role", "Admin"],
    capture_output=True, text=True, timeout=30, check=False
)
if result.returncode != 0:
    print(f"Failed to get domain creds: {result.stderr}")
    sys.exit(1)

domain_env = {}
for line in result.stdout.strip().split('\n'):
    if line.startswith('export '):
        key, val = line.replace('export ', '').split('=', 1)
        domain_env[key] = val
print("  Got domain creds")

# Step 2: Assume role in pool account
print("Step 2: Assuming SMUS-AccountPoolFactory-DomainAccess in 392423995616...")
env = os.environ.copy()
env.update(domain_env)

result = subprocess.run([
    "aws", "sts", "assume-role",
    "--role-arn", "arn:aws:iam::392423995616:role/SMUS-AccountPoolFactory-DomainAccess",
    "--role-session-name", "test-create-project",
    "--external-id", DOMAIN_ID,
    "--output", "json"
], capture_output=True, text=True, env=env, timeout=30, check=False)

if result.returncode != 0:
    print(f"Failed to assume role: {result.stderr}")
    sys.exit(1)

creds = json.loads(result.stdout)['Credentials']
pool_env = os.environ.copy()
pool_env['AWS_ACCESS_KEY_ID'] = creds['AccessKeyId']
pool_env['AWS_SECRET_ACCESS_KEY'] = creds['SecretAccessKey']
pool_env['AWS_SESSION_TOKEN'] = creds['SessionToken']
print("  Assumed role successfully")

# Step 3: Skip identity check, go straight to create-project
print("  Skipping identity check, proceeding to create-project...")

# Step 4: Create project
print("Step 4: Creating project from pool account...")
ts = str(int(time.time()))

user_params = json.dumps([
    {
        "environmentConfigurationName": "ToolingLite",
        "environmentResolvedAccount": {
            "awsAccountId": "392423995616",
            "regionName": "us-east-2",
            "sourceAccountPoolId": "5id04597iehicp"
        }
    },
    {
        "environmentConfigurationName": "S3Bucket",
        "environmentResolvedAccount": {
            "awsAccountId": "392423995616",
            "regionName": "us-east-2",
            "sourceAccountPoolId": "5id04597iehicp"
        }
    },
    {
        "environmentConfigurationName": "S3TableCatalog",
        "environmentResolvedAccount": {
            "awsAccountId": "392423995616",
            "regionName": "us-east-2",
            "sourceAccountPoolId": "5id04597iehicp"
        }
    }
])

role_configs = json.dumps([
    {
        "roleArn": "arn:aws:iam::392423995616:role/service-role/AmazonSageMakerProjectRole",
        "roleDesignation": "PROJECT_CONTRIBUTOR"
    }
])

cmd = [
    "aws", "datazone", "create-project",
    "--domain-identifier", DOMAIN_ID,
    "--name", f"test-from-pool-{ts}",
    "--description", "Test create-project from pool account",
    "--project-profile-id", "48ly31ms09wckp",
    "--user-parameters", user_params,
    "--customer-provided-role-configs", role_configs,
    "--membership-assignments", "[]",
    "--region", "us-east-2",
    "--output", "json"
]

try:
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=pool_env, timeout=30, check=False
    )
    print(f"  Return code: {result.returncode}")
    if result.stdout:
        print(f"  STDOUT: {result.stdout[:2000]}")
    if result.stderr:
        print(f"  STDERR: {result.stderr[:2000]}")
except subprocess.TimeoutExpired:
    print("  TIMEOUT after 30s")
    sys.exit(1)
