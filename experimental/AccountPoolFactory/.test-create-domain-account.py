#!/usr/bin/env python3
"""
Test create-project using the domain account itself as the environment account.
No pool account involved — useful for verifying authorization grants work.
Run from domain account (amirbo+3).
"""
import json
import time
import sys
import os
import boto3
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, 'config.yaml')) as f:
    config = yaml.safe_load(f)

DOMAIN_ID      = config['datazone']['domain_id']
REGION         = config['aws']['region']
DOMAIN_ACCOUNT = config['aws']['domain_account_id']
PROFILE_ID     = '5riu03k7l71zc9'   # All Capabilities - Account Pool
OWNER_USERNAME = config['datazone'].get('default_project_owner', '')

# ── Verify creds ──────────────────────────────────────────────────────────────
sts = boto3.client('sts', region_name=REGION)
current_account = sts.get_caller_identity()['Account']
if current_account != DOMAIN_ACCOUNT:
    print(f"ERROR: Must run in domain account ({DOMAIN_ACCOUNT}), currently in {current_account}")
    print(f"Run: eval $(isengardcli credentials amirbo+3@amazon.com)")
    sys.exit(1)
print(f"Running in domain account {current_account}")

dz = boto3.client('datazone', region_name=REGION)

# ── Look up owner ─────────────────────────────────────────────────────────────
owner_user_id = None
if OWNER_USERNAME:
    resp = dz.search_user_profiles(domainIdentifier=DOMAIN_ID, userType='SSO_USER', searchText=OWNER_USERNAME)
    for item in resp.get('items', []):
        if item.get('details', {}).get('sso', {}).get('username') == OWNER_USERNAME:
            owner_user_id = item['id']
            break
    print(f"Owner '{OWNER_USERNAME}': {owner_user_id or 'NOT FOUND'}")

# ── Get env config names ──────────────────────────────────────────────────────
profile = dz.get_project_profile(domainIdentifier=DOMAIN_ID, identifier=PROFILE_ID)
env_config_names = [e['name'] for e in profile.get('environmentConfigurations', [])]
print(f"Profile has {len(env_config_names)} env configs")

# ── Build user params — all configs → domain account ─────────────────────────
user_params = [
    {
        'environmentConfigurationName': name,
        'environmentResolvedAccount': {
            'awsAccountId': DOMAIN_ACCOUNT,
            'regionName': REGION
        }
    }
    for name in env_config_names
]

# ── Create project ────────────────────────────────────────────────────────────
ts = str(int(time.time()))
project_name = f'test-domain-acct-{ts}'
print(f"\nCreating project '{project_name}'...")

create_resp = dz.create_project(
    domainIdentifier=DOMAIN_ID,
    name=project_name,
    description='Test: domain account as environment account, no pool',
    projectProfileId=PROFILE_ID,
    userParameters=user_params,
)
project_id = create_resp['id']
print(f"  Project ID: {project_id}")

if owner_user_id:
    dz.create_project_membership(
        domainIdentifier=DOMAIN_ID,
        projectIdentifier=project_id,
        designation='PROJECT_OWNER',
        member={'userIdentifier': owner_user_id}
    )
    print(f"  Owner added: {OWNER_USERNAME}")

# ── Poll ──────────────────────────────────────────────────────────────────────
print("\nPolling...")
for i in range(30):
    time.sleep(10)
    proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
    overall = proj.get('environmentDeploymentDetails', {}).get('overallDeploymentStatus', 'PENDING')
    print(f"  [{i+1}] {overall}")
    if overall not in ('PENDING_DEPLOYMENT', 'IN_PROGRESS_DEPLOYMENT'):
        break

# ── Result ────────────────────────────────────────────────────────────────────
proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
deploy = proj.get('environmentDeploymentDetails', {})
print(f"\n=== Result ===")
print(f"  Status:     {proj.get('projectStatus')}")
print(f"  Deployment: {deploy.get('overallDeploymentStatus')}")
failures = deploy.get('environmentFailureReasons', {})
if failures:
    for env, reasons in failures.items():
        for r in reasons:
            print(f"  ❌ {env}: [{r.get('code')}] {r.get('message')}")
else:
    print(f"  ✅ No failures")
print(f"  Portal: {config['datazone']['portal_url']}/projects/{project_id}")
