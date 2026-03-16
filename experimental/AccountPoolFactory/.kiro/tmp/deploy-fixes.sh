#!/bin/bash
# Deploy the 4 updated Lambda functions to domain account (994753223772)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"
# PROJECT_ROOT should be experimental/AccountPoolFactory
REGION="us-east-2"
TEMPLATES_DIR="$PROJECT_ROOT/templates/cloudformation/03-project-account/deploy"

echo "🔑 Switching to domain account..."
eval $(isengardcli credentials amirbo+3@amazon.com)

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "   Account: $ACCOUNT"
if [ "$ACCOUNT" != "994753223772" ]; then
    echo "❌ Wrong account! Expected 994753223772"
    exit 1
fi

echo ""
echo "📦 Packaging Lambda functions..."

zip -q "$PROJECT_ROOT/pool-manager.zip"        -j "$PROJECT_ROOT/src/pool-manager/lambda_function.py"
zip -q "$PROJECT_ROOT/account-reconciler.zip"  -j "$PROJECT_ROOT/src/account-reconciler/lambda_function.py"
zip -q "$PROJECT_ROOT/account-recycler.zip"    -j "$PROJECT_ROOT/src/account-recycler/lambda_function.py"

# Setup Orchestrator: lambda + all CF templates (same as 01-deploy.sh)
zip -q "$PROJECT_ROOT/setup-orchestrator.zip"  -j "$PROJECT_ROOT/src/setup-orchestrator/lambda_function.py"
zip -q "$PROJECT_ROOT/setup-orchestrator.zip"  -j "$TEMPLATES_DIR"/*.yaml

echo "✅ Packages created"
echo ""

deploy_lambda() {
    local name="$1" zipfile="$2"
    echo "🔄 Deploying $name..."
    aws lambda update-function-code \
        --function-name "$name" \
        --zip-file "fileb://$zipfile" \
        --region "$REGION" \
        --query 'LastModified' --output text
}

deploy_lambda PoolManager          "$PROJECT_ROOT/pool-manager.zip"
deploy_lambda SetupOrchestrator    "$PROJECT_ROOT/setup-orchestrator.zip"
deploy_lambda AccountReconciler    "$PROJECT_ROOT/account-reconciler.zip"
deploy_lambda AccountRecycler      "$PROJECT_ROOT/account-recycler.zip"

echo ""
echo "🧹 Cleaning up zip files..."
rm -f "$PROJECT_ROOT"/{pool-manager,setup-orchestrator,account-reconciler,account-recycler}.zip

echo ""
echo "✅ All 4 Lambda functions deployed!"
echo "   - PoolManager: projectId update fix"
echo "   - SetupOrchestrator: clear projectId on AVAILABLE + dynamic wave 3"
echo "   - AccountReconciler: detect deleted projects + missing StackSets"
echo "   - AccountRecycler: handle SETTING_UP state"
