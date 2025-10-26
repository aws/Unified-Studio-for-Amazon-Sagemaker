# Training Workflow

This folder contains all components for the ML training pipeline orchestration.

## Core Orchestration
- `sagemaker_ml_orchestrator.py` - Main orchestrator script (minimal version)
- `test_orchestrator_direct.py` - Direct testing of orchestrator
- `package_orchestrator_code.sh` - Package orchestrator for S3 upload

## Training Components
- `run_realistic_experiment.py` - Multi-algorithm model training with MLflow
- `sagemaker_training_script.py` - SageMaker training entry point
- `package_training_code.sh` - Package training code for S3 upload

## Model Management
- `tag_champion_model.py` - Tag best model as champion in MLflow
- `find_model_s3.py` - Discover model artifacts in S3
- `model_evaluation.py` - Model evaluation for Glue jobs

## Inference
- `run_batch_inference.py` - Batch inference with SageMaker Transform
- `s3_model_inference.py` - Direct S3 model inference

## Workflow Configuration
- `ml_dev_workflow.yaml` - SMUS workflow definition
- `run_dev_workflow.sh` - Execute training workflow

## Pipeline Flow
Training → Model Registration → Evaluation → Champion Tagging → Batch Inference
