#!/bin/bash

# Cleanup Script for SMUS CICD Demo Resources
# This script cleans up resources created during the full pipeline lifecycle demo

set -e

echo "🧹 SMUS CICD Demo Resource Cleanup"
echo "=================================="

# Configuration
PIPELINE_FILE="${1:-DemoMarketingPipeline.yaml}"
DOMAIN_NAME="${2:-cicd-test-domain}"
PROJECT_NAME="${3:-dev-marketing}"

echo "Pipeline File: $PIPELINE_FILE"
echo "Domain Name: $DOMAIN_NAME"
echo "Project Name: $PROJECT_NAME"
echo ""

# Check if CLI is installed
if ! command -v smus-cli &> /dev/null; then
    echo "❌ smus-cli not found. Please install it first:"
    echo "   cd experimental/SMUS-CICD-pipeline-cli"
    echo "   pip install -e ."
    exit 1
fi

# Check if pipeline file exists
if [ ! -f "$PIPELINE_FILE" ]; then
    echo "❌ Pipeline file not found: $PIPELINE_FILE"
    echo "Available pipeline files:"
    ls -1 *.yaml 2>/dev/null || echo "  No .yaml files found"
    exit 1
fi

echo "🔍 Checking existing resources..."

# List current targets to see what exists
echo ""
echo "Current pipeline targets:"
smus-cli describe --pipeline "$PIPELINE_FILE" --targets || echo "  No targets found or pipeline invalid"

echo ""
echo "🗑️  Cleaning up demo resources..."

# Delete test target (most common demo target)
echo ""
echo "Deleting test target..."
smus-cli delete \
  --pipeline "$PIPELINE_FILE" \
  --targets test \
  --force || echo "  No test target to clean up"

# Delete staging target if it exists
echo ""
echo "Deleting staging target..."
smus-cli delete \
  --pipeline "$PIPELINE_FILE" \
  --targets staging \
  --force || echo "  No staging target to clean up"

# Delete prod target if it exists
echo ""
echo "Deleting prod target..."
smus-cli delete \
  --pipeline "$PIPELINE_FILE" \
  --targets prod \
  --force || echo "  No prod target to clean up"

# Delete any other common demo targets
echo ""
echo "Deleting other demo targets..."
for target in demo example marketing analytics; do
    smus-cli delete \
      --pipeline "$PIPELINE_FILE" \
      --targets "$target" \
      --force 2>/dev/null || echo "  No $target target to clean up"
done

echo ""
echo "✅ Cleanup completed!"
echo ""
echo "📋 Summary:"
echo "  - Attempted cleanup of common demo targets: test, staging, prod, demo, example, marketing, analytics"
echo "  - Use --force flag was used to avoid confirmation prompts"
echo "  - Errors for non-existent targets are expected and ignored"
echo ""
echo "🔍 To verify cleanup, run:"
echo "  smus-cli describe --pipeline $PIPELINE_FILE --targets --connect"
echo ""
echo "💡 To clean up specific targets manually:"
echo "  smus-cli delete --pipeline $PIPELINE_FILE --targets <target-name> --force"
