#!/bin/bash
# Comprehensive workflow validation: download outputs and analyze for errors

set -e

WORKFLOW_NAME="${1:-}"
REGION="${2:-us-east-1}"
OUTPUT_DIR="tests/test-outputs/notebooks"

if [ -z "$WORKFLOW_NAME" ]; then
    echo "Usage: $0 <workflow_name> [region]"
    echo "Example: $0 IntegrationTestMLTraining_test_marketing_ml_training_workflow us-east-1"
    exit 1
fi

echo "🔍 Validating workflow: $WORKFLOW_NAME"
echo "   Region: $REGION"
echo ""

# Step 1: Download notebook outputs
echo "📥 Step 1: Downloading notebook outputs from XCom..."
python3 tests/scripts/download_workflow_outputs_from_xcom.py "$WORKFLOW_NAME" --region "$REGION" --output-dir "$OUTPUT_DIR"
DOWNLOAD_STATUS=$?

if [ $DOWNLOAD_STATUS -ne 0 ]; then
    echo "❌ Failed to download notebook outputs"
    exit 1
fi

echo ""

# Step 2: Analyze notebooks for errors
echo "🔬 Step 2: Analyzing notebooks for errors..."
python3 tests/scripts/analyze_notebook_errors.py "$OUTPUT_DIR" --verbose
ANALYSIS_STATUS=$?

echo ""

# Step 3: Summary
if [ $ANALYSIS_STATUS -eq 0 ]; then
    echo "✅ Workflow validation PASSED - no errors found"
    exit 0
else
    echo "❌ Workflow validation FAILED - errors detected"
    echo ""
    echo "To open notebooks with errors:"
    echo "  python3 tests/scripts/analyze_notebook_errors.py $OUTPUT_DIR --open-errors"
    exit 1
fi
