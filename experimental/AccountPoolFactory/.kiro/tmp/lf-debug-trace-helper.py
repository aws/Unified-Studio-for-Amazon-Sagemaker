#!/usr/bin/env python3
"""
Helper for lf-debug-trace.sh — performs LF operations via boto3.
Usage: python3 lf-debug-trace-helper.py <action>

Actions:
  check_domain_grants   - List domain account LF grants to project account
  check_project_state   - Show project account LF admins + permissions
  test_visibility       - Test Glue get_databases via DomainAccess role
  grant_cross_account   - Grant LF from domain to project account ID
  grant_local_to_role   - Grant LF in project account to DZ user role
"""
import boto3, json, sys

REGION = "us-east-2"
PROJECT_ACCOUNT = "261399254793"
DOMAIN_ACCOUNT = "994753223772"
DOMAIN_ID = "dzd-4h7jbz76qckoh5"
PROJECT_ID = "5237hturzpp5ih"
DZ_ROLE = f"arn:aws:iam::{PROJECT_ACCOUNT}:role/datazone_usr_role_{PROJECT_ID}_b2no4uzn8mttt5"
DOMAIN_ACCESS_ROLE = f"arn:aws:iam::{PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess"
DBS = ["apf_test_customers", "apf_test_transactions"]


def get_project_clients():
    """Assume DomainAccess role and return LF + Glue clients for project account."""
    sts = boto3.client('sts', region_name=REGION)
    r = sts.assume_role(
        RoleArn=DOMAIN_ACCESS_ROLE,
        RoleSessionName='lf-debug-trace',
        ExternalId=DOMAIN_ID)
    c = r['Credentials']
    kwargs = dict(region_name=REGION,
        aws_access_key_id=c['AccessKeyId'],
        aws_secret_access_key=c['SecretAccessKey'],
        aws_session_token=c['SessionToken'])
    return (
        boto3.client('lakeformation', **kwargs),
        boto3.client('glue', **kwargs),
        boto3.client('sts', **kwargs),
    )


def check_domain_grants():
    """List all LF grants in domain account that target the project account."""
    lf = boto3.client('lakeformation', region_name=REGION)
    found = []
    for db in DBS:
        for resource in [
            {'Database': {'Name': db}},
            {'Table': {'DatabaseName': db, 'TableWildcard': {}}}
        ]:
            perms = lf.list_permissions(Resource=resource)
            for p in perms['PrincipalResourcePermissions']:
                principal = p['Principal']['DataLakePrincipalIdentifier']
                if PROJECT_ACCOUNT in principal:
                    found.append({
                        'principal': principal,
                        'permissions': p['Permissions'],
                        'grantOption': p.get('PermissionsWithGrantOption', []),
                        'resource': resource
                    })
    if found:
        for f in found:
            res_type = 'Database' if 'Database' in f['resource'] else 'Table'
            res_name = f['resource'].get('Database', f['resource'].get('Table', {})).get('Name',
                f['resource'].get('Table', {}).get('DatabaseName', ''))
            print(f"  {f['principal']}")
            print(f"    {res_type}: {res_name}")
            print(f"    Permissions: {f['permissions']}")
            if f['grantOption']:
                print(f"    GrantOption: {f['grantOption']}")
    else:
        print("  No grants to project account found (clean)")


def check_project_state():
    """Show LF admins and all permissions in project account."""
    lf, glue, sts_proj = get_project_clients()

    # LF admins
    settings = lf.get_data_lake_settings()
    admins = settings['DataLakeSettings'].get('DataLakeAdmins', [])
    print(f"  LF Admins ({len(admins)}):")
    for a in admins:
        arn = a['DataLakePrincipalIdentifier']
        marker = " <-- DZ USER ROLE" if DZ_ROLE in arn else ""
        print(f"    {arn}{marker}")

    # All LF permissions
    all_perms = []
    token = None
    while True:
        params = {'MaxResults': 100}
        if token:
            params['NextToken'] = token
        resp = lf.list_permissions(**params)
        all_perms.extend(resp['PrincipalResourcePermissions'])
        token = resp.get('NextToken')
        if not token:
            break

    if all_perms:
        print(f"  LF Permissions ({len(all_perms)}):")
        for p in all_perms:
            principal = p['Principal']['DataLakePrincipalIdentifier']
            perms = p['Permissions']
            resource = p['Resource']
            if 'Database' in resource:
                res_desc = f"Database: {resource['Database']['Name']}"
            elif 'Table' in resource:
                res_desc = f"Table: {resource['Table']['DatabaseName']}/*"
            elif 'TableWithColumns' in resource:
                res_desc = f"TableWithColumns: {resource['TableWithColumns']['DatabaseName']}/*"
            else:
                res_desc = json.dumps(resource)
            print(f"    {principal}")
            print(f"      {res_desc} -> {perms}")
    else:
        print("  LF Permissions: none (clean)")

    # Glue databases
    dbs_list = glue.get_databases()
    print(f"  Glue Databases ({len(dbs_list['DatabaseList'])}):")
    for db in dbs_list['DatabaseList']:
        t = db.get('TargetDatabase', {})
        if t:
            print(f"    {db['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}")
        else:
            print(f"    {db['Name']}")


