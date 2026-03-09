#!/usr/bin/env python3
"""
End-to-end test: create a project from the account pool.

Correct call sequence:
  1. Call AccountProvider Lambda (listAuthorizedAccountsRequest) → get available pool accounts
  2. Pick the first AVAILABLE account
  3. Call get_project_profile → get environment config names
  4. Call CreateProject with userParameters — each env config mapped to the chosen
     account + sourceAccountPoolId  (REQUIRED — without this DataZone returns
     FAILED_VALIDATION: "EnvironmentConfigurations require a resolved account on input")
  5. Poll until overallDeploymentStatus is SUCCEEDED or FAILED (up to 10 min)
  6. Verify DynamoDB: account is ASSIGNED, poolName=default
  7. Optionally delete project and verify reclaim (--delete flag)

Usage:
  eval $(isengardcli credentials amirbo+3@amazon.com)
  python3 scripts/03-project-account/deploy/01-create-test-project.py            # create, keep
  python3 scripts/03-project-account/deploy/01-create-test-project.py --delete   # create + delete
"""
import json
import sys
import time
import os
import argparse
import boto3
import yaml

# ── Args ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--delete', action='store_true', help='Delete project after successful deployment')
args = parser.parse_args()

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '../../..'))

cfg_file = os.path.join(PROJECT_ROOT, 'domain-config.yaml')
with open(cfg_file) as f:
    config = yaml.safe_load(f)

REGION   = config.get('region', 'us-east-2')
DOMAIN_ID = config.get('domain_id', '')

if not DOMAIN_ID:
    dz_tmp = boto3.client('datazone', region_name=REGION)
    domain_name = config.get('domain_name', '')
    for d in dz_tmp.list_domains().get('items', []):
        if d.get('name') == domain_name:
            DOMAIN_ID = d['id']
            break

if not DOMAIN_ID:
    print('❌ Could not resolve domain ID from domain-config.yaml')
    sys.exit(1)

# Get pool config from first pool entry
pools = config.get('pools', [])
if not pools:
    print('❌ No pools defined in domain-config.yaml')
    sys.exit(1)
first_pool = pools[0]
PROFILE_NAME   = first_pool.get('project_profile_name', 'All Capabilities - Account Pool')
OWNER_USERNAME = first_pool.get('default_project_owner', '')

# ── Clients ───────────────────────────────────────────────────────────────────
sts    = boto3.client('sts', region_name=REGION)
dz     = boto3.client('datazone', region_name=REGION)
lam    = boto3.client('lambda', region_name=REGION)
ddb    = boto3.client('dynamodb', region_name=REGION)

# ── Step 0: Verify credentials ────────────────────────────────────────────────
print('Step 0: Verifying credentials...')
identity = sts.get_caller_identity()
print(f'  Account: {identity["Account"]}  ARN: {identity["Arn"]}')

# ── Step 1: Get account pool ID ───────────────────────────────────────────────
print('\nStep 1: Getting account pool ID...')
pools_resp = dz.list_account_pools(domainIdentifier=DOMAIN_ID)
pool_items = pools_resp.get('items', [])
if not pool_items:
    print('❌ No account pools found in domain')
    sys.exit(1)
ACCOUNT_POOL_ID = pool_items[0]['id']
print(f'  Account pool: {pool_items[0]["name"]} ({ACCOUNT_POOL_ID})')

# ── Step 2: Get project profile ID ───────────────────────────────────────────
print(f'\nStep 2: Resolving project profile "{PROFILE_NAME}"...')
profiles = dz.list_project_profiles(domainIdentifier=DOMAIN_ID)
profile_id = None
for p in profiles.get('items', []):
    if p['name'] == PROFILE_NAME:
        profile_id = p['id']
        break
if not profile_id:
    print(f'❌ Profile "{PROFILE_NAME}" not found')
    sys.exit(1)
print(f'  Profile ID: {profile_id}')

# ── Step 3: Call AccountProvider → get available pool account ─────────────────
print('\nStep 3: Calling AccountProvider (listAuthorizedAccountsRequest)...')
ap_resp = lam.invoke(
    FunctionName='AccountProvider',
    InvocationType='RequestResponse',
    Payload=json.dumps({'operationRequest': {'listAuthorizedAccountsRequest': {
        'context': {'projectProfileName': PROFILE_NAME}
    }}}).encode()
)
ap_result = json.loads(ap_resp['Payload'].read())
available = ap_result.get('operationResponse', {}) \
                     .get('listAuthorizedAccountsResponse', {}) \
                     .get('items', [])
if not available:
    print('❌ No available accounts in pool — run force_replenishment first')
    sys.exit(1)
pool_account_id = available[0]['awsAccountId']
print(f'  Pool has {len(available)} available accounts')
print(f'  Using account: {pool_account_id}')

# ── Step 4: Get environment config names from profile ─────────────────────────
print(f'\nStep 4: Getting environment configs from profile...')
profile_detail = dz.get_project_profile(
    domainIdentifier=DOMAIN_ID,
    identifier=profile_id
)
env_config_names = [e['name'] for e in profile_detail.get('environmentConfigurations', [])]
print(f'  {len(env_config_names)} env configs: {env_config_names}')

