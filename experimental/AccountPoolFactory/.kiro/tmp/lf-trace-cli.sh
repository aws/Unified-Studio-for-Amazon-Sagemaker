#!/bin/bash
# =============================================================================
# Lake Formation Cross-Account Grant Debug Trace
#
# Domain Account: 994753223772 (source — owns Glue DBs + S3 data)
# Project Account: 261399254793 (target — has resource link databases)
# DZ User Role: datazone_usr_role_5237hturzpp5ih_b2no4uzn8mttt5
# Databases: apf_test_customers, apf_test_transactions
# Region: us-east-2
#
# Usage:
#   eval $(isengardcli credentials amirbo+3@amazon.com)
#   bash lf-trace-cli.sh > lf-trace-cli-output.txt 2>&1
# =============================================================================
set -e

REGION="us-east-2"
PROJECT_ACCOUNT="261399254793"
DOMAIN_ACCOUNT="994753223772"
DZ_ROLE="arn:aws:iam::261399254793:role/datazone_usr_role_5237hturzpp5ih_b2no4uzn8mttt5"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Save domain account creds
SAVE_AKI="$AWS_ACCESS_KEY_ID"
SAVE_SAK="$AWS_SECRET_ACCESS_KEY"
SAVE_ST="$AWS_SESSION_TOKEN"

use_domain() {
    export AWS_ACCESS_KEY_ID="$SAVE_AKI"
    export AWS_SECRET_ACCESS_KEY="$SAVE_SAK"
    export AWS_SESSION_TOKEN="$SAVE_ST"
}
use_project() { eval $(use_domain; python3 "$SCRIPT_DIR/lf-trace-creds-project.py"); }
use_dzrole()  { eval $(use_domain; python3 "$SCRIPT_DIR/lf-trace-creds-dzrole.py"); }

