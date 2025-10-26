# Deployment Workflow

This folder contains all components for the ML deployment pipeline orchestration.

## Core Components
- `get_champion_model.py` - Retrieve champion model from MLflow registry
- `create_sagemaker_endpoint.py` - Deploy SageMaker real-time endpoint
- `test_sagemaker_endpoint.py` - Test deployed endpoint with sample data
- `cleanup_endpoint.py` - Clean up endpoint resources

## Workflow Configuration
- `ml_deploy_workflow.yaml` - SMUS workflow definition
- `run_deploy_workflow.sh` - Execute deployment workflow

## Pipeline Flow
Champion Retrieval → Model Creation → Endpoint Deployment → Testing → Cleanup

## Usage
```bash
# Deploy to test environment
./run_deploy_workflow.sh us-west-2 test

# Deploy to production environment  
./run_deploy_workflow.sh us-west-2 prod
```
