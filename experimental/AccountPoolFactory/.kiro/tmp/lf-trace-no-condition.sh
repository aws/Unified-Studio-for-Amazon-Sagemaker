#!/bin/bash
# Test: IAMPrincipals grant with NO condition
set -e

REGION="us-east-2"
PROJECT_ACCOUNT="261399254793"
PRINCIPAL="${PROJECT_ACCOUNT}:IAMPrincipals"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SAVE_AKI="$AWS_ACCESS_KEY_ID"
SAVE_SAK="$AWS_SECRET_ACCESS_KEY"
SAVE_ST="$AWS_SESSION_TOKEN"
use_domain() { export AWS_ACCESS_KEY_ID="$SAVE_AKI"; export AWS_SECRET_ACCESS_KEY="$SAVE_SAK"; export AWS_SESSION_TOKEN="$SAVE_ST"; }
use_project() { eval $(use_domain; python3 "$SCRIPT_DIR/lf-trace-creds-project.py"); }
use_dzrole() { eval $(use_domain; python3 "$SCRIPT_DIR/lf-trace-creds-dzrole.py"); }

echo "============================================================================="
echo "  Test: IAMPrincipals with NO condition"
echo "  Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
echo ""

# Revoke ALL existing IAMPrincipals grants (both condition variants)
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

echo ">>> Revoking all existing IAMPrincipals grants..."
python3 -c "
import boto3,json
lf=boto3.client('lakeformation',region_name='$REGION')
principal='$PRINCIPAL'
conditions=[
    'context has datazone && context.datazone has projectId && context.datazone.projectId==\"5237hturzpp5ih\"',
    'context has datazone && context.datazone has projectId',
    None
]
for db in ['apf_test_customers','apf_test_transactions']:
    for res,perms in [
        ({'Database':{'Name':db}},['DESCRIBE']),
        ({'Table':{'DatabaseName':db,'TableWildcard':{}}},['DESCRIBE','SELECT']),
    ]:
        for cond in conditions:
            try:
                kwargs=dict(Principal={'DataLakePrincipalIdentifier':principal},Resource=res,Permissions=perms)
                if cond: kwargs['Condition']={'Expression':cond}
                lf.revoke_permissions(**kwargs)
                c_str=cond[:40]+'...' if cond else 'none'
                print(f'  Revoked {perms} on {db} (cond={c_str})')
            except: pass
"
echo ""

# Verify clean
use_dzrole
echo ">>> [DZ User Role] aws glue get-databases (BEFORE — after revoking)"
aws glue get-databases --region $REGION --output json | python3 -c "
import sys,json
dbs=json.load(sys.stdin)['DatabaseList']
for d in dbs:
    t=d.get('TargetDatabase',{})
    if t: print(f\"  {d['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}\")
    else: print(f\"  {d['Name']}\")"
echo ""

# Grant with NO condition
use_project
echo "============================================================================="
echo "  Granting with NO condition"
echo "============================================================================="
echo ""
python3 -c "
import boto3,json
lf=boto3.client('lakeformation',region_name='$REGION')
for db in ['apf_test_customers','apf_test_transactions']:
    for res,perms in [
        ({'Database':{'Name':db}},['DESCRIBE']),
        ({'Table':{'DatabaseName':db,'TableWildcard':{}}},['DESCRIBE','SELECT']),
    ]:
        try:
            lf.grant_permissions(
                Principal={'DataLakePrincipalIdentifier':'$PRINCIPAL'},
                Resource=res, Permissions=perms)
            print(f'  Granted {perms} on {json.dumps(res)}')
        except Exception as e:
            print(f'  ERROR: {e}')
"
echo ""

# Check visibility
use_dzrole
echo ">>> [DZ User Role] aws glue get-databases (AFTER no-condition grants)"
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
