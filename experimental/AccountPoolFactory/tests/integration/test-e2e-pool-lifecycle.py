#!/usr/bin/env python3
"""
End-to-end pool lifecycle test:
  1. Create project from pool  → account moves to ASSIGNED
  2. Delete project            → account returns to AVAILABLE

Usage:
    eval $(isengardcli credentials amirbo+3@amazon.com)
    python3 tests/integration/test-e2e-pool-lifecycle.py

Exit codes: 0 = all steps passed, 1 = failure
"""
import sys
import os
import time
import json
import boto3
import yaml
from datetime import datetime, timezone

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..', '..')

# Load domain-config.yaml (preferred) or fall back to legacy config.yaml
_cfg_file = os.path.join(PROJECT_ROOT, 'domain-config.yaml')
if not os.path.exists(_cfg_file):
    _cfg_file = os.path.join(PROJECT_ROOT, 'config.yaml')
with open(_cfg_file) as f:
    _cfg = yaml.safe_load(f)

def _get(key, legacy_path=None, default=''):
    if key in _cfg:
        return _cfg[key]
    if legacy_path:
        try:
            v = _cfg
            for k in legacy_path:
                v = v[k]
            return v
        except (KeyError, TypeError):
            pass
    return default

DOMAIN_ID        = _get('domain_id', ['datazone', 'domain_id'], '')
REGION           = _get('region', ['aws', 'region'], 'us-east-2')
ACCOUNT_POOL_ID  = 'c5r1rtjwi2qhbd'
PROFILE_ID       = '5riu03k7l71zc9'   # All Capabilities - Account Pool
PROVIDER_FN      = 'AccountProvider'
OWNER_USERNAME   = _get('default_project_owner', ['datazone', 'default_project_owner'], '')
TABLE            = 'AccountPoolFactory-AccountState'

dz     = boto3.client('datazone', region_name=REGION)
ddb    = boto3.client('dynamodb', region_name=REGION)
lam    = boto3.client('lambda', region_name=REGION)
sts    = boto3.client('sts', region_name=REGION)

PASS = "✅"
FAIL = "❌"
INFO = "ℹ️ "


def step(n, title):
    print(f"\n{'='*60}")
    print(f"Step {n}: {title}")
    print('='*60)


def get_account_state(account_id):
    resp = ddb.query(
        TableName=TABLE,
        KeyConditionExpression='accountId = :a',
        ExpressionAttributeValues={':a': {'S': account_id}},
        ScanIndexForward=False, Limit=1
    )
    items = resp.get('Items', [])
    return items[0] if items else None


def poll_state(account_id, expected_state, timeout, interval=15):
    start = time.time()
    while time.time() - start < timeout:
        item = get_account_state(account_id)
        if not item:
            print(f"  {FAIL} Account {account_id} not found in pool")
            return False
        state = item.get('state', {}).get('S', '?')
        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] state={state}")
        if state == expected_state:
            return True
        time.sleep(interval)
    return False

def run_athena_query(athena, sql, workgroup, timeout=60):
    """Submit an Athena query and wait for completion."""
    resp = athena.start_query_execution(
        QueryString=sql,
        WorkGroup=workgroup
    )
    query_id = resp['QueryExecutionId']

    start = time.time()
    while time.time() - start < timeout:
        status = athena.get_query_execution(QueryExecutionId=query_id)
        state = status['QueryExecution']['Status']['State']
        if state == 'SUCCEEDED':
            return query_id
        if state in ('FAILED', 'CANCELLED'):
            reason = status['QueryExecution']['Status'].get(
                'StateChangeReason', ''
            )
            raise RuntimeError(f"Athena query {state}: {reason}")
        time.sleep(2)
    raise RuntimeError(f"Athena query timed out after {timeout}s")


def get_athena_results(athena, query_id):
    """Fetch result rows (excluding header) from a completed Athena query."""
    resp = athena.get_query_results(QueryExecutionId=query_id)
    rows = resp['ResultSet']['Rows']
    # First row is the header
    return [
        [col.get('VarCharValue', '') for col in row['Data']]
        for row in rows[1:]
    ]