def test_visibility():
    """Test what Glue get_databases returns via DomainAccess role.
    Note: DomainAccess has AdminAccess so it sees everything.
    The real test is whether LF permissions exist for the DZ role."""
    lf, glue, sts_proj = get_project_clients()

    # Check who we are
    identity = sts_proj.get_caller_identity()
    print(f"  Testing as: {identity['Arn']}")
    print(f"  (Note: DomainAccess has AdminAccess, so it sees all Glue DBs)")
    print(f"  The real question is: does the DZ role have LF permissions?")
    print()

    # Check if DZ role is LF admin
    settings = lf.get_data_lake_settings()
    admins = [a['DataLakePrincipalIdentifier'] for a in settings['DataLakeSettings'].get('DataLakeAdmins', [])]
    is_admin = DZ_ROLE in admins
    print(f"  DZ role is LF admin: {is_admin}")

    # Check LF permissions for the DZ role on each DB
    for db in DBS:
        for resource in [
            {'Database': {'Name': db}},
        ]:
            try:
                perms = lf.list_permissions(Resource=resource)
                role_perms = [p for p in perms['PrincipalResourcePermissions']
                             if p['Principal']['DataLakePrincipalIdentifier'] == DZ_ROLE]
                if role_perms:
                    print(f"  {db}: DZ role has {role_perms[0]['Permissions']}")
                else:
                    print(f"  {db}: DZ role has NO permissions")
            except Exception as e:
                print(f"  {db}: Error checking - {e}")

    # Try get_tables to see if cross-account access works
    print()
    for db in DBS:
        try:
            tables = glue.get_tables(DatabaseName=db)
            tnames = [t['Name'] for t in tables['TableList']]
            print(f"  get_tables({db}): {tnames if tnames else 'empty'}")
        except Exception as e:
            err = str(e)
            if 'AccessDenied' in err:
                print(f"  get_tables({db}): ACCESS DENIED (no cross-account LF grant)")
            else:
                print(f"  get_tables({db}): Error - {e}")


def grant_cross_account():
    """Grant LF permissions from domain account to project account ID."""
    lf = boto3.client('lakeformation', region_name=REGION)
    for db in DBS:
        # Database: DESCRIBE with grant option
        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': PROJECT_ACCOUNT},
                Resource={'Database': {'Name': db}},
                Permissions=['DESCRIBE'],
                PermissionsWithGrantOption=['DESCRIBE'])
            print(f"  Granted DESCRIBE on DB {db} to {PROJECT_ACCOUNT} (with grant option)")
        except Exception as e:
            print(f"  DB {db}: {e}")

        # Tables: SELECT + DESCRIBE with grant option
        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': PROJECT_ACCOUNT},
                Resource={'Table': {'DatabaseName': db, 'TableWildcard': {}}},
                Permissions=['SELECT', 'DESCRIBE'],
                PermissionsWithGrantOption=['SELECT', 'DESCRIBE'])
            print(f"  Granted SELECT+DESCRIBE on tables in {db} to {PROJECT_ACCOUNT} (with grant option)")
        except Exception as e:
            print(f"  Tables {db}: {e}")


