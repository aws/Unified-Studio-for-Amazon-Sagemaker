#!/usr/bin/env python3
"""Debug a project's deployment status, account, and environment details."""
import boto3, json

DOMAIN_ID = 'dzd-4h7jbz76qckoh5'
REGION = 'us-east-2'
PROJECT_ID = 'ccs8js7cy92p7t'

dz = boto3.client('datazone', region_name=REGION)
ddb = boto3.client('dynamodb', region_name=REGION)

# 1. Project details
print("=== Project Details ===")
proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=PROJECT_ID)
print(f"  Name: {proj['name']}")
print(f"  Status: {proj.get('projectStatus', '?')}")
deploy = proj.get('environmentDeploymentDetails', {})
print(f"  Deployment: {deploy.get('overallDeploymentStatus', '?')}")
env_failures = deploy.get('environmentFailureReasons', {})
for env_name, reasons in env_failures.items():
    for r in reasons:
        print(f"  FAILURE [{env_name}]: {r.get('message','')}")

# 2. Environment details — get the account ID
print("\n=== Environments ===")
envs = dz.list_environments(domainIdentifier=DOMAIN_ID, projectIdentifier=PROJECT_ID)
assigned_account = None
for env in envs.get('items', []):
    print(f"  {env['id']}: name={env['name']} status={env.get('status','?')}")
    try:
        detail = dz.get_environment(domainIdentifier=DOMAIN_ID, identifier=env['id'])
        acct = detail.get('awsAccountId', '?')
        region = detail.get('awsAccountRegion', '?')
        print(f"    account={acct} region={region}")
        if acct != '?':
            assigned_account = acct
        # Check provisioned resources
        prov = detail.get('provisionedResources', [])
        if prov:
            print(f"    provisionedResources: {len(prov)}")
        # Check last deployment
        last_dep = detail.get('lastDeployment', {})
        if last_dep:
            print(f"    lastDeployment: status={last_dep.get('deploymentStatus','?')} reason={last_dep.get('failureReason',{}).get('message','')[:200]}")
    except Exception as e:
        print(f"    detail error: {e}")

# 3. Check account state in DynamoDB
if assigned_account:
    print(f"\n=== Account {assigned_account} in DynamoDB ===")
    resp = ddb.query(
        TableName='AccountPoolFactory-AccountState',
        KeyConditionExpression='accountId = :a',
        ExpressionAttributeValues={':a': {'S': assigned_account}},
        ScanIndexForward=False, Limit=1
    )
    if resp.get('Items'):
        item = resp['Items'][0]
        print(f"  state: {item.get('state',{}).get('S','?')}")
        ds = [e.get('S','') for e in item.get('deployedStackSets',{}).get('L',[])]
        print(f"  deployedStackSets: {ds}")
        resources = {}
        for k, v in item.get('resources', {}).get('M', {}).items():
            resources[k] = v.get('S', '?')
        print(f"  resources.vpcId: {resources.get('vpcId','?')}")
        print(f"  resources.manageAccessRoleArn: {resources.get('manageAccessRoleArn','?')}")
        print(f"  resources.blueprintIds: {resources.get('blueprintIds','?')[:100]}")

# 4. Members
print(f"\n=== Members ===")
members = dz.list_project_memberships(domainIdentifier=DOMAIN_ID, projectIdentifier=PROJECT_ID)
for m in members.get('members', []):
    designation = m.get('designation', '?')
    member = m.get('member', {})
    user_id = member.get('userIdentifier', '?')
    print(f"  {designation}: userId={user_id}")
if not members.get('members'):
    print("  (no members)")
