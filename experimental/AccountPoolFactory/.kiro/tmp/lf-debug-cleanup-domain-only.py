#!/usr/bin/env python3
"""Clean domain account LF grants for project account 261399254793 only."""
import boto3, json

REGION = "us-east-2"
PROJECT_ACCOUNT = "261399254793"
DBS = ["apf_test_customers", "apf_test_transactions"]

lf = boto3.client('lakeformation', region_name=REGION)
for db in DBS:
    for resource in [
        {'Database': {'Name': db}},
        {'Table': {'DatabaseName': db, 'TableWildcard': {}}}
    ]:
        perms = lf.list_permissions(Resource=resource)
        for p in perms['PrincipalResourcePermissions']:
            principal = p['Principal']['DataLakePrincipalIdentifier']
            if PROJECT_ACCOUNT in principal:
                grants = p['Permissions']
                grant_opts = p.get('PermissionsWithGrantOption', [])
                kwargs = {
                    'Principal': {'DataLakePrincipalIdentifier': principal},
                    'Resource': resource,
                    'Permissions': grants,
                }
                if grant_opts:
                    kwargs['PermissionsWithGrantOption'] = grant_opts
                try:
                    lf.revoke_permissions(**kwargs)
                    print(f"Revoked {grants} from {principal} on {json.dumps(resource)}")
                except Exception as e:
                    print(f"Failed: {e}")
print("Done")
