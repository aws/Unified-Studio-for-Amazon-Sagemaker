#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../../.."

echo "🚀 Running all integration tests in parallel..."
echo "📁 Test directory: $SCRIPT_DIR"
echo "⏰ Start time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Run pytest with xdist for parallel execution
# -n auto: automatically detect number of CPUs
# -v: verbose output
# --tb=short: shorter traceback format
pytest "$SCRIPT_DIR" \
    -n auto \
    -v \
    --tb=short \
    --color=yes

EXIT_CODE=$?

echo ""
echo "⏰ End time: $(date '+%Y-%m-%d %H:%M:%S')"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
