#!/bin/bash
# Deploy updated SetupOrchestrator + DeprovisionAccount lambdas, then fix all AVAILABLE accounts
set -e
eval $(isengardcli credentials amirbo+3@amazon.com)
REGION="us-east-2"
PROJECT_ROOT="experimental/AccountPoolFactory"
TEMPLATES_DIR="$PROJECT_ROOT/templates/cloudformation/03-project-account/deploy"

echo "Step 1: Package and deploy lambdas..."

# SetupOrchestrator (needs CF templates too)
zip -q "$PROJECT_ROOT/setup-orchestrator.zip" -j "$PROJECT_ROOT/src/setup-orchestrator/lambda_function.py"
zip -q "$PROJECT_ROOT/setup-orchestrator.zip" -j "$TEMPLATES_DIR"/*.yaml
aws lambda update-function-code --function-name SetupOrchestrator --zip-file "fileb://$PROJECT_ROOT/setup-orchestrator.zip" --region "$REGION" --query 'LastModified' --output text

# DeprovisionAccount
zip -q "$PROJECT_ROOT/deprovision-account.zip" -j "$PROJECT_ROOT/src/deprovision-account/lambda_function.py"
aws lambda update-function-code --function-name DeprovisionAccount --zip-file "fileb://$PROJECT_ROOT/deprovision-account.zip" --region "$REGION" --query 'LastModified' --output text

rm -f "$PROJECT_ROOT"/{setup-orchestrator,deprovision-account}.zip
echo "Lambdas deployed."

echo ""
echo "Step 2: Trigger recycler with force=true on all AVAILABLE accounts..."
echo "This will re-run SetupOrchestrator on each AVAILABLE account,"
echo "which will call _add_datazone_roles_as_lf_admins."
aws lambda invoke --function-name AccountRecycler \
    --payload '{"recycleAll":true,"force":true}' \
    --cli-binary-format raw-in-base64-out \
    --region "$REGION" \
    /dev/stdout 2>/dev/null | python3 -m json.tool

echo ""
echo "Done. Recycler will process accounts in batches."
