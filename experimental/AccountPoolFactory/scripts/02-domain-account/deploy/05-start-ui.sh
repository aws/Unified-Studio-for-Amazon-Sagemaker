#!/bin/bash
set -e

# Start the Account Pool Factory web UI.
#
# Two modes:
#   ./scripts/02-domain-account/deploy/05-start-ui.sh          # mock mode (no AWS calls)
#   ./scripts/02-domain-account/deploy/05-start-ui.sh --live   # live mode (real AWS)
#
# Live mode requires valid AWS credentials for the domain account:
#   eval $(isengardcli credentials amirbo+3@amazon.com)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
UI_DIR="$PROJECT_ROOT/ui"

MODE="${1:-}"

if [ "$MODE" = "--live" ]; then
    echo "🌐 Starting UI in LIVE mode (real AWS)..."
    echo "   Pool Console    : http://localhost:8080/pool-console/"
    echo "   Project Creator : http://localhost:8080/project-creator/"
    echo ""
    python3 "$UI_DIR/mock-server.py" --live
else
    echo "🧪 Starting UI in MOCK mode (fake data)..."
    echo "   Pool Console    : http://localhost:8080/pool-console/"
    echo "   Project Creator : http://localhost:8080/project-creator/"
    echo ""
    echo "   To use real AWS data: $0 --live"
    echo ""
    python3 "$UI_DIR/mock-server.py"
fi
