#!/usr/bin/env python3
"""
Fix the trust policy on SMUS-AccountPoolFactory-StackSetExecution in all pool accounts.
The role must trust the current StackSetAdmin role ARN (not a stale role ID).

Usage:
    eval $(isengardcli credentials amirbo+1@amazon.com)
    python3 scripts/utils/fix-stackset-execution-trust.py [--dry-run]
"""
import sys, json, time, argparse, boto3
from concurrent.futures import ThreadPoolExecutor, as_completed

REGION           = 'us-east-2'
EXEC_ROLE        = 'SMUS-AccountPoolFactory-StackSetExecution'
ADMIN_ROLE_NAME  = 'SMUS-AccountPoolFactory-StackSetAdmin'
ORG_ACCOUNT      = '495869084367'

sts = boto3.client('sts')
ddb = boto3.client('dynamodb', region_name=REGION)

CORRECT_TRUST = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {
            "AWS": f"arn:aws:iam::{ORG_ACCOUNT}:role/{ADMIN_ROLE_NAME}"
        },
        "Action": "sts:AssumeRole"
    }]
}


def get_pool_accounts():
    """Get pool account IDs from AWS Organizations (OU scan)."""
    org = boto3.client('organizations')
    # Get accounts from the target OU
    OU_ID = 'ou-n5om-otvkrtx2'  # RetailBanking/CustomerAnalytics OU
    accounts = []
    paginator = org.get_paginator('list_accounts_for_parent')
    for page in paginator.paginate(ParentId=OU_ID):
        accounts.extend([a['Id'] for a in page['Accounts'] if a['Status'] == 'ACTIVE'])
    return accounts


def fix_account(account_id, dry_run):
    try:
        creds = sts.assume_role(
            RoleArn=f'arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole',
            RoleSessionName='fix-stackset-trust'
        )['Credentials']
        iam = boto3.client('iam',
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken'])

        current = iam.get_role(RoleName=EXEC_ROLE)['Role']['AssumeRolePolicyDocument']
        # Check if already correct
        stmts = current.get('Statement', [])
        if stmts and stmts[0].get('Principal', {}).get('AWS', '').endswith(ADMIN_ROLE_NAME):
            return account_id, 'already_correct'

        if not dry_run:
            iam.update_assume_role_policy(
                RoleName=EXEC_ROLE,
                PolicyDocument=json.dumps(CORRECT_TRUST)
            )
        return account_id, 'fixed'
    except Exception as e:
        return account_id, f'error: {e}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    accounts = get_pool_accounts()
    print(f"Fixing trust policy on {len(accounts)} accounts (dry_run={args.dry_run})")

    results = {'fixed': 0, 'already_correct': 0, 'error': 0}
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(fix_account, a, args.dry_run): a for a in accounts}
        for f in as_completed(futures):
            acct, status = f.result()
            if status.startswith('error'):
                print(f"  ❌ {acct}: {status}")
                results['error'] += 1
            elif status == 'fixed':
                results['fixed'] += 1
            else:
                results['already_correct'] += 1

    print(f"\nDone: fixed={results['fixed']} already_correct={results['already_correct']} errors={results['error']}")
    if results['error']:
        sys.exit(1)


if __name__ == '__main__':
    main()
