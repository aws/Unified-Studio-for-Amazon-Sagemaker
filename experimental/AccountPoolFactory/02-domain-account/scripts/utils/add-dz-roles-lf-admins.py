#!/usr/bin/env python3
"""
One-time fix: Add datazone_usr_role_* as LF admins in all AVAILABLE pool accounts.

TEMPORARY WORKAROUND for Lake Formation resource link visibility.
Resource links require local LF grants, but we don't know project role names
at StackSet deploy time. This script discovers datazone_usr_role_* roles and
adds them as LF admins so they can see shared databases.

Going forward, SetupOrchestrator handles this automatically for new accounts.

Usage:
    eval $(isengardcli credentials amirbo+3@amazon.com)
    python3 02-domain-account/scripts/utils/add-dz-roles-lf-admins.py
    python3 02-domain-account/scripts/utils/add-dz-roles-lf-admins.py --dry-run
"""
import sys
import argparse
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed

REGION = 'us-east-2'
DOMAIN_ID = 'dzd-4h7jbz76qckoh5'
TABLE_NAME = 'AccountPoolFactory-AccountState'

sts = boto3.client('sts', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def get_available_accounts():
    """Get all AVAILABLE account IDs from DynamoDB."""
    response = table.scan()
    items = response['Items']
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response['Items'])

    latest = {}
    for item in items:
        aid = item['accountId']
        ts = item.get('timestamp', '')
        if aid not in latest or ts > latest[aid].get('timestamp', ''):
            latest[aid] = item

    return [aid for aid, item in latest.items() if item.get('state') == 'AVAILABLE']


def fix_account(acct, dry_run=False):
    """Add datazone_usr_role_* as LF admins in one account."""
    try:
        creds = sts.assume_role(
            RoleArn=f'arn:aws:iam::{acct}:role/SMUS-AccountPoolFactory-DomainAccess',
            RoleSessionName='add-dz-lf-admin',
            ExternalId=DOMAIN_ID,
            DurationSeconds=900
        )['Credentials']

        kwargs = dict(aws_access_key_id=creds['AccessKeyId'],
                      aws_secret_access_key=creds['SecretAccessKey'],
                      aws_session_token=creds['SessionToken'],
                      region_name=REGION)

        iam = boto3.client('iam', **kwargs)
        lf = boto3.client('lakeformation', **kwargs)

        # Discover datazone_usr_role_* roles
        dz_roles = []
        paginator = iam.get_paginator('list_roles')
        for page in paginator.paginate(PathPrefix='/'):
            for role in page['Roles']:
                if role['RoleName'].startswith('datazone_usr_role_'):
                    dz_roles.append(role['Arn'])

        if not dz_roles:
            return acct, 'SKIP', 'no datazone_usr_role found'

        # Get current LF admins
        settings = lf.get_data_lake_settings()
        admins = settings['DataLakeSettings'].get('DataLakeAdmins', [])
        admin_arns = set(a['DataLakePrincipalIdentifier'] for a in admins)

        to_add = [r for r in dz_roles if r not in admin_arns]
        if not to_add:
            return acct, 'OK', f'{len(dz_roles)} roles already admins'

        if dry_run:
            return acct, 'DRY-RUN', f'would add {len(to_add)} roles'

        for arn in to_add:
            admins.append({'DataLakePrincipalIdentifier': arn})
        settings['DataLakeSettings']['DataLakeAdmins'] = admins
        lf.put_data_lake_settings(DataLakeSettings=settings['DataLakeSettings'])

        return acct, 'FIXED', f'added {len(to_add)} roles as LF admins'

    except Exception as e:
        return acct, 'ERROR', str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    accounts = get_available_accounts()
    print(f"Found {len(accounts)} AVAILABLE accounts")

    fixed = errors = skipped = ok = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(fix_account, a, args.dry_run): a for a in accounts}
        for f in as_completed(futures):
            acct, status, msg = f.result()
            if status == 'FIXED':
                fixed += 1
                print(f"  ✅ {acct}: {msg}")
            elif status == 'ERROR':
                errors += 1
                print(f"  ❌ {acct}: {msg}")
            elif status == 'SKIP':
                skipped += 1
            elif status == 'DRY-RUN':
                fixed += 1
                print(f"  🔍 {acct}: {msg}")
            else:
                ok += 1

    print(f"\nDone: {fixed} fixed, {ok} already ok, {skipped} skipped (no roles), {errors} errors")


if __name__ == '__main__':
    main()
