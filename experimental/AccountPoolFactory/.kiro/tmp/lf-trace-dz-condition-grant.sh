#!/bin/bash
# Grant using 261399254793:IAMPrincipals with DataZone project condition
# This matches how DataZone itself grants access to project databases
set -e

REGION="us-east-2"
PROJECT_ACCOUNT="261399254793"
PROJECT_ID="5237hturzpp5ih"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SAVE_AKI="$AWS_ACCESS_KEY_ID"
SAVE_SAK="$AWS_SECRET_ACCESS_KEY"
SAVE_ST="$AWS_SESSION_TOKEN"
use_domain() { export AWS_ACCESS_KEY_ID="$SAVE_AKI"; export AWS_SECRET_ACCESS_KEY="$SAVE_SAK"; export AWS_SESSION_TOKEN="$SAVE_ST"; }
use_project() { eval $(use_domain; python3 "$SCRIPT_DIR/lf-trace-creds-project.py"); }
use_dzrole() { eval $(use_domain; python3 "$SCRIPT_DIR/lf-trace-creds-dzrole.py"); }
strip() { python3 -c "
import sys,json
s=sys.stdin.read().strip()
if not s: print('(no output)')
elif s[0] in ('{','['): d=json.loads(s);isinstance(d,dict) and d.pop('ResponseMetadata',None);print(json.dumps(d,indent=2,default=str))
else: print(s)"; }

PRINCIPAL="${PROJECT_ACCOUNT}:IAMPrincipals"
CONDITION="context has datazone && context.datazone has projectId && context.datazone.projectId==\"${PROJECT_ID}\""

echo "============================================================================="
echo "  Test: IAMPrincipals + DataZone condition grant in project account"
echo "  Principal: $PRINCIPAL"
echo "  Condition: $CONDITION"
echo "  Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
echo ""

# Baseline
use_dzrole
echo ">>> [DZ User Role] aws glue get-databases (BEFORE)"
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
aws lakeformation put-data-lake-settings --data-lake-settings "$UPDATED" --region $REGION --output json 2>&1 | strip
echo ""

# Grant DESCRIBE on resource link DBs with DZ condition
echo "============================================================================="
echo "  Granting DESCRIBE on resource link DBs to IAMPrincipals with DZ condition"
echo "============================================================================="
echo ""

for DB in apf_test_customers apf_test_transactions; do
    echo ">>> aws lakeformation grant-permissions — DESCRIBE on DB $DB to $PRINCIPAL (with condition)"
    python3 -c "
import boto3,json
lf=boto3.client('lakeformation',region_name='$REGION')
try:
    lf.grant_permissions(
        Principal={'DataLakePrincipalIdentifier':'$PRINCIPAL'},
        Resource={'Database':{'Name':'$DB'}},
        Permissions=['DESCRIBE'],
        Condition={'Expression':'$CONDITION'})
    print('(no output)')
except Exception as e:
    print(str(e))"
    echo ""

    echo ">>> aws lakeformation grant-permissions — DESCRIBE,SELECT on Table wildcard $DB to $PRINCIPAL (with condition)"
    python3 -c "
import boto3,json
lf=boto3.client('lakeformation',region_name='$REGION')
try:
    lf.grant_permissions(
        Principal={'DataLakePrincipalIdentifier':'$PRINCIPAL'},
        Resource={'Table':{'DatabaseName':'$DB','TableWildcard':{}}},
        Permissions=['DESCRIBE','SELECT'],
        Condition={'Expression':'$CONDITION'})
    print('(no output)')
except Exception as e:
    print(str(e))"
    echo ""
done

# Check visibility
use_dzrole
echo ">>> [DZ User Role] aws glue get-databases (AFTER condition grants)"
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

# Show LF permissions
use_project
echo ">>> [Project Account] aws lakeformation list-permissions (filtered to apf_test_*)"
aws lakeformation list-permissions --region $REGION --output json | python3 -c "
import sys,json
d=json.load(sys.stdin)
d.pop('ResponseMetadata',None)
filtered=[p for p in d['PrincipalResourcePermissions'] if 'apf_test' in json.dumps(p.get('Resource',{}))]
print(json.dumps({'PrincipalResourcePermissions':filtered},indent=2,default=str))"
echo ""

# Cleanup
echo ">>> Removing DomainAccess from LF admins..."
CURRENT=$(aws lakeformation get-data-lake-settings --region $REGION --output json)
UPDATED=$(echo "$CURRENT" | python3 -c "
import sys,json
s=json.load(sys.stdin)['DataLakeSettings']
role='arn:aws:iam::${PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess'
s['DataLakeAdmins']=[a for a in s.get('DataLakeAdmins',[]) if a['DataLakePrincipalIdentifier']!=role]
print(json.dumps(s))")
aws lakeformation put-data-lake-settings --data-lake-settings "$UPDATED" --region $REGION --output json 2>&1 | strip
echo ""

echo "============================================================================="
echo "  Done: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
