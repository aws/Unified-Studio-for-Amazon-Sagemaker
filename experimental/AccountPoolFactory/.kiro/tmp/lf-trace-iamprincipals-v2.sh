#!/bin/bash
# Test IAMPrincipals grant — keep grants, check list-permissions, wait and recheck
set -e

REGION="us-east-2"
PROJECT_ACCOUNT="261399254793"
PRINCIPAL="${PROJECT_ACCOUNT}:IAMPrincipals"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SAVE_AKI="$AWS_ACCESS_KEY_ID"
SAVE_SAK="$AWS_SECRET_ACCESS_KEY"
SAVE_ST="$AWS_SESSION_TOKEN"
use_domain() { export AWS_ACCESS_KEY_ID="$SAVE_AKI"; export AWS_SECRET_ACCESS_KEY="$SAVE_SAK"; export AWS_SESSION_TOKEN="$SAVE_ST"; }
use_dzrole() { eval $(use_domain; python3 "$SCRIPT_DIR/lf-trace-creds-dzrole.py"); }
strip() { python3 -c "
import sys,json
s=sys.stdin.read().strip()
if not s: print('(no output)')
elif s[0] in ('{','['): d=json.loads(s);isinstance(d,dict) and d.pop('ResponseMetadata',None);print(json.dumps(d,indent=2,default=str))
else: print(s)"; }
filter_perms() { python3 -c "
import sys,json
d=json.load(sys.stdin)
f=[p for p in d['PrincipalResourcePermissions'] if '$PROJECT_ACCOUNT' in p['Principal']['DataLakePrincipalIdentifier']]
d['PrincipalResourcePermissions']=f
d.pop('ResponseMetadata',None)
print(json.dumps(d,indent=2,default=str))"; }

echo "============================================================================="
echo "  Test: ${PROJECT_ACCOUNT}:IAMPrincipals grant from source account"
echo "  Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
echo ""

use_domain
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

# Grant on both DBs — DESCRIBE on DB, DESCRIBE+SELECT on table wildcard
for DB in apf_test_customers apf_test_transactions; do
    echo ">>> aws lakeformation grant-permissions — DESCRIBE on DB $DB to $PRINCIPAL"
    aws lakeformation grant-permissions \
        --principal "DataLakePrincipalIdentifier=$PRINCIPAL" \
        --resource "{\"Database\":{\"Name\":\"$DB\"}}" \
        --permissions DESCRIBE \
        --region $REGION --output json 2>&1 | strip
    echo ""

    echo ">>> aws lakeformation grant-permissions — DESCRIBE,SELECT on Table wildcard $DB to $PRINCIPAL"
    aws lakeformation grant-permissions \
        --principal "DataLakePrincipalIdentifier=$PRINCIPAL" \
        --resource "{\"Table\":{\"DatabaseName\":\"$DB\",\"TableWildcard\":{}}}" \
        --permissions DESCRIBE SELECT \
        --region $REGION --output json 2>&1 | strip
    echo ""
done

# Verify grants in domain account
echo ">>> aws lakeformation list-permissions --resource Database:apf_test_customers (filtered)"
aws lakeformation list-permissions \
    --resource '{"Database":{"Name":"apf_test_customers"}}' \
    --region $REGION --output json | filter_perms
echo ""

echo ">>> aws lakeformation list-permissions --resource Table:apf_test_customers/* (filtered)"
aws lakeformation list-permissions \
    --resource '{"Table":{"DatabaseName":"apf_test_customers","TableWildcard":{}}}' \
    --region $REGION --output json | filter_perms
echo ""

# Test visibility immediately
echo ">>> [DZ User Role] aws glue get-databases (immediate)"
use_dzrole
aws glue get-databases --region $REGION --output json | python3 -c "
import sys,json
dbs=json.load(sys.stdin)['DatabaseList']
for d in dbs:
    t=d.get('TargetDatabase',{})
    if t: print(f\"  {d['Name']} -> {t.get('CatalogId','')}/{t.get('DatabaseName','')}\")
    else: print(f\"  {d['Name']}\")"
echo ""

# Wait and retry
echo ">>> Waiting 10 seconds..."
sleep 10

echo ">>> [DZ User Role] aws glue get-databases (after 10s wait)"
use_dzrole
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
    d=json.loads(s)
    d.pop('ResponseMetadata',None)
    tables=d.get('TableList',[])
    print(f'  Tables found: {len(tables)}')
    for t in tables: print(f\"    {t['Name']}\")
else: print(s)"
echo ""

echo "============================================================================="
echo "  Done: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