def grant_local_iap():
    """Grant LF permissions in project account to IAM_ALLOWED_PRINCIPALS.
    DomainAccess has AdminAccess but is not an LF admin.
    Step 1: Add DomainAccess role as LF admin (temporarily)
    Step 2: Grant IAM_ALLOWED_PRINCIPALS on resource link DBs
    Step 3: Remove DomainAccess from LF admins"""
    lf, glue, sts_proj = get_project_clients()

    identity = sts_proj.get_caller_identity()
    my_arn = identity['Arn']
    # Extract role ARN from assumed-role ARN
    # arn:aws:sts::ACCT:assumed-role/ROLE/SESSION -> arn:aws:iam::ACCT:role/ROLE
    parts = my_arn.split(':')
    role_part = parts[5].split('/')[1]  # SMUS-AccountPoolFactory-DomainAccess
    my_role_arn = f"arn:aws:iam::{PROJECT_ACCOUNT}:role/{role_part}"
    print(f"  Operating as: {my_arn}")
    print(f"  Role ARN: {my_role_arn}")

    # Step 1: Add ourselves as LF admin
    print(f"  Step 1: Adding DomainAccess as LF admin (temporarily)...")
    settings = lf.get_data_lake_settings()
    dls = settings['DataLakeSettings']
    old_admins = list(dls.get('DataLakeAdmins', []))
    admin_arns = [a['DataLakePrincipalIdentifier'] for a in old_admins]
    if my_role_arn not in admin_arns:
        dls['DataLakeAdmins'] = old_admins + [{'DataLakePrincipalIdentifier': my_role_arn}]
        lf.put_data_lake_settings(DataLakeSettings=dls)
        print(f"    Added {my_role_arn} as LF admin")
    else:
        print(f"    Already an LF admin")

    # Step 2: Grant IAM_ALLOWED_PRINCIPALS
    print(f"  Step 2: Granting to IAM_ALLOWED_PRINCIPALS...")
    IAP = 'IAM_ALLOWED_PRINCIPALS'
    for db in DBS:
        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': IAP},
                Resource={'Database': {'Name': db}},
                Permissions=['DESCRIBE'])
            print(f"    Granted DESCRIBE on DB {db}")
        except Exception as e:
            print(f"    DB {db}: {e}")

        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': IAP},
                Resource={'Table': {'DatabaseName': db, 'TableWildcard': {}}},
                Permissions=['SELECT', 'DESCRIBE'])
            print(f"    Granted SELECT+DESCRIBE on tables in {db}")
        except Exception as e:
            print(f"    Tables {db}: {e}")

    # Step 3: Remove ourselves from LF admins
    print(f"  Step 3: Removing DomainAccess from LF admins...")
    settings = lf.get_data_lake_settings()
    dls = settings['DataLakeSettings']
    dls['DataLakeAdmins'] = [a for a in dls['DataLakeAdmins']
                             if a['DataLakePrincipalIdentifier'] != my_role_arn]
    lf.put_data_lake_settings(DataLakeSettings=dls)
    print(f"    Removed {my_role_arn} from LF admins")


def grant_cross_account_to_role():
    """Grant LF from domain account directly to the DZ user role ARN.
    This is the pattern the PoolManager Lambda uses."""
    lf = boto3.client('lakeformation', region_name=REGION)
    for db in DBS:
        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': DZ_ROLE},
                Resource={'Database': {'Name': db}},
                Permissions=['DESCRIBE'])
            print(f"  Granted DESCRIBE on DB {db} to DZ role (cross-account)")
        except Exception as e:
            print(f"  DB {db}: {e}")
        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': DZ_ROLE},
                Resource={'Table': {'DatabaseName': db, 'TableWildcard': {}}},
                Permissions=['SELECT', 'DESCRIBE'])
            print(f"  Granted SELECT+DESCRIBE on tables in {db} to DZ role (cross-account)")
        except Exception as e:
            print(f"  Tables {db}: {e}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 lf-debug-trace-helper.py <action>")
        print("Actions: check_domain_grants, check_project_state, test_visibility,")
        print("         grant_cross_account, grant_local_iap, grant_cross_account_to_role")
        sys.exit(1)

    action = sys.argv[1]
    actions = {
        'check_domain_grants': check_domain_grants,
        'check_project_state': check_project_state,
        'test_visibility': test_visibility,
        'grant_cross_account': grant_cross_account,
        'grant_local_iap': grant_local_iap,
        'grant_cross_account_to_role': grant_cross_account_to_role,
    }
    if action not in actions:
        print(f"Unknown action: {action}")
        sys.exit(1)
    actions[action]()
