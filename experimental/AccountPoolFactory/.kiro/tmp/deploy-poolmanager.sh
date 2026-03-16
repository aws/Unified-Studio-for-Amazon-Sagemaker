#!/bin/bash
eval $(isengardcli credentials amirbo+3@amazon.com)
REGION="us-east-2"
ROOT="experimental/AccountPoolFactory"
TEMPLATES="$ROOT/templates/cloudformation/03-project-account/deploy"

echo "Deploying PoolManager..."
zip -q "$ROOT/pool-manager.zip" -j "$ROOT/src/pool-manager/lambda_function.py"
aws lambda update-function-code --function-name PoolManager --zip-file "fileb://$ROOT/pool-manager.zip" --region "$REGION" --query 'LastModified' --output text

echo "Deploying SetupOrchestrator..."
zip -q "$ROOT/setup-orchestrator.zip" -j "$ROOT/src/setup-orchestrator/lambda_function.py"
zip -q "$ROOT/setup-orchestrator.zip" -j "$TEMPLATES"/*.yaml
aws lambda update-function-code --function-name SetupOrchestrator --zip-file "fileb://$ROOT/setup-orchestrator.zip" --region "$REGION" --query 'LastModified' --output text

rm -f "$ROOT"/{pool-manager,setup-orchestrator}.zip
echo "Done"
