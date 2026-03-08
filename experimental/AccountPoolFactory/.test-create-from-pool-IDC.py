#!/usr/bin/env python3
"""
Test create-project from pool account — IDC domain version.

Flow:
  1. Run in domain account (amirbo+3) as Admin
  2. Call AccountProvider Lambda to list available pool accounts
  3. Pick the first AVAILABLE account
  4. Get environment config names from the project profile
  5. Call CreateProject with all env configs pointing to the pool account
  6. Poll until project is ACTIVE or FAILED
  7. Print result

No role configs needed — IDC domain creates roles automatically.
"""
import json
import subprocess
import time
import sys
import os
import boto3
import yaml

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, 'config.yaml')) as f:
    config = yaml.safe_load(f)

DOMAIN_ID        = config['datazone']['domain_id']
REGION           = config['aws']['region']
ACCOUNT_POOL_ID  = 'c5r1rtjwi2qhbd'
PROFILE_ID       = '5riu03k7l71zc9'   # All Capabilities - Account Pool
PROVIDER_FN      = 'AccountProvider'
OWNER_USERNAME   = config['datazone'].get('default_project_owner', '')

# ── Step 1: Verify we're in the domain account ────────────────────────────────
print("Step 1: Verifying domain account credentials...")
sts = boto3.client('sts', region_name=REGION)
identity = sts.get_caller_identity()
current_account = identity['Account']
domain_account  = config['aws']['domain_account_id']

if current_account != domain_account:
    print(f"  ERROR: Must run in domain account ({domain_account}), currently in {current_account}")
    print(f"  Run: eval $(isengardcli credentials amirbo+3@amazon.com)")
    sys.exit(1)
print(f"  OK — running in domain account {current_account}")

# ── Step 2: Get available pool account from AccountProvider ───────────────────
print("\nStep 2: Calling AccountProvider to list available accounts...")
lambda_client = boto3.client('lambda', region_name=REGION)

response = lambda_client.invoke(
    FunctionName=PROVIDER_FN,
    InvocationType='RequestResponse',
    Payload=json.dumps({'operationRequest': {'listAuthorizedAccountsRequest': {}}})
)
result = json.loads(response['Payload'].read())
accounts = result.get('operationResponse', {}) \
                 .get('listAuthorizedAccountsResponse', {}) \
                 .get('items', [])

if not accounts:
    print("  ERROR: No available accounts in pool")
    sys.exit(1)

pool_account_id = accounts[0]['awsAccountId']
print(f"  Pool has {len(accounts)} available accounts")
print(f"  Using account: {pool_account_id}")

# ── Step 3: Get environment config names from project profile ─────────────────
print(f"\nStep 3: Getting environment configs from profile {PROFILE_ID}...")
dz = boto3.client('datazone', region_name=REGION)

profile = dz.get_project_profile(
    domainIdentifier=DOMAIN_ID,
    identifier=PROFILE_ID
)
env_config_names = [e['name'] for e in profile.get('environmentConfigurations', [])]
print(f"  Found {len(env_config_names)} environment configs: {env_config_names}")

# ── Step 3b: Look up project owner user profile ID ────────────────────────────
owner_user_id = None
if OWNER_USERNAME:
    print(f"\nStep 3b: Looking up user profile for '{OWNER_USERNAME}'...")
    resp = dz.search_user_profiles(
        domainIdentifier=DOMAIN_ID,
        userType='SSO_USER',
        searchText=OWNER_USERNAME
    )
    for item in resp.get('items', []):
        if item.get('details', {}).get('sso', {}).get('username') == OWNER_USERNAME:
            owner_user_id = item['id']
            break
    if owner_user_id:
        print(f"  Found user ID: {owner_user_id}")
    else:
        print(f"  ⚠️  User '{OWNER_USERNAME}' not found, skipping owner assignment")

# ── Step 4: Build userParameters — all env configs → same pool account ────────
user_params = [
    {
        'environmentConfigurationName': name,
        'environmentResolvedAccount': {
            'awsAccountId': pool_account_id,
            'regionName': REGION,
            'sourceAccountPoolId': ACCOUNT_POOL_ID
        }
    }
    for name in env_config_names
]

# ── Step 5: Build membership assignments ─────────────────────────────────────
membership_assignments = []
if owner_user_id:
    membership_assignments = [
        {
            'designation': 'PROJECT_OWNER',
            'member': {'userIdentifier': owner_user_id}
        }
    ]

# ── Step 6: Create project ────────────────────────────────────────────────────
ts = str(int(time.time()))
project_name = f'test-pool-idc-{ts}'
print(f"\nStep 5: Creating project '{project_name}'...")

create_kwargs = dict(
    domainIdentifier=DOMAIN_ID,
    name=project_name,
    description='End-to-end test: IDC domain, account pool, no role config',
    projectProfileId=PROFILE_ID,
    userParameters=user_params,
)

create_resp = dz.create_project(**create_kwargs)

project_id = create_resp['id']
print(f"  Project created: {project_id}")
print(f"  Status: {create_resp.get('projectStatus')}")

# Add project owner
if owner_user_id:
    print(f"  Adding {OWNER_USERNAME} as PROJECT_OWNER...")
    try:
        dz.create_project_membership(
            domainIdentifier=DOMAIN_ID,
            projectIdentifier=project_id,
            designation='PROJECT_OWNER',
            member={'userIdentifier': owner_user_id}
        )
        print(f"  ✅ Owner added")
    except Exception as e:
        print(f"  ⚠️  Could not add owner: {e}")

# ── Step 7: Poll until ACTIVE or deployment result ────────────────────────────
print(f"\nStep 6: Polling project status...")
for i in range(30):
    time.sleep(10)
    proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
    status = proj.get('projectStatus')
    deploy = proj.get('environmentDeploymentDetails', {})
    overall = deploy.get('overallDeploymentStatus', 'PENDING')
    print(f"  [{i+1}] projectStatus={status}  deploymentStatus={overall}")

    if status == 'ACTIVE' and overall not in ('PENDING_DEPLOYMENT', 'IN_PROGRESS_DEPLOYMENT'):
        break
    if status == 'DELETE_FAILED':
        break

# ── Step 8: Final result ──────────────────────────────────────────────────────
print(f"\n=== Result ===")
proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
print(f"  Project ID:        {project_id}")
print(f"  Project Name:      {proj['name']}")
print(f"  Project Status:    {proj.get('projectStatus')}")
deploy = proj.get('environmentDeploymentDetails', {})
print(f"  Deployment Status: {deploy.get('overallDeploymentStatus')}")

failures = deploy.get('environmentFailureReasons', {})
if failures:
    print(f"  Failures:")
    for env, reasons in failures.items():
        for r in reasons:
            print(f"    {env}: [{r.get('code')}] {r.get('message')}")
else:
    print(f"  No deployment failures ✅")

print(f"\n  Portal: {config['datazone']['portal_url']}/projects/{project_id}")
