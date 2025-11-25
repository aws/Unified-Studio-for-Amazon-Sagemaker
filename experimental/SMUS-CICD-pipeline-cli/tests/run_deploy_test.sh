#!/bin/bash
set -e

echo "🚀 Quick Deployment Test"
echo "========================"
echo ""

# Check if venv exists
VENV_PATH="/tmp/deploy_test_env"
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Test environment not found. Run ./debug_deployment.sh first"
    exit 1
fi

# Activate venv
source "$VENV_PATH/bin/activate"

# Run test
cd "$(dirname "$0")/.."
python3 tests/test_deployment_local.py

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Test PASSED"
else
    echo "❌ Test FAILED"
fi

exit $EXIT_CODE