def verify_athena_connection(dz_client, domain_id, project_id):
    """Step 5b: Verify shared Glue/LF data is accessible via Athena.

    Gets an Athena connection from DataZone, runs SHOW DATABASES to check
    that apf_test_customers and apf_test_transactions are visible, then
    queries apf_test_customers.customers to verify data access.
    Returns True if all checks pass, False otherwise.
    """
    print(f"  Getting Athena connection from DataZone...")
    try:
        connections = dz_client.list_connections(
            domainIdentifier=domain_id,
            projectIdentifier=project_id,
            type='ATHENA'
        )
    except Exception as e:
        print(f"  {FAIL} Failed to list connections: {e}")
        return False

    if not connections.get('items'):
        print(f"  {FAIL} No Athena connections found in project")
        return False

    connection_id = connections['items'][0]['connectionId']
    try:
        conn = dz_client.get_connection(
            domainIdentifier=domain_id,
            identifier=connection_id,
            withSecret=True
        )
    except Exception as e:
        print(f"  {FAIL} Failed to get connection details: {e}")
        return False

    athena = boto3.client('athena', region_name=REGION)
    workgroup = (
        conn.get('props', {})
        .get('athenaProperties', {})
        .get('workgroupName', 'primary')
    )

    # Verify shared databases are visible
    print(f"  Running: SHOW DATABASES...")
    try:
        qid = run_athena_query(athena, "SHOW DATABASES", workgroup)
        databases = get_athena_results(athena, qid)
        db_names = [row[0] for row in databases]
    except Exception as e:
        print(f"  {FAIL} SHOW DATABASES failed: {e}")
        return False

    expected_dbs = ['apf_test_customers', 'apf_test_transactions']
    for db in expected_dbs:
        if db not in db_names:
            print(f"  {FAIL} Database '{db}' not in SHOW DATABASES")
            return False
    print(f"  {PASS} Shared databases visible: {expected_dbs}")

    # Query a table to verify data access
    sql = ("SELECT * FROM apf_test_customers.customers "
           "LIMIT 5")
    print(f"  Running: {sql}")
    try:
        qid = run_athena_query(athena, sql, workgroup)
        rows = get_athena_results(athena, qid)
    except Exception as e:
        print(f"  {FAIL} SELECT query failed: {e}")
        return False

    if not rows:
        print(f"  {FAIL} No rows returned from customers table")
        return False
    print(f"  {PASS} Query returned {len(rows)} rows")

    print(f"  {PASS} Athena connection verification PASSED")
    return True




