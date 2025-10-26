#!/bin/bash

# Test script for split SageMaker ML workflows in SMUS CICD pipeline

set -e

echo "=== Testing Split SageMaker ML Workflows for SMUS CICD ==="

# Configuration
DEV_WORKFLOW="ml_dev_workflow"
DEPLOY_WORKFLOW="ml_deploy_workflow"
S3_BUCKET="${S3_BUCKET:-demo-bucket-smus-ml-us-west-2}"
ACCOUNT_ID="${ACCOUNT_ID:-123456789012}"

echo "Configuration:"
echo "  Dev Workflow: $DEV_WORKFLOW"
echo "  Deploy Workflow: $DEPLOY_WORKFLOW"
echo "  S3 Bucket: $S3_BUCKET"
echo "  Account ID: $ACCOUNT_ID"

# Check workflow files
for workflow in "ml_dev_workflow.yaml" "ml_deploy_workflow.yaml"; do
    if [ ! -f "$workflow" ]; then
        echo "ERROR: $workflow not found"
        exit 1
    fi
    echo "✓ $workflow found"
done

# Check support scripts
for script in "model_evaluation.py" "get_champion_model.py"; do
    if [ ! -f "$script" ]; then
        echo "ERROR: $script not found"
        exit 1
    fi
    echo "✓ $script found"
done

# Validate YAML syntax
echo "Validating YAML syntax..."
for workflow in "ml_dev_workflow.yaml" "ml_deploy_workflow.yaml"; do
    python3 -c "import yaml; yaml.safe_load(open('$workflow'))" || {
        echo "ERROR: Invalid YAML syntax in $workflow"
        exit 1
    }
    echo "✓ $workflow syntax valid"
done

# Validate dev workflow structure
echo "Validating dev workflow..."
python3 -c "
import yaml
with open('ml_dev_workflow.yaml') as f:
    workflow = yaml.safe_load(f)

tasks = workflow['ml_dev_workflow']['tasks']
required_tasks = ['model_training', 'model_evaluation', 'champion_tagging', 'batch_inference']

for task in required_tasks:
    assert task in tasks, f'Missing task: {task}'

# Check dependencies
assert 'model_training' in tasks['model_evaluation']['dependencies']
assert 'model_evaluation' in tasks['champion_tagging']['dependencies']
assert 'champion_tagging' in tasks['batch_inference']['dependencies']

print('✓ Dev workflow structure valid')
"

# Validate deploy workflow structure
echo "Validating deploy workflow..."
python3 -c "
import yaml
with open('ml_deploy_workflow.yaml') as f:
    workflow = yaml.safe_load(f)

tasks = workflow['ml_deploy_workflow']['tasks']
required_tasks = ['champion_model_retrieval', 'model_registration', 'endpoint_deployment', 'endpoint_testing']

for task in required_tasks:
    assert task in tasks, f'Missing task: {task}'

# Check dependencies
assert 'champion_model_retrieval' in tasks['model_registration']['dependencies']
assert 'model_registration' in tasks['endpoint_deployment']['dependencies']
assert 'endpoint_deployment' in tasks['endpoint_testing']['dependencies']

print('✓ Deploy workflow structure valid')
"

# Check stage parameterization
echo "Validating stage parameterization..."
python3 -c "
import yaml
with open('ml_deploy_workflow.yaml') as f:
    content = f.read()
    
# Check for stage variables
assert '{{ var.value.stage }}' in content, 'Missing stage parameterization'
assert 'endpoint_instance_type' in content, 'Missing instance type parameterization'

print('✓ Stage parameterization valid')
"

echo ""
echo "=== Split ML Workflows Test Summary ==="
echo "✓ All tests passed!"
echo ""
echo "Workflows created:"
echo "1. DEV WORKFLOW (ml_dev_workflow.yaml):"
echo "   - model_training → model_evaluation → champion_tagging → batch_inference"
echo "   - Runs in dev stage for training and evaluation"
echo ""
echo "2. DEPLOY WORKFLOW (ml_deploy_workflow.yaml):"
echo "   - champion_model_retrieval → model_registration → endpoint_deployment → endpoint_testing"
echo "   - Runs in test/prod stages using champion model"
echo ""
echo "Environment variables needed:"
echo "- account_id: $ACCOUNT_ID"
echo "- s3_bucket: $S3_BUCKET"
echo "- stage: dev|test|prod"
echo "- mlflow_tracking_uri: MLflow server URL"
echo "- endpoint_instance_type: ml.t2.medium (optional)"
