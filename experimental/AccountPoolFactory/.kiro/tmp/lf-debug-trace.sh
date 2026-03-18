#!/bin/bash
# =============================================================================
# Lake Formation Cross-Account Grant Debug Trace
# =============================================================================
#
# This script traces the full Lake Formation permission granting flow between
# the domain account and a project account, showing the state at each step.
#
# Architecture:
#   Domain Account (994753223772) - owns Glue databases + S3 data
#   Project Account (261399254793) - has resource link databases pointing to domain
#
# The flow:
#   1. Domain account grants LF permissions to project account (cross-account)
#   2. Project account grants LF permissions to the DZ user role (local)
#   3. DZ user role should see databases via Glue get_databases
#
# Prerequisites:
#   - Resource link databases already exist in project account
#   - Both accounts should be cleaned of LF grants before running
#   - Run with: eval $(isengardcli credentials amirbo+3@amazon.com)
#
# Usage:
#   bash lf-debug-trace.sh 2>&1 | tee lf-debug-trace-output.txt
# =============================================================================

set -e

REGION="us-east-2"
PROJECT_ACCOUNT="261399254793"
DOMAIN_ACCOUNT="994753223772"
DOMAIN_ID="dzd-4h7jbz76qckoh5"
PROJECT_ID="5237hturzpp5ih"
DZ_ROLE="arn:aws:iam::${PROJECT_ACCOUNT}:role/datazone_usr_role_${PROJECT_ID}_b2no4uzn8mttt5"
DOMAIN_ACCESS_ROLE="arn:aws:iam::${PROJECT_ACCOUNT}:role/SMUS-AccountPoolFactory-DomainAccess"
DBS="apf_test_customers apf_test_transactions"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================================="
echo "  Lake Formation Cross-Account Grant Debug Trace"
echo "============================================================================="
echo "  Timestamp:       $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "  Domain Account:  $DOMAIN_ACCOUNT"
echo "  Project Account: $PROJECT_ACCOUNT"
echo "  Project ID:      $PROJECT_ID"
echo "  DZ User Role:    $DZ_ROLE"
echo "  Databases:       $DBS"
echo "============================================================================="
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 0: Verify starting state (should be clean)
# ─────────────────────────────────────────────────────────────────────────────
echo "============================================================================="
echo "  PHASE 0: Verify Clean Starting State"
echo "============================================================================="
echo ""

echo ">>> [Domain Account] Switching credentials..."
eval $(isengardcli credentials amirbo+3@amazon.com)
echo "  Identity: $(aws sts get-caller-identity --region $REGION --query 'Arn' --output text)"
echo ""

echo ">>> [Domain Account] LF grants to project account $PROJECT_ACCOUNT:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_domain_grants
echo ""

echo ">>> [Project Account] LF state (via DomainAccess role):"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_project_state
echo ""

echo ">>> [Project Account] Glue get_databases as DZ user role:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" test_visibility
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: Grant cross-account LF permissions (Domain -> Project Account)
# ─────────────────────────────────────────────────────────────────────────────
echo "============================================================================="
echo "  PHASE 1: Grant Cross-Account LF Permissions (Domain -> Project Account ID)"
echo "  Granting DESCRIBE on databases + SELECT,DESCRIBE on tables"
echo "  Principal: account ID $PROJECT_ACCOUNT (with grant option)"
echo "============================================================================="
echo ""

python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" grant_cross_account
echo ""

echo ">>> [Domain Account] Verify grants exist:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_domain_grants
echo ""

echo ">>> [Project Account] Test visibility after cross-account grant only:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" test_visibility
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2: Grant local LF permissions in project account (Account -> DZ Role)
# ─────────────────────────────────────────────────────────────────────────────
echo "============================================================================="
echo "  PHASE 2: Grant Local LF Permissions in Project Account"
echo "  Using StackSetExecution role (LF admin) to grant"
echo "  Granting DESCRIBE on databases + SELECT,DESCRIBE on tables"
echo "  Principal: DZ user role $DZ_ROLE"
echo "============================================================================="
echo ""

python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" grant_local_to_role
echo ""

echo ">>> [Project Account] LF ListPermissions after local grant:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_project_state
echo ""

echo ">>> [Project Account] Test visibility after local grant:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" test_visibility
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2b: Also grant cross-account directly to the DZ role ARN
# ─────────────────────────────────────────────────────────────────────────────
echo "============================================================================="
echo "  PHASE 2b: Grant Cross-Account LF Directly to DZ Role ARN"
echo "  This is the pattern the PoolManager Lambda uses."
echo "  Granting from domain account directly to the role ARN."
echo "============================================================================="
echo ""

python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" grant_cross_account_to_role
echo ""

echo ">>> [Domain Account] LF ListPermissions after role grant:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_domain_grants
echo ""

echo ">>> [Project Account] LF ListPermissions + Glue GetDatabases:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_project_state
echo ""

echo ">>> [Project Account] Test visibility after cross-account role grant:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" test_visibility
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3: Summary
# ─────────────────────────────────────────────────────────────────────────────
echo "============================================================================="
echo "  PHASE 3: Final Summary"
echo "============================================================================="
echo ""
echo "  Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo ""
echo "  The trace above shows whether the DZ user role can see the shared"
echo "  databases after each granting step. If databases are NOT visible"
echo "  even after both cross-account and local grants, the issue is in"
echo "  how Lake Formation resolves permissions for resource link databases."
echo ""
echo "============================================================================="
