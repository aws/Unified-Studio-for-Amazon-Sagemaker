#!/bin/bash
set -e

# Verify pool health — runs AccountReconciler with full self-healing.
# Detects drift, recycles FAILED accounts, and replenishes if pool is low.
#
# Usage:
#   eval $(isengardcli credentials amirbo+3@amazon.com)
#   ./scripts/utils/verify-pool-health.sh           # full self-healing
#   ./scripts/utils/verify-pool-health.sh --dry-run # preview only, no changes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DRY_RUN=""
[ "$1" = "--dry-run" ] && DRY_RUN="--dry-run"

exec "$SCRIPT_DIR/invoke-reconciler.sh" --auto-recycle --auto-replenish $DRY_RUN
