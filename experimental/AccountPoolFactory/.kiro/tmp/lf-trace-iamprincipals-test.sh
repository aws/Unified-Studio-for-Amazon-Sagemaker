#!/bin/bash
# Test different IAMPrincipals variations for cross-account LF grants
# All grants from domain (source) account only
# Using Table wildcard with DESCRIBE + SELECT
set -e

REGION="us-east-2"
PROJECT_ACCOUNT="261399254793"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SAVE_AKI="$AWS_ACCESS_KEY_ID"
SAVE_SAK="$AWS_SECRET_ACCESS_KEY"
SAVE_ST="$AWS_SESSION_TOKEN"
use_domain() {
    export AWS_ACCESS_KEY_ID="$SAVE_AKI"
    export AWS_SECRET_ACCESS_KEY="$SAVE_SAK"
    export AWS_SESSION_TOKEN="$SAVE_ST"
}
use_dzrole() { eval $(use_domain; python3 "$SCRIPT_DIR/lf-trace-creds-dzrole.py"); }
strip() { python3 -c "
import sys,json
s=sys.stdin.read().strip()
if not s: print('(no output)')
elif s[0] in ('{','['): d=json.loads(s);isinstance(d,dict) and d.pop('ResponseMetadata',None);print(json.dumps(d,indent=2,default=str))
else: print(s)"; }

echo "============================================================================="
echo "  Test IAMPrincipals variations for cross-account LF grants"
echo "  Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "  Source (domain): 994753223772"
echo "  Target (project): $PROJECT_ACCOUNT"
echo "  Test DB: apf_test_customers"
echo "============================================================================="
echo ""

use_domain
echo ">>> aws sts get-caller-identity"
aws sts get-caller-identity --region $REGION --output json | strip
echo ""

# Variations to try
VARIATIONS=(
    "${PROJECT_ACCOUNT}:IAMPrincipals"
    "${PROJECT_ACCOUNT}:AllIAMPrincipals"
    "${PROJECT_ACCOUNT}:IAM_ALLOWED_PRINCIPALS"
)

for PRINCIPAL in "${VARIATIONS[@]}"; do
    echo "============================================================================="
    echo "  Trying principal: $PRINCIPAL"
    echo "============================================================================="
    echo ""

    echo ">>> aws lakeformation grant-permissions — DESCRIBE on DB apf_test_customers to $PRINCIPAL"
    aws lakeformation grant-permissions \
        --principal "DataLakePrincipalIdentifier=$PRINCIPAL" \
        --resource '{"Database":{"Name":"apf_test_customers"}}' \
        --permissions DESCRIBE \
        --region $REGION --output json 2>&1 | strip
    echo ""

    echo ">>> aws lakeformation grant-permissions — DESCRIBE,SELECT on Table wildcard apf_test_customers to $PRINCIPAL"
    aws lakeformation grant-permissions \
        --principal "DataLakePrincipalIdentifier=$PRINCIPAL" \
        --resource '{"Table":{"DatabaseName":"apf_test_customers","TableWildcard":{}}}' \
        --permissions DESCRIBE SELECT \
        --region $REGION --output json 2>&1 | strip
    echo ""

    # Quick check — did it work?
    echo ">>> [DZ User Role] aws glue get-databases (checking visibility)"
    use_dzrole
    aws glue get-databases --region $REGION --output json | python3 -c "
import sys,json
dbs=json.load(sys.stdin)['DatabaseList']
names=[d['Name'] for d in dbs]
print('  Visible databases:', names)
found='apf_test_customers' in names
print('  apf_test_customers visible:', found)"
    echo ""

    # Revoke before next attempt
    use_domain
    echo ">>> Revoking grants for $PRINCIPAL..."
    aws lakeformation revoke-permissions \
        --principal "DataLakePrincipalIdentifier=$PRINCIPAL" \
        --resource '{"Database":{"Name":"apf_test_customers"}}' \
        --permissions DESCRIBE \
        --region $REGION --output json 2>&1 | strip
    aws lakeformation revoke-permissions \
        --principal "DataLakePrincipalIdentifier=$PRINCIPAL" \
        --resource '{"Table":{"DatabaseName":"apf_test_customers","TableWildcard":{}}}' \
        --permissions DESCRIBE SELECT \
        --region $REGION --output json 2>&1 | strip
    echo ""
done

echo "============================================================================="
echo "  Done: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================================="
