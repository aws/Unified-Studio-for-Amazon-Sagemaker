#!/bin/bash
# Lake Formation Grant Debug Trace
#
# Phase 1: Domain account grants to project account ID (cross-account)
# Phase 2: Project account grants to IAM_ALLOWED_PRINCIPALS (local)
#
# Before/after each phase: LF ListPermissions + Glue GetDatabases
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ">>> Switching to domain account..."
eval $(isengardcli credentials amirbo+3@amazon.com)
echo ""

echo "============================================================================="
echo "  BASELINE: State before any grants"
echo "============================================================================="
echo ""
echo ">>> [Domain Account] LF ListPermissions for project account:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_domain_grants
echo ""
echo ">>> [Project Account] LF ListPermissions + Glue GetDatabases:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_project_state
echo ""
echo ">>> [Project Account] Visibility test (get_tables on resource links):"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" test_visibility
echo ""

echo "============================================================================="
echo "  PHASE 1: Cross-account grant (domain -> project account ID)"
echo "  Source: domain account 994753223772"
echo "  Target: account ID 261399254793 (with grant option)"
echo "============================================================================="
echo ""
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" grant_cross_account
echo ""

echo "--- AFTER Phase 1 ---"
echo ""
echo ">>> [Domain Account] LF ListPermissions:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_domain_grants
echo ""
echo ">>> [Project Account] LF ListPermissions + Glue GetDatabases:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_project_state
echo ""
echo ">>> [Project Account] Visibility test:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" test_visibility
echo ""

echo "============================================================================="
echo "  PHASE 2: Local grant in project account to IAM_ALLOWED_PRINCIPALS"
echo "  Using DomainAccess role (temporarily added as LF admin)"
echo "============================================================================="
echo ""
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" grant_local_iap
echo ""

echo "--- AFTER Phase 2 ---"
echo ""
echo ">>> [Project Account] LF ListPermissions + Glue GetDatabases:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_project_state
echo ""
echo ">>> [Project Account] Visibility test:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" test_visibility
echo ""

echo "============================================================================="
echo "  PHASE 3: Cross-account grant directly to DZ Role ARN"
echo "  From domain account to the specific DZ user role"
echo "============================================================================="
echo ""
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" grant_cross_account_to_role
echo ""

echo "--- AFTER Phase 3 ---"
echo ""
echo ">>> [Domain Account] LF ListPermissions:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_domain_grants
echo ""
echo ">>> [Project Account] LF ListPermissions + Glue GetDatabases:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" check_project_state
echo ""
echo ">>> [Project Account] Visibility test:"
python3 "$SCRIPT_DIR/lf-debug-trace-helper.py" test_visibility
echo ""

echo "============================================================================="
echo "  Done."
echo "  Phase 1: domain -> account ID (cross-account share)"
echo "  Phase 2: project -> IAM_ALLOWED_PRINCIPALS (DB DESCRIBE only)"
echo "  Phase 3: domain -> DZ role ARN (cross-account direct)"
echo "============================================================================="
