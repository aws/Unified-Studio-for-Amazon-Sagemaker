#!/bin/bash
set -e

echo "=== Testing Direct Branch Deployment ==="
echo ""

# Set required environment variables
export AWS_ACCOUNT_ID=198737698272
export DEV_DOMAIN_REGION=us-east-2
export TEST_DOMAIN_REGION=us-east-2

echo "✓ Environment variables set"
echo ""

# Verify project exists
echo "1. Verifying test project exists..."
python -m smus_cicd.cli describe \
  --manifest examples/analytic-workflow/genai/manifest.yaml \
  --targets test \
  --connect | grep -q "test-marketing"

echo "✓ Project test-marketing exists"
echo ""

# Deploy directly from local filesystem (no bundle step)
echo "2. Deploying directly from local filesystem..."
python -m smus_cicd.cli deploy \
  --manifest examples/analytic-workflow/genai/manifest.yaml \
  --targets test

echo ""
echo "✓ Direct deployment successful"
echo ""

# Verify files were uploaded to S3
echo "3. Verifying files in S3..."
aws s3 ls s3://amazon-sagemaker-198737698272-us-east-2-5330xnk7amt221/shared/genai/bundle/agent-code/ | grep -q "requirements.txt"
aws s3 ls s3://amazon-sagemaker-198737698272-us-east-2-5330xnk7amt221/shared/genai/bundle/workflows/ | grep -q ".py"

echo "✓ Files verified in S3"
echo ""

echo "=== All Tests Passed! ==="
