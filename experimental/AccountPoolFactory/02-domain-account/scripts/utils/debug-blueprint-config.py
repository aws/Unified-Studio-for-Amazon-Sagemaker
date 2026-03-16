#!/usr/bin/env python3
"""Compare Tooling blueprint config between failing and working accounts."""
import boto3, json

REGION = 'us-east-2'
DOMAIN_ID = 'dzd-4h7jbz76qckoh5'
TOOLING_BP = '3owsbi7jjppvc9'

sts = boto3.client('sts', region_name=REGION)

def check_account(acct_id, label):
    print(f"\n=== {label}: Account {acct_id} ===")
    creds = sts.assume_role(
        RoleArn=f'arn:aws:iam::{acct_id}:role/SMUS-AccountPoolFactory-DomainAccess',
        RoleSessionName='debug-bp', ExternalId=DOMAIN_ID, DurationSeconds=900
    )['Credentials']
    dz = boto3.client('datazone', region_name=REGION,
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken'])
    try:
        cfg = dz.get_environment_blueprint_configuration(
            domainIdentifier=DOMAIN_ID,
            environmentBlueprintIdentifier=TOOLING_BP
        )
        print(f"  enabledRegions: {cfg.get('enabledRegions')}")
        print(f"  manageAccessRoleArn: {cfg.get('manageAccessRoleArn','?')}")
        print(f"  provisioningRoleArn: {cfg.get('provisioningRoleArn','?')}")
        rp = cfg.get('regionalParameters', {})
        print(f"  regionalParameters: {json.dumps(rp, indent=4)}")
    except Exception as e:
        print(f"  ERROR: {e}")

check_account('476383094227', 'FAILING (new StackSet)')
check_account('359642223527', 'WORKING (new StackSet, AVAILABLE)')
