# Example Applications

← [Back to Main README](../README.md)

This guide walks through real-world example applications showing how to deploy different types of workloads with SMUS CI/CD.

## Available Examples

### 📊 Data Engineering - Notebooks
**Path:** `examples/analytic-workflow/data-notebooks/`

Deploy Jupyter notebooks with Airflow orchestration for data analysis and ETL workflows.

**What it includes:**
- Jupyter notebooks for data processing
- Airflow workflow for parallel notebook execution
- S3 storage for notebooks and data
- Multi-stage deployment (dev, test)

**Key manifest features:**
```yaml
applicationName: IntegrationTestNotebooks

content:
  storage:
    - name: notebooks
      connectionName: default.s3_shared
      include: ['notebooks/', 'workflows/']
  workflows:
    - workflowName: parallel_notebooks_execution
      connectionName: default.workflow_serverless

stages:
  dev:
    domain:
      region: us-east-2
    project:
      name: dev-marketing
  test:
    domain:
      region: us-east-1
    project:
      name: test-notebooks
      create: true
      owners: [Eng1]
```

**Use this example when:**
- Building data analysis pipelines with notebooks
- Need to orchestrate multiple notebooks
- Want to deploy notebooks across environments

---

### 🤖 Machine Learning - Training
**Path:** `examples/analytic-workflow/ml/training/`

Train ML models with SageMaker and track experiments with MLflow.

**What it includes:**
- Python training scripts
- SageMaker training job configuration
- MLflow experiment tracking
- Model artifacts storage

**Key manifest features:**
```yaml
applicationName: MLTrainingPipeline

content:
  git:
    - repository: ml-training-code
      url: https://github.com/myorg/ml-training.git
  storage:
    - name: training-data
      connectionName: default.s3_shared
      include: ['data/']
  workflows:
    - workflowName: train_model
      connectionName: project.workflow_serverless

stages:
  dev:
    environment_variables:
      MODEL_TYPE: xgboost
      EPOCHS: 10
  prod:
    environment_variables:
      MODEL_TYPE: xgboost
      EPOCHS: 100
```

**Use this example when:**
- Training ML models with SageMaker
- Need experiment tracking with MLflow
- Want environment-specific training parameters

---

### 🤖 Machine Learning - Deployment
**Path:** `examples/analytic-workflow/ml/deployment/`

Deploy trained ML models as SageMaker endpoints for real-time inference.

**What it includes:**
- Model deployment scripts
- SageMaker endpoint configuration
- Inference testing workflows
- Model monitoring setup

**Key manifest features:**
```yaml
applicationName: MLDeploymentPipeline

content:
  storage:
    - name: model-artifacts
      connectionName: default.s3_shared
      include: ['models/']
  workflows:
    - workflowName: deploy_endpoint
      connectionName: project.workflow_serverless

stages:
  test:
    environment_variables:
      INSTANCE_TYPE: ml.t2.medium
      INSTANCE_COUNT: 1
  prod:
    environment_variables:
      INSTANCE_TYPE: ml.m5.xlarge
      INSTANCE_COUNT: 2
```

**Use this example when:**
- Deploying ML models to production
- Need different instance types per environment
- Want automated endpoint deployment

---

### 📊 Analytics - QuickSight Dashboard
**Path:** `examples/analytic-workflow/dashboard-glue-quick/`

Deploy QuickSight dashboards with Glue ETL pipelines for business intelligence.

**What it includes:**
- Glue ETL jobs for data preparation
- QuickSight dashboard definitions
- Athena queries for data access
- Automated dashboard deployment

**Key manifest features:**
```yaml
applicationName: AnalyticsDashboard

content:
  storage:
    - name: etl-scripts
      connectionName: default.s3_shared
      include: ['glue/']
  quicksight:
    - dashboardId: sales-dashboard
      assetBundle: quicksight/sales-dashboard.qs
  workflows:
    - workflowName: prepare_data
      connectionName: project.workflow_serverless

stages:
  dev:
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: dev-
  prod:
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: prod-
```

**Use this example when:**
- Building BI dashboards with QuickSight
- Need data preparation with Glue
- Want environment-specific dashboard configurations

---

### 🧠 Generative AI
**Path:** `examples/analytic-workflow/genai/`

Deploy GenAI applications with Bedrock agents and knowledge bases.

**What it includes:**
- Bedrock agent configurations
- Knowledge base setup
- RAG (Retrieval Augmented Generation) workflows
- Agent testing and validation

**Key manifest features:**
```yaml
applicationName: GenAIApplication

content:
  storage:
    - name: agent-config
      connectionName: default.s3_shared
      include: ['agents/', 'knowledge-bases/']
  workflows:
    - workflowName: deploy_agent
      connectionName: project.workflow_serverless

stages:
  dev:
    environment_variables:
      BEDROCK_MODEL: anthropic.claude-v2
      KNOWLEDGE_BASE: dev-kb
  prod:
    environment_variables:
      BEDROCK_MODEL: anthropic.claude-v2:1
      KNOWLEDGE_BASE: prod-kb
```

**Use this example when:**
- Building GenAI applications with Bedrock
- Need knowledge base integration
- Want to deploy AI agents across environments

---

## Quick Start with Examples

### 1. Choose an Example
Pick the example that matches your use case from above.

### 2. Copy the Example
```bash
cp -r examples/analytic-workflow/data-notebooks my-application
cd my-application
```

### 3. Customize the Manifest
Edit `manifest.yaml`:
- Change `applicationName` to your app name
- Update `project.name` for your stages
- Adjust `domain.region` to your AWS region
- Modify environment variables as needed

### 4. Deploy
```bash
# Deploy to dev
smus-cli deploy --targets dev --manifest manifest.yaml

# Deploy to test
smus-cli deploy --targets test --manifest manifest.yaml
```

## Example Structure

Each example follows this structure:
```
example-name/
├── manifest.yaml          # Application deployment manifest
├── notebooks/            # Jupyter notebooks (if applicable)
├── scripts/              # Python scripts
├── workflows/            # Airflow DAG definitions
├── glue/                 # Glue job scripts (if applicable)
├── quicksight/           # QuickSight assets (if applicable)
└── README.md             # Example-specific documentation
```

## Next Steps

- **[Manifest Guide](manifest.md)** - Learn about all manifest options
- **[CLI Commands](cli-commands.md)** - Explore available commands
- **[Substitutions & Variables](substitutions-and-variables.md)** - Use dynamic configuration
- **[GitHub Actions Integration](github-actions-integration.md)** - Automate deployments

## Need Help?

- Check the [Quick Start Guide](getting-started/quickstart.md) for step-by-step instructions
- Review the [Admin Guide](getting-started/admin-quickstart.md) for infrastructure setup
- Open an issue on [GitHub](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues)