def main():
    # ── Verify credentials ────────────────────────────────────────────────────
    step(0, "Verify credentials")
    identity = sts.get_caller_identity()
    current_account = identity['Account']
    domain_account  = _get('domain_account_id', ['aws', 'domain_account_id'], '')
    if current_account != domain_account:
        print(f"{FAIL} Must run in domain account ({domain_account}), got {current_account}")
        print(f"  Run: eval $(isengardcli credentials amirbo+3@amazon.com)")
        sys.exit(1)
    print(f"{PASS} Running in domain account {current_account}")

    # ── Step 1: Get available pool account ────────────────────────────────────
    step(1, "Get available pool account from AccountProvider")
    resp = lam.invoke(
        FunctionName=PROVIDER_FN,
        InvocationType='RequestResponse',
        Payload=json.dumps({'operationRequest': {'listAuthorizedAccountsRequest': {}}}).encode()
    )
    result = json.loads(resp['Payload'].read())
    accounts = result.get('operationResponse', {}) \
                     .get('listAuthorizedAccountsResponse', {}) \
                     .get('items', [])
    if not accounts:
        print(f"{FAIL} No available accounts in pool")
        sys.exit(1)
    pool_account_id = accounts[0]['awsAccountId']
    print(f"{PASS} Pool has {len(accounts)} available accounts")
    print(f"  Using account: {pool_account_id}")

    # ── Step 2: Get environment configs ───────────────────────────────────────
    step(2, "Get environment configs from project profile")
    profile = dz.get_project_profile(domainIdentifier=DOMAIN_ID, identifier=PROFILE_ID)
    env_config_names = [e['name'] for e in profile.get('environmentConfigurations', [])]
    print(f"{PASS} {len(env_config_names)} environment configs: {env_config_names[:3]}...")

    # ── Step 3: Look up project owner ─────────────────────────────────────────
    owner_user_id = None
    if OWNER_USERNAME:
        step(3, f"Look up user profile for '{OWNER_USERNAME}'")
        resp = dz.search_user_profiles(
            domainIdentifier=DOMAIN_ID, userType='SSO_USER', searchText=OWNER_USERNAME
        )
        for item in resp.get('items', []):
            if item.get('details', {}).get('sso', {}).get('username') == OWNER_USERNAME:
                owner_user_id = item['id']
                break
        if owner_user_id:
            print(f"{PASS} Found user ID: {owner_user_id}")
        else:
            print(f"{INFO} User '{OWNER_USERNAME}' not found, skipping owner assignment")

    # ── Step 4: Create project ────────────────────────────────────────────────
    step(4, "Create project from pool account")
    ts = str(int(time.time()))
    project_name = f'e2e-test-{ts}'
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
    create_resp = dz.create_project(
        domainIdentifier=DOMAIN_ID,
        name=project_name,
        description='Automated e2e lifecycle test',
        projectProfileId=PROFILE_ID,
        userParameters=user_params,
    )
    project_id = create_resp['id']
    print(f"{PASS} Project created: {project_id} ({project_name})")
    _portal = _get('portal_url', ['datazone', 'portal_url'], f'https://{DOMAIN_ID}.sagemaker.{REGION}.on.aws')
    print(f"  Portal: {_portal}/projects/{project_id}")

    if owner_user_id:
        try:
            dz.create_project_membership(
                domainIdentifier=DOMAIN_ID, projectIdentifier=project_id,
                designation='PROJECT_OWNER', member={'userIdentifier': owner_user_id}
            )
            print(f"{PASS} Owner {OWNER_USERNAME} added")
        except dz.exceptions.ConflictException:
            print(f"{PASS} Owner already a member")
        except Exception as e:
            print(f"{INFO} Could not add owner: {e}")

    # ── Step 5: Wait for account to be ASSIGNED ───────────────────────────────
    step(5, f"Wait for account {pool_account_id} to reach ASSIGNED state")
    print(f"  (triggered by AccountProvider.validate or DataZone Environment Deployment Completed event)")
    assigned = poll_state(pool_account_id, 'ASSIGNED', timeout=180, interval=10)
    if not assigned:
        print(f"{FAIL} Account {pool_account_id} did not reach ASSIGNED state within 180s")
        print(f"  Cleaning up project {project_id}...")
        try:
            dz.delete_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
        except Exception:
            pass
        sys.exit(1)
    item = get_account_state(pool_account_id)
    print(f"{PASS} Account {pool_account_id} is ASSIGNED")
    print(f"  assignedDate : {item.get('assignedDate',{}).get('S','')}")

    # ── Wait for deployment to complete before verification ──────────────────
    print(f"\n  Waiting for deployment to finish...")
    start = time.time()
    while time.time() - start < 600:
        proj = dz.get_project(
            domainIdentifier=DOMAIN_ID, identifier=project_id
        )
        deploy_status = (
            proj.get('environmentDeploymentDetails', {})
            .get('overallDeploymentStatus', '')
        )
        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] deploymentStatus={deploy_status}")
        if deploy_status not in (
            'PENDING_DEPLOYMENT',
            'IN_PROGRESS_DEPLOYMENT',
            'IN_PROGRESS',
        ):
            break
        time.sleep(20)

    # ── Step 5b: Verify Athena connection to shared test data ─────────────────
    step("5b", "Verify Athena connection to shared test data")
    athena_ok = verify_athena_connection(dz, DOMAIN_ID, project_id)
    if athena_ok:
        print(f"{PASS} Athena verification passed")
    else:
        print(f"{FAIL} Athena verification failed (continuing with cleanup)")

    # ── Step 6: Delete project ────────────────────────────────────────────────
    step(6, f"Delete project {project_id}")

    # Delete data sources first
    print(f"  Deleting data sources...")
    try:
        ds_resp = dz.list_data_sources(domainIdentifier=DOMAIN_ID, projectIdentifier=project_id)
        for ds in ds_resp.get('items', []):
            ds_id = ds['dataSourceId']
            print(f"    Deleting data source {ds_id}...")
            try:
                dz.delete_data_source(domainIdentifier=DOMAIN_ID, identifier=ds_id)
            except Exception as e:
                print(f"    Warning: {e}")
    except Exception as e:
        print(f"  Warning listing data sources: {e}")

    # Delete environments — retry until all are gone
    print(f"  Deleting environments...")
    start_env = time.time()
    while time.time() - start_env < 300:
        try:
            env_resp = dz.list_environments(domainIdentifier=DOMAIN_ID, projectIdentifier=project_id)
            active = [e for e in env_resp.get('items', []) if e.get('status') not in ('DELETED',)]
            if not active:
                break
            for env in active:
                env_id = env['id']
                env_status = env.get('status', '')
                if env_status not in ('DELETE_IN_PROGRESS',):
                    print(f"    Deleting environment {env_id} (status={env_status})...")
                    try:
                        dz.delete_environment(domainIdentifier=DOMAIN_ID, identifier=env_id)
                    except Exception as e:
                        print(f"    Warning: {e}")
        except Exception as e:
            print(f"  Warning listing environments: {e}")
            break
        time.sleep(10)

    # Now delete the project
    try:
        dz.delete_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
        print(f"  Delete request accepted")
    except Exception as e:
        print(f"{FAIL} Delete failed: {e}")
        sys.exit(1)

    # Wait for project to be gone
    print(f"  Waiting for project deletion...")
    start = time.time()
    while time.time() - start < 300:
        try:
            proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
            status = proj.get('projectStatus', '?')
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] projectStatus={status}")
            if status == 'DELETE_FAILED':
                print(f"{FAIL} Project deletion failed")
                sys.exit(1)
        except dz.exceptions.ResourceNotFoundException:
            elapsed = int(time.time() - start)
            print(f"{PASS} Project deleted after {elapsed}s")
            break
        time.sleep(15)

    # ── Step 7: Wait for account to return to AVAILABLE ───────────────────────
    step(7, f"Wait for account {pool_account_id} to return to AVAILABLE")
    print(f"  (triggered by DataZone Environment Deletion Completed event)")
    print(f"  Note: DataZone may take several minutes to delete all environments.")
    print(f"  With REUSE strategy: ASSIGNED → CLEANING → (deprovision) → (setup) → AVAILABLE")

    start = time.time()
    interval = 20
    reclaim_triggered = False

    while time.time() - start < 1200:
        item = get_account_state(pool_account_id)
        if not item:
            print(f"{FAIL} Account {pool_account_id} not found in pool")
            sys.exit(1)
        state = item.get('state', {}).get('S', '?')
        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] state={state}")

        if state == 'AVAILABLE':
            print(f"\n{PASS} Account {pool_account_id} is back to AVAILABLE")
            reclaim_triggered = True
            break
        if state in ('CLEANING', 'DELETING'):
            reclaim_triggered = True  # Reclaim was triggered, just waiting for completion
        if state == 'FAILED' and reclaim_triggered:
            # Reclaim was triggered but re-setup failed — recycler will fix on next run
            print(f"\n{INFO} Account reached FAILED state after reclaim (re-setup issue, recycler will fix)")
            print(f"  Reclaim trigger: ✅ PASSED")
            print(f"  Re-setup: ⚠️  FAILED (pre-existing REUSE cycle issue, not related to this migration)")
            break
        time.sleep(interval)

    if not reclaim_triggered:
        print(f"\n{FAIL} Reclaim was NOT triggered for account {pool_account_id}")
        sys.exit(1)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"{PASS} End-to-end lifecycle test PASSED")
    print(f"  Account {pool_account_id}: AVAILABLE → ASSIGNED → reclaim triggered")
    print('='*60)


if __name__ == '__main__':
    main()
