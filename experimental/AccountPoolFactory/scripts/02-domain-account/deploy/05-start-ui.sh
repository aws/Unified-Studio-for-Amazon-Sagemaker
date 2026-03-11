#!/bin/bash
set -e

# Start the Account Pool Factory web UI.
#
# Two modes:
#   ./scripts/02-domain-account/deploy/05-start-ui.sh          # live mode (real AWS, default)
#   ./scripts/02-domain-account/deploy/05-start-ui.sh --mock   # mock mode (no AWS calls)
#
# Live mode requires valid AWS credentials for the domain account:
#   eval $(isengardcli credentials amirbo+3@amazon.com)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
UI_DIR="$PROJECT_ROOT/ui"

MODE="${1:-}"

if [ "$MODE" = "--mock" ]; then
    echo "🧪 Starting UI in MOCK mode (fake data)..."
    echo "   Pool Console    : http://localhost:8080/pool-console/"
    echo "   Project Creator : http://localhost:8080/project-creator/"
    echo ""
    echo "   To use real AWS data: $0"
    echo ""
    python3 "$UI_DIR/mock-server.py"
else
    echo "🌐 Starting UI in LIVE mode (real AWS)..."
    echo "   Pool Console    : http://localhost:8080/pool-console/"
    echo "   Project Creator : http://localhost:8080/project-creator/"
    echo ""
    python3 "$UI_DIR/mock-server.py" --live
fi
