# ML Workflow for SageMaker Unified Studio

Complete MLOps pipeline with model training, promotion, and inference.

## Structure

```
ml/
├── src/
│   ├── sagemaker_train_realistic.py  # Main training script (4 models comparison)
│   ├── inference.py                  # SageMaker inference handler
│   └── requirements.txt              # Dependencies
├── scripts/
│   ├── run_realistic_experiment.py   # Run training experiment
│   ├── tag_champion_model.py         # Promote model to champion
│   ├── find_model_s3.py             # Discover S3 model artifacts
│   ├── run_batch_inference.py        # MLflow + Batch Transform inference
│   ├── s3_model_inference.py         # Direct S3 model inference
│   └── generate_mlflow_url.sh        # Generate MLflow UI URL
├── config/                           # Training job configurations
└── README.md
```

## Quick Start

1. **Train Models**: `python scripts/run_realistic_experiment.py`
2. **Promote Best Model**: `python scripts/tag_champion_model.py`
3. **Run Inference**: `python scripts/run_batch_inference.py`

## Features

- ✅ 4-model comparison (RF, GB, LR, SVM)
- ✅ MLflow experiment tracking
- ✅ Model registry with champion promotion
- ✅ Multiple inference pathways
- ✅ CICD-ready scripts
