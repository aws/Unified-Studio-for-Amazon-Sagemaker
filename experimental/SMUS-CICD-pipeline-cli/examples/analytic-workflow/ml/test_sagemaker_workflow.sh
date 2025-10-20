#!/bin/bash

# Test script for SageMaker ML workflow in SMUS CICD pipeline
# Following the pattern from experimental/SMUS-CICD-pipeline-cli/examples/analytic-workflow/etl

set -e

echo "=== Testing SageMaker ML Workflow for SMUS CICD ==="

# Configuration
WORKFLOW_NAME="ml_inference_workflow_smus"
S3_BUCKET="${S3_BUCKET:-demo-bucket-smus-ml-us-west-2}"
ACCOUNT_ID="${ACCOUNT_ID:-123456789012}"
REGION="${AWS_REGION:-us-west-2}"

echo "Configuration:"
echo "  Workflow: $WORKFLOW_NAME"
echo "  S3 Bucket: $S3_BUCKET"
echo "  Account ID: $ACCOUNT_ID"
echo "  Region: $REGION"

# Check if workflow file exists
if [ ! -f "ml_workflow.yaml" ]; then
    echo "ERROR: ml_workflow.yaml not found"
    exit 1
fi

# Check if training script exists
if [ ! -f "sagemaker_training_script.py" ]; then
    echo "ERROR: sagemaker_training_script.py not found"
    exit 1
fi

echo "✓ Workflow files found"

# Validate YAML syntax
echo "Validating YAML syntax..."
python3 -c "import yaml; yaml.safe_load(open('ml_workflow.yaml'))" || {
    echo "ERROR: Invalid YAML syntax in ml_workflow.yaml"
    exit 1
}
echo "✓ YAML syntax valid"

# Check AWS credentials
echo "Checking AWS credentials..."
aws sts get-caller-identity > /dev/null || {
    echo "ERROR: AWS credentials not configured"
    exit 1
}
echo "✓ AWS credentials configured"

# Create test data for training
echo "Creating test training data..."
python3 -c "
import pandas as pd
import numpy as np

# Create sample training data
np.random.seed(42)
X = np.random.randn(100, 5)
y = np.random.choice([0, 1, 2], 100)
df = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(5)])
df['target'] = y
df.to_csv('test_training_data.csv', index=False)
print('Test training data created')
"
echo "✓ Test data created"

# Upload training script to S3 (simulated)
echo "Simulating S3 upload of training script..."
echo "aws s3 cp sagemaker_training_script.py s3://$S3_BUCKET/scripts/"
echo "aws s3 cp test_training_data.csv s3://$S3_BUCKET/training-data/"
echo "✓ S3 upload simulation complete"

# Validate workflow structure
echo "Validating workflow structure..."
python3 -c "
import yaml
with open('ml_workflow.yaml') as f:
    workflow = yaml.safe_load(f)

# Check required structure
assert 'ml_inference_workflow_smus' in workflow
wf = workflow['ml_inference_workflow_smus']
assert 'dag_id' in wf
assert 'tasks' in wf

# Check required tasks
required_tasks = ['model_training', 'model_registration', 'endpoint_deployment', 'batch_inference']
for task in required_tasks:
    assert task in wf['tasks'], f'Missing task: {task}'
    assert 'operator' in wf['tasks'][task], f'Missing operator in task: {task}'

print('✓ Workflow structure valid')
"

# Check SageMaker operators
echo "Validating SageMaker operators..."
python3 -c "
import yaml
with open('ml_workflow.yaml') as f:
    workflow = yaml.safe_load(f)

tasks = workflow['ml_inference_workflow_smus']['tasks']
expected_operators = {
    'model_training': 'SageMakerTrainingOperator',
    'model_registration': 'SageMakerModelOperator', 
    'endpoint_deployment': 'SageMakerEndpointOperator',
    'batch_inference': 'SageMakerTransformOperator'
}

for task, expected_op in expected_operators.items():
    operator = tasks[task]['operator']
    assert expected_op in operator, f'Wrong operator for {task}: {operator}'

print('✓ SageMaker operators valid')
"

# Check dependencies
echo "Validating task dependencies..."
python3 -c "
import yaml
with open('ml_workflow.yaml') as f:
    workflow = yaml.safe_load(f)

tasks = workflow['ml_inference_workflow_smus']['tasks']

# Check dependency chain
assert 'model_training' not in tasks or 'dependencies' not in tasks['model_training']
assert 'model_training' in tasks['model_registration']['dependencies']
assert 'model_registration' in tasks['endpoint_deployment']['dependencies']  
assert 'endpoint_deployment' in tasks['batch_inference']['dependencies']

print('✓ Task dependencies valid')
"

# Cleanup test files
echo "Cleaning up test files..."
rm -f test_training_data.csv
echo "✓ Cleanup complete"

echo ""
echo "=== ML Workflow Test Summary ==="
echo "✓ All tests passed!"
echo "✓ Workflow ready for SMUS CICD pipeline deployment"
echo ""
echo "Next steps:"
echo "1. Upload training script to S3: aws s3 cp sagemaker_training_script.py s3://$S3_BUCKET/scripts/"
echo "2. Deploy using SMUS CICD CLI with environment variables:"
echo "   - account_id: $ACCOUNT_ID"
echo "   - s3_bucket: $S3_BUCKET"
echo "3. Monitor workflow execution in Airflow UI"
