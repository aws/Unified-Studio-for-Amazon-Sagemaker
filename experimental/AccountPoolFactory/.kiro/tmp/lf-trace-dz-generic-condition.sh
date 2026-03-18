#!/bin/bash
# Test generic DataZone condition (no specific projectId)
# Condition: just check that datazone context with projectId exists
set -e

REGION="us-east-2"
PROJECT_ACCOUNT="261399254793"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SAVE_AKI="$AWS_ACCESS_KEY_ID"
SAVE_SAK="$AWS_SECRET_ACCESS_KEY"
SAVE_ST="$AWS_SESSION_TOKEN"
use_domain() { export AWS_ACCESS_KEY_ID="$SAVE_AKI"; export AWS_SECRET_ACCESS_KEY="$SAVE_SAK"; export AWS_SESSION_TOKEN="$SAVE_ST"; }
use_project() { eval $(use_domain; python3 "$SCRIPT_DIR/lf-trace-creds-project.py"); }
use_dzrole() { eval $(use_domain; python3 "$SCRIPT_DIR/lf-trace-creds-dzrole.py"); }

PRINCIPAL="${PROJECT_ACCOUNT}:IAMPrincipals"
# Just check that the datazone context exists with a projectId — any project
CONDITION='context has datazone && context.datazone has projectId'

echo "============================================================================="
echo "  Test: Generic DataZone condition (no specific projectId)"
echo "  Principal: $PRINCIPAL"
echo "  Condition: $CONDITION"
echo "  Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
echo ""

# First revoke the project-specific grants from previous test
use_project
echo ">>> Revoking previous project-specific condition grants..."
python3 -c "
import boto3
lf=boto3.client('lakeformation',region_name='$REGION')
pid='5237hturzpp5ih'
cond='context has datazone && context.datazone has projectId && context.datazone.projectId==\"'+pid+'\"'
for db in ['apf_test_customers','apf_test_transactions']:
    for res,perms in [
        ({'Database':{'Name':db}},['DESCRIBE']),
        ({'Table':{'DatabaseName':db,'TableWildcard':{}}},['DESCRIBE','SELECT']),
    ]:
        try:
            lf.revoke_permissions(
                Principal={'DataLakePrincipalIdentifier':'$PRINCIPAL'},
                Resource=res, Permissions=perms,
                Condition={'Expression':cond})
            print(f'  Revoked {perms} on {db}')
        except Exception as e:
            if 'not found' in str(e).lower() or 'invalid' in str(e).lower():
                print(f'  Skip {db}: {e}')
            else:
                print(f'  Error {db}: {e}')
"
echo ""

# Verify clean
use_dzrole
echo ">>> [DZ User Role] aws glue get-databases (BEFORE — should be clean)"
aws glue get-databases --region $REGION --output json | python3 -c "
import sys,json
dbs=json.load(sys.stdin)['DatabaseList']
for d in dbs:
    t=d.get('TargetDatabase',{})
    if t: print(f\"  {d['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}\")
    else: print(f\"  {d['Name']}\")"
echo ""

# Add DomainAccess as LF admin
use_project
echo ">>> Adding DomainAccess as LF admin..."
CURRENT=$(aws lakeformation get-data-lake-settings --region $REGION --output json)
UPDATED=$(echo "$CURRENT" | python3 -c "
import sys,json
s=json.load(sys.stdin)['DataLakeSettings']
role='arn:aws:iam::${PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess'
admins=s.get('DataLakeAdmins',[])
if not any(a['DataLakePrincipalIdentifier']==role for a in admins):
    admins.append({'DataLakePrincipalIdentifier':role})
s['DataLakeAdmins']=admins
print(json.dumps(s))")
aws lakeformation put-data-lake-settings --data-lake-settings "$UPDATED" --region $REGION 2>&1 > /dev/null
echo "  Done"
echo ""

# Grant with generic condition
echo "============================================================================="
echo "  Granting with generic condition: $CONDITION"
echo "============================================================================="
echo ""

python3 -c "
import boto3,json
lf=boto3.client('lakeformation',region_name='$REGION')
cond='$CONDITION'
for db in ['apf_test_customers','apf_test_transactions']:
    for res,perms in [
        ({'Database':{'Name':db}},['DESCRIBE']),
        ({'Table':{'DatabaseName':db,'TableWildcard':{}}},['DESCRIBE','SELECT']),
    ]:
        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier':'$PRINCIPAL'},
                Resource=res, Permissions=perms,
                Condition={'Expression':cond})
            print(f'  Granted {perms} on {json.dumps(res)}')
        except Exception as e:
            print(f'  ERROR: {e}')
"
echo ""

# Check visibility
use_dzrole
echo ">>> [DZ User Role] aws glue get-databases (AFTER generic condition grants)"
aws glue get-databases --region $REGION --output json | python3 -c "
import sys,json
dbs=json.load(sys.stdin)['DatabaseList']
for d in dbs:
    t=d.get('TargetDatabase',{})
    if t: print(f\"  {d['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}\")
    else: print(f\"  {d['Name']}\")"
echo ""

echo ">>> [DZ User Role] aws glue get-tables --database-name apf_test_customers"
aws glue get-tables --database-name apf_test_customers --region $REGION --output json 2>&1 | python3 -c "
import sys,json
s=sys.stdin.read().strip()
if s[0]=='{':
    d=json.loads(s); d.pop('ResponseMetadata',None)
    tables=d.get('TableList',[])
    print(f'  Tables: {len(tables)}')
    for t in tables: print(f\"    {t['Name']}\")
else: print(s)"
echo ""

# Cleanup
use_project
echo ">>> Removing DomainAccess from LF admins..."
CURRENT=$(aws lakeformation get-data-lake-settings --region $REGION --output json)
UPDATED=$(echo "$CURRENT" | python3 -c "
import sys,json
s=json.load(sys.stdin)['DataLakeSettings']
role='arn:aws:iam::${PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess'
s['DataLakeAdmins']=[a for a in s.get('DataLakeAdmins',[]) if a['DataLakePrincipalIdentifier']!=role]
print(json.dumps(s))")
aws lakeformation put-data-lake-settings --data-lake-settings "$UPDATED" --region $REGION 2>&1 > /dev/null
echo "  Done"
echo ""

echo "============================================================================="
echo "  Done: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