# Strip ResponseMetadata, handle empty input and error strings
strip() { python3 -c "
import sys,json
s=sys.stdin.read().strip()
if not s:
    print('(no output)')
elif s[0] in ('{','['):
    d=json.loads(s)
    if isinstance(d,dict): d.pop('ResponseMetadata',None)
    print(json.dumps(d,indent=2,default=str))
else:
    print(s)"; }
# Filter list-permissions to project account
filter_perms() { python3 -c "
import sys,json
d=json.load(sys.stdin)
f=[p for p in d['PrincipalResourcePermissions'] if '$PROJECT_ACCOUNT' in p['Principal']['DataLakePrincipalIdentifier']]
d['PrincipalResourcePermissions']=f
d.pop('ResponseMetadata',None)
print(json.dumps(d,indent=2,default=str))"; }

echo "============================================================================="
echo "  Lake Formation Cross-Account Grant Debug Trace"
echo "  Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "  Domain Account (source): $DOMAIN_ACCOUNT"
echo "  Project Account (target): $PROJECT_ACCOUNT"
echo "  DZ User Role: $DZ_ROLE"
echo "============================================================================="
echo ""

# =============================================================================
# BASELINE
# =============================================================================
echo "============================================================================="
echo "  BASELINE — Clean Starting State"
echo "============================================================================="
echo ""

# -- Domain account: LF permissions --
use_domain
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation list-permissions --resource Database:apf_test_customers (filtered to $PROJECT_ACCOUNT)"
aws lakeformation list-permissions --resource '{"Database":{"Name":"apf_test_customers"}}' --region $REGION --output json | filter_perms
echo ""

echo ">>> aws lakeformation list-permissions --resource Table:apf_test_customers/* (filtered to $PROJECT_ACCOUNT)"
aws lakeformation list-permissions --resource '{"Table":{"DatabaseName":"apf_test_customers","TableWildcard":{}}}' --region $REGION --output json | filter_perms
echo ""

echo ">>> aws lakeformation list-permissions --resource Database:apf_test_transactions (filtered to $PROJECT_ACCOUNT)"
aws lakeformation list-permissions --resource '{"Database":{"Name":"apf_test_transactions"}}' --region $REGION --output json | filter_perms
echo ""

echo ">>> aws lakeformation list-permissions --resource Table:apf_test_transactions/* (filtered to $PROJECT_ACCOUNT)"
aws lakeformation list-permissions --resource '{"Table":{"DatabaseName":"apf_test_transactions","TableWildcard":{}}}' --region $REGION --output json | filter_perms
echo ""

# -- Project account (DomainAccess — LF admin view): LF settings + permissions --
use_project
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation get-data-lake-settings"
aws lakeformation get-data-lake-settings --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation list-permissions"
aws lakeformation list-permissions --region $REGION --output json | strip
echo ""

echo ">>> aws glue get-databases (DomainAccess — admin view, shows what SHOULD be there)"
aws glue get-databases --region $REGION --output json | strip
echo ""

echo ">>> aws glue get-tables --database-name apf_test_customers (DomainAccess — admin view)"
aws glue get-tables --database-name apf_test_customers --region $REGION --output json 2>&1 | strip || true
echo ""

echo ">>> aws glue get-tables --database-name apf_test_transactions (DomainAccess — admin view)"
aws glue get-tables --database-name apf_test_transactions --region $REGION --output json 2>&1 | strip || true
echo ""

# -- DZ User Role: what the actual user sees --
use_dzrole
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws glue get-databases (DZ User Role — actual user view)"
aws glue get-databases --region $REGION --output json | strip
echo ""

echo ">>> aws glue get-tables --database-name apf_test_customers (DZ User Role)"
aws glue get-tables --database-name apf_test_customers --region $REGION --output json 2>&1 | strip || true
echo ""

echo ">>> aws glue get-tables --database-name apf_test_transactions (DZ User Role)"
aws glue get-tables --database-name apf_test_transactions --region $REGION --output json 2>&1 | strip || true
echo ""

# =============================================================================
# PHASE 1: Cross-account grant (domain -> project account ID)
# =============================================================================
echo "============================================================================="
echo "  PHASE 1: Cross-account grant (domain -> account ID $PROJECT_ACCOUNT)"
echo "============================================================================="
echo ""

use_domain
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation grant-permissions — DESCRIBE on DB apf_test_customers to $PROJECT_ACCOUNT"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=$PROJECT_ACCOUNT" \
    --resource '{"Database":{"Name":"apf_test_customers"}}' \
    --permissions DESCRIBE --permissions-with-grant-option DESCRIBE \
    --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation grant-permissions — SELECT,DESCRIBE on tables apf_test_customers/* to $PROJECT_ACCOUNT"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=$PROJECT_ACCOUNT" \
    --resource '{"Table":{"DatabaseName":"apf_test_customers","TableWildcard":{}}}' \
    --permissions SELECT DESCRIBE --permissions-with-grant-option SELECT DESCRIBE \
    --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation grant-permissions — DESCRIBE on DB apf_test_transactions to $PROJECT_ACCOUNT"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=$PROJECT_ACCOUNT" \
    --resource '{"Database":{"Name":"apf_test_transactions"}}' \
    --permissions DESCRIBE --permissions-with-grant-option DESCRIBE \
    --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation grant-permissions — SELECT,DESCRIBE on tables apf_test_transactions/* to $PROJECT_ACCOUNT"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=$PROJECT_ACCOUNT" \
    --resource '{"Table":{"DatabaseName":"apf_test_transactions","TableWildcard":{}}}' \
    --permissions SELECT DESCRIBE --permissions-with-grant-option SELECT DESCRIBE \
    --region $REGION --output json | strip
echo ""

echo "--- AFTER Phase 1: Verify ---"
echo ""

echo ">>> aws lakeformation list-permissions --resource Database:apf_test_customers (filtered)"
aws lakeformation list-permissions --resource '{"Database":{"Name":"apf_test_customers"}}' --region $REGION --output json | filter_perms
echo ""

echo ">>> aws lakeformation list-permissions --resource Table:apf_test_customers/* (filtered)"
aws lakeformation list-permissions --resource '{"Table":{"DatabaseName":"apf_test_customers","TableWildcard":{}}}' --region $REGION --output json | filter_perms
echo ""

use_project
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation list-permissions"
aws lakeformation list-permissions --region $REGION --output json | strip
echo ""

use_dzrole
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws glue get-databases (DZ User Role — after Phase 1)"
aws glue get-databases --region $REGION --output json | strip
echo ""

echo ">>> aws glue get-tables --database-name apf_test_customers (DZ User Role — after Phase 1)"
aws glue get-tables --database-name apf_test_customers --region $REGION --output json 2>&1 | strip || true
echo ""

echo ">>> aws glue get-tables --database-name apf_test_transactions (DZ User Role — after Phase 1)"
aws glue get-tables --database-name apf_test_transactions --region $REGION --output json 2>&1 | strip || true
echo ""

# =============================================================================
# PHASE 2: Grant IAM_ALLOWED_PRINCIPALS in project account
# =============================================================================
echo "============================================================================="
echo "  PHASE 2: Grant IAM_ALLOWED_PRINCIPALS in project account"
echo "============================================================================="
echo ""

use_project
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation get-data-lake-settings (before)"
aws lakeformation get-data-lake-settings --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation put-data-lake-settings — add DomainAccess as LF admin (temporarily)"
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
aws lakeformation put-data-lake-settings --data-lake-settings "$UPDATED" --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation grant-permissions — DESCRIBE on DB apf_test_customers to IAM_ALLOWED_PRINCIPALS"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=IAM_ALLOWED_PRINCIPALS" \
    --resource '{"Database":{"Name":"apf_test_customers"}}' \
    --permissions DESCRIBE \
    --region $REGION --output json 2>&1 | strip || true
echo ""

echo ">>> aws lakeformation grant-permissions — SELECT,DESCRIBE on tables apf_test_customers/* to IAM_ALLOWED_PRINCIPALS"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=IAM_ALLOWED_PRINCIPALS" \
    --resource '{"Table":{"DatabaseName":"apf_test_customers","TableWildcard":{}}}' \
    --permissions SELECT DESCRIBE \
    --region $REGION --output json 2>&1 | strip || true
echo ""

echo ">>> aws lakeformation grant-permissions — DESCRIBE on DB apf_test_transactions to IAM_ALLOWED_PRINCIPALS"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=IAM_ALLOWED_PRINCIPALS" \
    --resource '{"Database":{"Name":"apf_test_transactions"}}' \
    --permissions DESCRIBE \
    --region $REGION --output json 2>&1 | strip || true
echo ""

echo ">>> aws lakeformation grant-permissions — SELECT,DESCRIBE on tables apf_test_transactions/* to IAM_ALLOWED_PRINCIPALS"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=IAM_ALLOWED_PRINCIPALS" \
    --resource '{"Table":{"DatabaseName":"apf_test_transactions","TableWildcard":{}}}' \
    --permissions SELECT DESCRIBE \
    --region $REGION --output json 2>&1 | strip || true
echo ""

echo ">>> aws lakeformation put-data-lake-settings — remove DomainAccess from LF admins"
CURRENT=$(aws lakeformation get-data-lake-settings --region $REGION --output json)
UPDATED=$(echo "$CURRENT" | python3 -c "
import sys,json
s=json.load(sys.stdin)['DataLakeSettings']
role='arn:aws:iam::${PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess'
s['DataLakeAdmins']=[a for a in s.get('DataLakeAdmins',[]) if a['DataLakePrincipalIdentifier']!=role]
print(json.dumps(s))")
aws lakeformation put-data-lake-settings --data-lake-settings "$UPDATED" --region $REGION --output json | strip
echo ""

echo "--- AFTER Phase 2: Verify ---"
echo ""

echo ">>> aws lakeformation list-permissions"
aws lakeformation list-permissions --region $REGION --output json | strip
echo ""

use_dzrole
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws glue get-databases (DZ User Role — after Phase 2)"
aws glue get-databases --region $REGION --output json | strip
echo ""

echo ">>> aws glue get-tables --database-name apf_test_customers (DZ User Role — after Phase 2)"
aws glue get-tables --database-name apf_test_customers --region $REGION --output json 2>&1 | strip || true
echo ""

echo ">>> aws glue get-tables --database-name apf_test_transactions (DZ User Role — after Phase 2)"
aws glue get-tables --database-name apf_test_transactions --region $REGION --output json 2>&1 | strip || true
echo ""

# =============================================================================
# PHASE 3: Cross-account grant directly to DZ Role ARN
# =============================================================================
echo "============================================================================="
echo "  PHASE 3: Cross-account grant directly to DZ Role ARN"
echo "============================================================================="
echo ""

use_domain
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation grant-permissions — DESCRIBE on DB apf_test_customers to $DZ_ROLE"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=$DZ_ROLE" \
    --resource '{"Database":{"Name":"apf_test_customers"}}' \
    --permissions DESCRIBE \
    --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation grant-permissions — SELECT,DESCRIBE on tables apf_test_customers/* to $DZ_ROLE"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=$DZ_ROLE" \
    --resource '{"Table":{"DatabaseName":"apf_test_customers","TableWildcard":{}}}' \
    --permissions SELECT DESCRIBE \
    --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation grant-permissions — DESCRIBE on DB apf_test_transactions to $DZ_ROLE"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=$DZ_ROLE" \
    --resource '{"Database":{"Name":"apf_test_transactions"}}' \
    --permissions DESCRIBE \
    --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation grant-permissions — SELECT,DESCRIBE on tables apf_test_transactions/* to $DZ_ROLE"
aws lakeformation grant-permissions \
    --principal "DataLakePrincipalIdentifier=$DZ_ROLE" \
    --resource '{"Table":{"DatabaseName":"apf_test_transactions","TableWildcard":{}}}' \
    --permissions SELECT DESCRIBE \
    --region $REGION --output json | strip
echo ""

echo "--- AFTER Phase 3: Verify ---"
echo ""

echo ">>> aws lakeformation list-permissions --resource Database:apf_test_customers (filtered)"
aws lakeformation list-permissions --resource '{"Database":{"Name":"apf_test_customers"}}' --region $REGION --output json | filter_perms
echo ""

echo ">>> aws lakeformation list-permissions --resource Table:apf_test_customers/* (filtered)"
aws lakeformation list-permissions --resource '{"Table":{"DatabaseName":"apf_test_customers","TableWildcard":{}}}' --region $REGION --output json | filter_perms
echo ""

use_project
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws lakeformation list-permissions"
aws lakeformation list-permissions --region $REGION --output json | strip
echo ""

use_dzrole
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

echo ">>> aws glue get-databases (DZ User Role — after Phase 3)"
aws glue get-databases --region $REGION --output json | strip
echo ""

echo ">>> aws glue get-tables --database-name apf_test_customers (DZ User Role — after Phase 3)"
aws glue get-tables --database-name apf_test_customers --region $REGION --output json 2>&1 | strip || true
echo ""

echo ">>> aws glue get-tables --database-name apf_test_transactions (DZ User Role — after Phase 3)"
aws glue get-tables --database-name apf_test_transactions --region $REGION --output json 2>&1 | strip || true
echo ""

echo "============================================================================="
echo "  Trace complete: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
