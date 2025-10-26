# Shared Utilities

This folder contains common utilities and infrastructure components used by both training and deployment workflows.

## Infrastructure Setup
- `setup-workflow-role.sh` - Create IAM role for SMUS workflows
- `workflow-sagemaker-policy.json` - IAM policy for SageMaker permissions
- `workflow-trust-policy.json` - Trust policy for multiple AWS services

## Utilities
- `generate_mlflow_url.sh` - Generate MLflow tracking server URLs

## Alternative Implementations
- `ml_pipeline_notebook.ipynb` - Notebook-based ML pipeline
- `notebook_runner.py` - Execute notebooks in SageMaker Processing

## Testing
- `test_minimal.yaml` - Minimal workflow for testing
- `test_ml_workflows.sh` - Test script for workflow validation
