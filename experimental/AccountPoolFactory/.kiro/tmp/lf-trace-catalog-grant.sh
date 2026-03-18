#!/bin/bash
# Test ALLIAMPrincipals grants in the project account on resource link DBs
# ALLIAMPrincipals = LF-authorized access for all IAM principals (not IAM fallback)
set -e

REGION="us-east-2"
PROJECT_ACCOUNT="261399254793"
DOMAIN_ID="dzd-4h7jbz76qckoh5"
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

echo "============================================================================="
echo "  Test: ALLIAMPrincipals grants in project account"
echo "  Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
echo ""

# Baseline: what DZ role sees before
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

# Add DomainAccess as LF admin in project account
use_project
echo ">>> [Project Account] Adding DomainAccess as LF admin..."
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

# Try 1: DESCRIBE on each resource link DB to ALLIAMPrincipals
echo "============================================================================="
echo "  Try 1: DESCRIBE on resource link DBs to ALLIAMPrincipals"
echo "============================================================================="
echo ""
for DB in apf_test_customers apf_test_transactions; do
    echo ">>> aws lakeformation grant-permissions — DESCRIBE on DB $DB to ALLIAMPrincipals"
    aws lakeformation grant-permissions \
        --principal "DataLakePrincipalIdentifier=ALLIAMPrincipals" \
        --resource "{\"Database\":{\"Name\":\"$DB\"}}" \
        --permissions DESCRIBE \
        --region $REGION --output json 2>&1 | strip
    echo ""
done

use_dzrole
echo ">>> [DZ User Role] aws glue get-databases (after Try 1)"
aws glue get-databases --region $REGION --output json | python3 -c "
import sys,json
dbs=json.load(sys.stdin)['DatabaseList']
for d in dbs:
    t=d.get('TargetDatabase',{})
    if t: print(f\"  {d['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}\")
    else: print(f\"  {d['Name']}\")"
echo ""

# Try 2: DESCRIBE+SELECT on Table wildcard to ALLIAMPrincipals
echo "============================================================================="
echo "  Try 2: DESCRIBE+SELECT on Table wildcard to ALLIAMPrincipals"
echo "============================================================================="
echo ""
use_project
for DB in apf_test_customers apf_test_transactions; do
    echo ">>> aws lakeformation grant-permissions — DESCRIBE,SELECT on Table wildcard $DB to ALLIAMPrincipals"
    aws lakeformation grant-permissions \
        --principal "DataLakePrincipalIdentifier=ALLIAMPrincipals" \
        --resource "{\"Table\":{\"DatabaseName\":\"$DB\",\"TableWildcard\":{}}}" \
        --permissions DESCRIBE SELECT \
        --region $REGION --output json 2>&1 | strip
    echo ""
done

use_dzrole
echo ">>> [DZ User Role] aws glue get-databases (after Try 2)"
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

# Show LF permissions in project account
use_project
echo ">>> [Project Account] aws lakeformation list-permissions"
aws lakeformation list-permissions --region $REGION --output json | strip
echo ""

# Cleanup: remove DomainAccess from LF admins
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
