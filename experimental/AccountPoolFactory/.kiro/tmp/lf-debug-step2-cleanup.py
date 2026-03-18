#!/usr/bin/env python3
"""
Step 2: Clean all LF permissions for account 261399254793.
  - Domain account: revoke all grants to 261399254793 (account ID + roles)
  - Project account: remove DZ role from LF admins
Run from domain account credentials (amirbo+3).
"""
import boto3, json

REGION = "us-east-2"
PROJECT_ACCOUNT = "261399254793"
DOMAIN_ACCOUNT = "994753223772"
DOMAIN_ID = "dzd-4h7jbz76qckoh5"
PROJECT_ID = "5237hturzpp5ih"
DZ_ROLE = f"arn:aws:iam::{PROJECT_ACCOUNT}:role/datazone_usr_role_{PROJECT_ID}_b2no4uzn8mttt5"
DBS = ["apf_test_customers", "apf_test_transactions"]

print("=" * 60)
print("  LF Debug Trace - Step 2: CLEANUP")
print(f"  Project Account: {PROJECT_ACCOUNT}")
print(f"  Domain Account:  {DOMAIN_ACCOUNT}")
print(f"  DZ User Role:    {DZ_ROLE}")
print("=" * 60)
print()

# ── DOMAIN ACCOUNT: Revoke all grants to 261399254793 ──────────
print(">>> DOMAIN ACCOUNT: Revoking grants to project account...")
lf_domain = boto3.client('lakeformation', region_name=REGION)

for db in DBS:
    for resource in [
        {'Database': {'Name': db}},
        {'Table': {'DatabaseName': db, 'TableWildcard': {}}}
    ]:
        try:
            perms = lf_domain.list_permissions(Resource=resource)
            for p in perms['PrincipalResourcePermissions']:
                principal = p['Principal']['DataLakePrincipalIdentifier']
                # Only revoke grants to our target account
                if PROJECT_ACCOUNT in principal:
                    grants = p['Permissions']
                    grant_opts = p.get('PermissionsWithGrantOption', [])
                    res_desc = json.dumps(resource, default=str)
                    try:
                        kwargs = {
                            'Principal': {'DataLakePrincipalIdentifier': principal},
                            'Resource': resource,
                            'Permissions': grants,
                        }
                        if grant_opts:
                            kwargs['PermissionsWithGrantOption'] = grant_opts
                        lf_domain.revoke_permissions(**kwargs)
                        print(f"  REVOKED {grants} from {principal}")
                        print(f"    on {res_desc}")
                    except Exception as e:
                        print(f"  FAILED to revoke from {principal}: {e}")
        except Exception as e:
            print(f"  Error listing perms for {resource}: {e}")

print()

# ── PROJECT ACCOUNT: Remove DZ role from LF admins ─────────────
print(">>> PROJECT ACCOUNT: Removing DZ role from LF admins...")
sts = boto3.client('sts', region_name=REGION)
r = sts.assume_role(
    RoleArn=f'arn:aws:iam::{PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='lf-cleanup',
    ExternalId=DOMAIN_ID)
c = r['Credentials']

lf_proj = boto3.client('lakeformation', region_name=REGION,
    aws_access_key_id=c['AccessKeyId'],
    aws_secret_access_key=c['SecretAccessKey'],
    aws_session_token=c['SessionToken'])

settings = lf_proj.get_data_lake_settings()
dls = settings['DataLakeSettings']
old_admins = dls.get('DataLakeAdmins', [])
print(f"  Current LF admins ({len(old_admins)}):")
for a in old_admins:
    print(f"    {a['DataLakePrincipalIdentifier']}")

new_admins = [a for a in old_admins if a['DataLakePrincipalIdentifier'] != DZ_ROLE]
if len(new_admins) < len(old_admins):
    dls['DataLakeAdmins'] = new_admins
    lf_proj.put_data_lake_settings(DataLakeSettings=dls)
    print(f"  REMOVED {DZ_ROLE} from LF admins")
    print(f"  Remaining admins ({len(new_admins)}):")
    for a in new_admins:
        print(f"    {a['DataLakePrincipalIdentifier']}")
else:
    print(f"  {DZ_ROLE} was NOT an LF admin, nothing to remove")

print()

# ── PROJECT ACCOUNT: Revoke any explicit LF permissions ─────────
print(">>> PROJECT ACCOUNT: Revoking any explicit LF permissions...")
try:
    all_perms = []
    token = None
    while True:
        params = {'MaxResults': 100}
        if token:
            params['NextToken'] = token
        resp = lf_proj.list_permissions(**params)
        all_perms.extend(resp['PrincipalResourcePermissions'])
        token = resp.get('NextToken')
        if not token:
            break
    if all_perms:
        for p in all_perms:
            principal = p['Principal']['DataLakePrincipalIdentifier']
            grants = p['Permissions']
            resource = p['Resource']
            try:
                lf_proj.revoke_permissions(
                    Principal={'DataLakePrincipalIdentifier': principal},
                    Resource=resource,
                    Permissions=grants)
                print(f"  REVOKED {grants} from {principal}")
            except Exception as e:
                print(f"  Failed: {e}")
    else:
        print("  No explicit LF permissions found in project account")
except Exception as e:
    print(f"  Error: {e}")

print()
print("=" * 60)
print("  Cleanup complete. Now verify with step 3.")
print("=" * 60)
