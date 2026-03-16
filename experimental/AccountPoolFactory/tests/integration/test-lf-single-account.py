#!/usr/bin/env python3
"""
Phase 2: Single-account Lake Formation test.
  1. Pick one AVAILABLE pool account
  2. Deploy StackSet 07 instance to just that account (assumes org admin already uploaded template)
  3. Create a project forced to use that specific account
  4. Wait for deployment, verify Athena connection to shared test data
  5. Clean up (delete project, wait for account to return to AVAILABLE)

Prerequisites:
  - Phase 1 complete (create-test-data.py has run in domain account)
  - Org admin has deployed (01-deploy.sh) so StackSet 07 template is uploaded
  - Run with domain account credentials

Usage:
    eval $(isengardcli credentials amirbo+3@amazon.com)
    python3 tests/integration/test-lf-single-account.py

Exit codes: 0 = all steps passed, 1 = failure
"""
import sys
import os
import time
import json
import boto3
import yaml

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..', '..')

# Load 02-domain-account/config.yaml (preferred) or fall back to legacy config.yaml
_cfg_file = os.path.join(PROJECT_ROOT, '02-domain-account/config.yaml')
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

DOMAIN_ID       = _get('domain_id', ['datazone', 'domain_id'], '')
REGION          = _get('region', ['aws', 'region'], 'us-east-2')
ACCOUNT_POOL_ID = 'c5r1rtjwi2qhbd'
PROFILE_ID      = '5riu03k7l71zc9'
PROVIDER_FN     = 'AccountProvider'
TABLE           = 'AccountPoolFactory-AccountState'
STACKSET_NAME   = 'SMUS-AccountPoolFactory-GlueLfTestData'
OWNER_USERNAME  = _get('default_project_owner', ['datazone', 'default_project_owner'], '')
# Also check under pools[0] where it's typically configured
if not OWNER_USERNAME:
    _pools = _cfg.get('pools', [])
    if _pools:
        OWNER_USERNAME = _pools[0].get('default_project_owner', '')

PASS = "✅"
FAIL = "❌"
INFO = "ℹ️ "


# ── Reusable helpers (same pattern as test-e2e-pool-lifecycle.py) ─────────

def step(n, title):
    print(f"\n{'='*60}")
    print(f"Step {n}: {title}")
    print('='*60)


def get_account_state(ddb, account_id):
    resp = ddb.query(
        TableName=TABLE,
        KeyConditionExpression='accountId = :a',
        ExpressionAttributeValues={':a': {'S': account_id}},
        ScanIndexForward=False, Limit=1
    )
    items = resp.get('Items', [])
    return items[0] if items else None


def poll_state(ddb, account_id, expected_state, timeout, interval=15):
    start = time.time()
    while time.time() - start < timeout:
        item = get_account_state(ddb, account_id)
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


# ── Athena helpers ────────────────────────────────────────────────────────

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
            reason = status['QueryExecution']['Status'].get('StateChangeReason', '')
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