# ── Step 5: Build userParameters — all env configs → same pool account ─────────
# This is REQUIRED. Without it DataZone returns:
# FAILED_VALIDATION: "EnvironmentConfigurations require a resolved account on input"
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

# ── Step 6: Look up project owner ─────────────────────────────────────────────
owner_user_id = None
if OWNER_USERNAME:
    print(f'\nStep 5: Looking up user "{OWNER_USERNAME}"...')
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
        print(f'  User ID: {owner_user_id}')
    else:
        print(f'  ⚠️  User not found, skipping owner assignment')

# ── Step 7: Create project ────────────────────────────────────────────────────
project_name = f'test-pool-{int(time.time())}'
print(f'\nStep 6: Creating project "{project_name}"...')

create_resp = dz.create_project(
    domainIdentifier=DOMAIN_ID,
    name=project_name,
    description='End-to-end pool test — auto-created by 01-create-test-project.py',
    projectProfileId=profile_id,
    userParameters=user_params,
)
project_id = create_resp['id']
print(f'  Project ID: {project_id}')
print(f'  Status: {create_resp.get("projectStatus")}')

# Add owner
if owner_user_id:
    try:
        dz.create_project_membership(
            domainIdentifier=DOMAIN_ID,
            projectIdentifier=project_id,
            designation='PROJECT_OWNER',
            member={'userIdentifier': owner_user_id}
        )
        print(f'  ✅ Owner {OWNER_USERNAME} added')
    except Exception as e:
        print(f'  ⚠️  Could not add owner: {e}')

# ── Step 8: Poll until deployment succeeds or fails ───────────────────────────
print(f'\nStep 7: Polling deployment status (up to 10 min)...')
POLL_INTERVAL = 15
MAX_POLLS = 40  # 40 × 15s = 10 min

final_status = None
for i in range(MAX_POLLS):
    time.sleep(POLL_INTERVAL)
    proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
    project_status = proj.get('projectStatus')
    deploy = proj.get('environmentDeploymentDetails', {})
    overall = deploy.get('overallDeploymentStatus', 'PENDING')
    print(f'  [{(i+1)*POLL_INTERVAL:3d}s] projectStatus={project_status}  deploymentStatus={overall}')

    if overall in ('SUCCESSFUL', 'SUCCEEDED', 'FAILED_VALIDATION', 'FAILED_DEPLOYMENT'):
        final_status = overall
        break
    if project_status == 'DELETE_FAILED':
        final_status = 'DELETE_FAILED'
        break
else:
    final_status = 'TIMEOUT'

# ── Step 9: Verify DynamoDB ───────────────────────────────────────────────────
print(f'\nStep 8: Verifying DynamoDB state...')
r = ddb.query(
    TableName='AccountPoolFactory-AccountState',
    KeyConditionExpression='accountId = :a',
    ExpressionAttributeValues={':a': {'S': pool_account_id}},
    ScanIndexForward=False, Limit=1
)
items = r.get('Items', [])
if items:
    state = items[0].get('state', {}).get('S', '?')
    pool  = items[0].get('poolName', {}).get('S', '?')
    print(f'  Account {pool_account_id}: state={state}  pool={pool}')
    dynamo_ok = state == 'ASSIGNED' and pool == 'default'
    print(f'  DynamoDB check: {"✅ PASS" if dynamo_ok else "❌ FAIL (expected ASSIGNED/default)"}')
else:
    print(f'  ❌ Account {pool_account_id} not found in DynamoDB')
    dynamo_ok = False

# ── Step 10: Print result ─────────────────────────────────────────────────────
print(f'\n{"="*60}')
print(f'Result:')
print(f'  Project:           {project_name} ({project_id})')
print(f'  Assigned account:  {pool_account_id}')
print(f'  Deployment status: {final_status}')
print(f'  DynamoDB:          {"✅ PASS" if dynamo_ok else "❌ FAIL"}')

proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
deploy = proj.get('environmentDeploymentDetails', {})
failures = deploy.get('environmentFailureReasons', {})
if failures:
    print(f'  Failures:')
    for env, reasons in failures.items():
        for r in reasons:
            print(f'    [{r.get("code")}] {r.get("message", "")[:120]}')

portal_url = f'https://{DOMAIN_ID}.sagemaker.{REGION}.on.aws'
print(f'\n  Portal: {portal_url}/projects/{project_id}')

overall_pass = final_status in ('SUCCESSFUL', 'SUCCEEDED') and dynamo_ok
print(f'\n{"✅ TEST PASSED" if overall_pass else "❌ TEST FAILED"}')

# ── Step 11: Optionally delete ────────────────────────────────────────────────
if args.delete:
    print(f'\nStep 9: Deleting project {project_id}...')
    dz.delete_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
    print(f'  Deleted. Monitor reclaim: python3 scripts/utils/monitor-pool.py 10')
else:
    print(f'\nProject kept. To delete:')
    print(f'  aws datazone delete-project --domain-identifier {DOMAIN_ID} --identifier {project_id} --region {REGION}')
    print(f'To run full cycle (create + delete):')
    print(f'  python3 {sys.argv[0]} --delete')

sys.exit(0 if overall_pass else 1)
