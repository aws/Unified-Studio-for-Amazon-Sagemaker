#!/usr/bin/env python3
"""
Verify accounts are clean after cleanupStacks.
Spot-checks 5 accounts: confirms DynamoDB has no setup fields
and only StackSet-managed stacks remain in the account.

Usage:
    eval $(isengardcli credentials amirbo+3@amazon.com)
    python3 02-domain-account/scripts/utils/verify-cleanup.py
"""
import boto3, json, random

REGION    = 'us-east-2'
DOMAIN_ID = 'dzd-4h7jbz76qckoh5'
TABLE     = 'AccountPoolFactory-AccountState'

ddb = boto3.client('dynamodb', region_name=REGION)
sts = boto3.client('sts', region_name=REGION)

# Fields that should be absent after reset
CLEARED_FIELDS = ['deployedStackSets', 'resources', 'completedSteps',
                  'setupCompleteDate', 'errorMessage', 'failedStep']

def get_available_sample(n=5):
    resp = ddb.query(
        TableName=TABLE,
        IndexName='StateIndex',
        KeyConditionExpression='#s = :s',
        ExpressionAttributeNames={'#s': 'state'},
        ExpressionAttributeValues={':s': {'S': 'AVAILABLE'}},
        Limit=50
    )
    items = resp.get('Items', [])
    return random.sample(items, min(n, len(items)))

def check_cf_stacks(account_id):
    # Uses currently active credentials (must be org-admin)
    creds = sts.assume_role(
        RoleArn=f'arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole',
        RoleSessionName='verify-cleanup'
    )['Credentials']
    cf = boto3.client('cloudformation', region_name=REGION,
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken'])
    stacks = cf.list_stacks(StackStatusFilter=['CREATE_COMPLETE','UPDATE_COMPLETE'])
    return [s['StackName'] for s in stacks.get('StackSummaries', [])]

def main():
    # DynamoDB is in domain account — detect which account we're in
    caller = sts.get_caller_identity()
    current = caller['Account']
    domain_account = '994753223772'
    org_account    = '495869084367'

    sample = []
    if current == domain_account:
        sample = get_available_sample(5)
        print(f"Spot-checking {len(sample)} AVAILABLE accounts (DynamoDB check)\n")
        for item in sample:
            acct_id = item['accountId']['S']
            name    = item.get('accountName', {}).get('S', '')
            print(f"Account: {acct_id} ({name})")
            ddb_ok = True
            for field in CLEARED_FIELDS:
                if field in item:
                    print(f"  ❌ DynamoDB still has '{field}'")
                    ddb_ok = False
            if ddb_ok:
                print(f"  ✅ DynamoDB cleared")
            print()
        print("Re-run with org-admin creds to check CF stacks.")

    elif current == org_account:
        # Get account IDs from DynamoDB isn't available here — use a fixed sample
        # or pass account IDs as args
        import sys
        acct_ids = sys.argv[1:] if len(sys.argv) > 1 else []
        if not acct_ids:
            print("Usage with org-admin creds: python3 verify-cleanup.py <acct1> <acct2> ...")
            return
        print(f"Checking CF stacks for {len(acct_ids)} accounts\n")
        for acct_id in acct_ids:
            print(f"Account: {acct_id}")
            try:
                stacks = check_cf_stacks(acct_id)
                direct    = [s for s in stacks if s.startswith('DataZone-')]
                stackset  = [s for s in stacks if s.startswith('StackSet-SMUS-')]
                execution = [s for s in stacks if 'StackSetExecution' in s]
                if direct:
                    print(f"  ❌ Direct CF stacks still present: {direct}")
                else:
                    print(f"  ✅ No direct CF stacks")
                print(f"  StackSet stacks: {stackset}")
                print(f"  Execution role:  {execution}")
            except Exception as e:
                print(f"  ⚠️  Error: {e}")
            print()
    else:
        print(f"Unknown account {current}. Use domain or org-admin creds.")

if __name__ == '__main__':
    main()