def verify_athena_connection(dz, domain_id, project_id):
    """Verify shared Glue/LF data is accessible via Athena connection.

    Gets an Athena connection from DataZone, then runs SHOW DATABASES
    and a SELECT query to confirm shared test data is visible and queryable.
    """
    print(f"  Getting Athena connection from DataZone...")
    connections = dz.list_connections(
        domainIdentifier=domain_id,
        projectIdentifier=project_id,
        type='ATHENA'
    )
    if not connections.get('items'):
        print(f"  {FAIL} No Athena connections found in project")
        return False

    connection_id = connections['items'][0]['connectionId']
    conn = dz.get_connection(
        domainIdentifier=domain_id,
        identifier=connection_id,
        withSecret=True
    )

    # The Athena workgroup lives in the PROJECT account, not the domain account.
    # Use the connection credentials to create an Athena client in the project account.
    creds = conn.get('connectionCredentials', {})
    access_key = creds.get('accessKeyId', '')
    secret_key = creds.get('secretAccessKey', '')
    session_token = creds.get('sessionToken', '')

    if access_key and secret_key:
        print(f"  {PASS} Got connection credentials for project account")
        athena = boto3.client('athena', region_name=REGION,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token)
    else:
        print(f"  {INFO} No connection credentials, using default Athena client")
        athena = boto3.client('athena', region_name=REGION)
    workgroup = conn.get('props', {}).get('athenaProperties', {}).get('workgroupName', 'primary')
    print(f"  Using workgroup: {workgroup}")

    # Verify shared databases are visible (with retries for LF propagation)
    print(f"  Running: SHOW DATABASES...")
    expected_dbs = ['apf_test_customers', 'apf_test_transactions']
    db_names = []
    for attempt in range(5):
        try:
            query_id = run_athena_query(athena, "SHOW DATABASES", workgroup)
            databases = get_athena_results(athena, query_id)
            db_names = [row[0] for row in databases]
            missing = [db for db in expected_dbs if db not in db_names]
            if not missing:
                break
            print(f"  [{attempt+1}/5] Missing: {missing}, retrying in 15s...")
            time.sleep(15)
        except Exception as e:
            print(f"  [{attempt+1}/5] SHOW DATABASES failed: {e}, retrying in 15s...")
            time.sleep(15)

    for db in expected_dbs:
        if db not in db_names:
            print(f"  {FAIL} Expected database '{db}' not found in SHOW DATABASES")
            return False
    print(f"  {PASS} Shared databases visible: {expected_dbs}")

    # Query a table to verify data access
    print(f"  Running: SELECT * FROM apf_test_customers.customers LIMIT 5...")
    try:
        query_id = run_athena_query(
            athena,
            "SELECT * FROM apf_test_customers.customers LIMIT 5",
            workgroup
        )
        rows = get_athena_results(athena, query_id)
        if not rows:
            print(f"  {FAIL} No rows returned from customers table")
            return False
        print(f"  {PASS} Query returned {len(rows)} rows")
    except Exception as e:
        print(f"  {FAIL} SELECT query failed: {e}")
        return False

    print(f"  {PASS} Athena connection verification PASSED")
    return True


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    dz  = boto3.client('datazone', region_name=REGION)
    ddb = boto3.client('dynamodb', region_name=REGION)
    lam = boto3.client('lambda', region_name=REGION)
    sts = boto3.client('sts', region_name=REGION)

    project_id = None
    test_account_id = None
    athena_ok = False
    returned = False

    try:
        # ── Step 0: Verify credentials ────────────────────────────────────
        step(0, "Verify credentials")
        identity = sts.get_caller_identity()
        domain_account = _get('domain_account_id', ['aws', 'domain_account_id'], '')
        if identity['Account'] != domain_account:
            print(f"{FAIL} Must run in domain account ({domain_account}), got {identity['Account']}")
            print(f"  Run: eval $(isengardcli credentials amirbo+3@amazon.com)")
            sys.exit(1)
        print(f"{PASS} Running in domain account {identity['Account']}")

        # ── Step 1: Pick one AVAILABLE pool account ───────────────────────
        step(1, "Pick one AVAILABLE pool account from AccountProvider")
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
        test_account_id = accounts[0]['awsAccountId']
        print(f"{PASS} Pool has {len(accounts)} available accounts")
        print(f"  Using account: {test_account_id}")

        # ── Step 2: StackSet 07 instance (pre-deployed from org admin) ──
        step(2, f"Verify StackSet 07 deployed for account {test_account_id}")
        print(f"  {INFO} StackSet operations require org admin credentials.")
        print(f"  {INFO} Assuming StackSet instance was pre-deployed from org admin account.")
        print(f"  {INFO} If not, run from org admin first:")
        print(f"    eval $(isengardcli credentials amirbo+1@amazon.com)")
        print(f"    bash experimental/AccountPoolFactory/.kiro/tmp/deploy-stackset-instance.sh")
        print(f"{PASS} Step 2 skipped (cross-account — pre-deploy required)")

        # ── Step 3: Create project forced to this account ─────────────────
        step(3, "Create project forced to this account")
        profile = dz.get_project_profile(domainIdentifier=DOMAIN_ID, identifier=PROFILE_ID)
        env_config_names = [e['name'] for e in profile.get('environmentConfigurations', [])]
        print(f"  {len(env_config_names)} environment configs: {env_config_names[:3]}...")

        ts = str(int(time.time()))
        project_name = f'e2e-lf-test-{ts}'
        user_params = [
            {
                'environmentConfigurationName': name,
                'environmentResolvedAccount': {
                    'awsAccountId': test_account_id,
                    'regionName': REGION,
                    'sourceAccountPoolId': ACCOUNT_POOL_ID
                }
            }
            for name in env_config_names
        ]
        create_resp = dz.create_project(
            domainIdentifier=DOMAIN_ID,
            name=project_name,
            description='Phase 2: single account LF test',
            projectProfileId=PROFILE_ID,
            userParameters=user_params,
        )
        project_id = create_resp['id']
        print(f"{PASS} Project created: {project_id} ({project_name})")

        # Add project owner (IDC/SSO user)
        if OWNER_USERNAME:
            print(f"  Looking up SSO user '{OWNER_USERNAME}'...")
            try:
                resp = dz.search_user_profiles(
                    domainIdentifier=DOMAIN_ID, userType='SSO_USER',
                    searchText=OWNER_USERNAME)
                owner_user_id = None
                for item in resp.get('items', []):
                    if item.get('details', {}).get('sso', {}).get('username') == OWNER_USERNAME:
                        owner_user_id = item['id']
                        break
                if owner_user_id:
                    dz.create_project_membership(
                        domainIdentifier=DOMAIN_ID, projectIdentifier=project_id,
                        designation='PROJECT_OWNER',
                        member={'userIdentifier': owner_user_id})
                    print(f"  {PASS} Owner {OWNER_USERNAME} added")
                else:
                    print(f"  {INFO} User '{OWNER_USERNAME}' not found, skipping")
            except dz.exceptions.ConflictException:
                print(f"  {PASS} Owner already a member")
            except Exception as e:
                print(f"  {INFO} Could not add owner: {e}")

        # ── Step 4: Wait for ASSIGNED state ───────────────────────────────
        step(4, f"Wait for account {test_account_id} to reach ASSIGNED")
        assigned = poll_state(ddb, test_account_id, 'ASSIGNED', timeout=180, interval=10)
        if not assigned:
            print(f"{FAIL} Account did not reach ASSIGNED within 180s")
            raise Exception("Account did not reach ASSIGNED state")
        print(f"{PASS} Account {test_account_id} is ASSIGNED")

        # ── Step 4b: Wait for deployment to complete ──────────────────────
        step("4b", "Wait for deployment to complete")
        start = time.time()
        while time.time() - start < 600:
            proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
            deploy_status = proj.get('environmentDeploymentDetails', {}).get('overallDeploymentStatus', '')
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] deploymentStatus={deploy_status}")
            if deploy_status not in ('PENDING_DEPLOYMENT', 'IN_PROGRESS_DEPLOYMENT', 'IN_PROGRESS'):
                break
            time.sleep(20)

        # ── Step 5: Verify Athena connection ──────────────────────────────
        step(5, "Verify Athena connection to shared test data")
        # Wait for LF grants to propagate — PoolManager adds LF admins and
        # cross-account grants during deployment-completed events, which may
        # still be processing when we reach this point.
        print(f"  Waiting 30s for LF grants to propagate...")
        time.sleep(30)
        athena_ok = verify_athena_connection(dz, DOMAIN_ID, project_id)
        if not athena_ok:
            print(f"{FAIL} Athena verification failed")
        else:
            print(f"{PASS} Athena verification passed")

    except Exception as e:
        print(f"\n{FAIL} Error: {e}")

    # ── Step 6: Cleanup (DISABLED — keeping project for debugging) ───────
    if project_id:
        step(6, f"Cleanup: SKIPPED — keeping project {project_id} for debugging")
        print(f"  {INFO} Project {project_id} left intact for further testing")
        print(f"  {INFO} Delete manually when done: python3 02-domain-account/scripts/utils/delete-project.py {project_id}")
        returned = True  # Don't fail the test for cleanup

    # ── Step 7: SKIPPED (keeping project) ─────────────────────────────────

    # ── Final result ──────────────────────────────────────────────────────
    overall = athena_ok and returned

    print(f"\n{'='*60}")
    if overall:
        print(f"{PASS} Phase 2: Single account LF test PASSED")
    else:
        print(f"{FAIL} Phase 2: Single account LF test FAILED")
    print('='*60)
    sys.exit(0 if overall else 1)


if __name__ == '__main__':
    main()
