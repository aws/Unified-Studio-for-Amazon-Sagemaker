# Example Applications

← [Back to Main README](../README.md)

This guide provides detailed walkthroughs of real-world example applications showing how to deploy different types of workloads with SMUS CI/CD.

## Available Examples

### 📊 Data Engineering - Notebooks
**Path:** [`examples/analytic-workflow/data-notebooks/`](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/experimental/SMUS-CICD-pipeline-cli/examples/analytic-workflow/data-notebooks)

Deploy Jupyter notebooks with Airflow orchestration for data analysis and ETL workflows. Demonstrates parallel notebook execution with MLflow integration for experiment tracking.

**What it includes:**
- 9 Jupyter notebooks covering various data engineering patterns
- Airflow workflow for parallel notebook execution
- MLflow connection for experiment tracking
- S3 storage for notebooks and data
- Multi-stage deployment (dev, test)
- Integration tests for notebook execution

**Complete manifest:**
```yaml
applicationName: IntegrationTestNotebooks

content:
  storage:
    - name: notebooks
      connectionName: default.s3_shared
      include:
        - notebooks/
        - workflows/
  
  workflows:
    - workflowName: parallel_notebooks_execution
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-1
    project:
      name: test-marketing
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
    environment_variables:
      S3_PREFIX: test
    deployment_configuration:
      storage:
        - name: notebooks
          connectionName: default.s3_shared
          targetDirectory: notebooks/bundle/notebooks
        - name: workflows
          connectionName: default.s3_shared
          targetDirectory: notebooks/bundle/workflows
    bootstrap:
      actions:
        - type: datazone.create_connection
          name: mlflow-server
          connection_type: MLFLOW
          properties:
            trackingServerArn: arn:aws:sagemaker:${STS_REGION}:${STS_ACCOUNT_ID}:mlflow-tracking-server/smus-integration-mlflow-use2
        - type: workflow.create
          workflowName: parallel_notebooks_execution
        - type: workflow.run
          workflowName: parallel_notebooks_execution
          trailLogs: true

tests:
  folder: examples/analytic-workflow/data-notebooks/app_tests/
```

**Key features explained:**
- **MLflow Connection**: Created before workflow to enable experiment tracking in notebooks
- **Parallel Execution**: Workflow orchestrates multiple notebooks running concurrently
- **Trail Logs**: `trailLogs: true` streams execution logs during deployment
- **Test Integration**: Validates notebook execution after deployment

**Use this example when:**
- Building data analysis pipelines with notebooks
- Need to orchestrate multiple notebooks in parallel
- Want experiment tracking with MLflow
- Deploying notebooks across environments

---

### 🤖 Machine Learning - Training
**Path:** [`examples/analytic-workflow/ml/training/`](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/experimental/SMUS-CICD-pipeline-cli/examples/analytic-workflow/ml/training)

Train ML models with SageMaker using the SageMaker SDK and SageMaker Distribution images. Track experiments with MLflow and automate training pipelines with environment-specific configurations.

**What it includes:**
- Python training scripts using SageMaker SDK
- SageMaker training job configuration
- MLflow experiment tracking integration
- Model artifacts storage with compression
- Airflow workflow for training orchestration
- Environment-specific training parameters

**Complete manifest:**
```yaml
applicationName: IntegrationTestMLTraining

content:
  storage:
    - name: training-code
      connectionName: default.s3_shared
      include:
        - code
    
    - name: training-workflows
      connectionName: default.s3_shared
      include:
        - workflows
  
  workflows:
    - workflowName: ml_training_workflow
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-1
    project:
      name: test-ml-training
      create: true
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
      role:
        arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/SMUSCICDTestRole
    environment_variables:
      S3_PREFIX: test
    deployment_configuration:
      storage:
        - name: training-code
          connectionName: default.s3_shared
          targetDirectory: ml/bundle/training-code
          compression: gz
        - name: training-workflows
          connectionName: default.s3_shared
          targetDirectory: ml/bundle/training-workflows
    bootstrap:
      actions:
        - type: datazone.create_connection
          name: mlflow-server
          connection_type: MLFLOW
          properties:
            trackingServerArn: arn:aws:sagemaker:${STS_REGION}:${STS_ACCOUNT_ID}:mlflow-tracking-server/smus-integration-mlflow-use2
        - type: workflow.create
          workflowName: ml_training_workflow
        - type: workflow.run
          workflowName: ml_training_workflow
          trailLogs: true

tests:
  folder: examples/analytic-workflow/ml/training/app_tests/
```

**Key features explained:**
- **Compression**: Training code is compressed with `compression: gz` to reduce upload time
- **Custom Role**: Uses project-specific IAM role for SageMaker training permissions
- **MLflow Integration**: Tracks experiments, parameters, and metrics automatically
- **SageMaker Distribution**: Uses pre-built images with common ML libraries
- **Project Creation**: `create: true` automatically creates project if it doesn't exist

**Use this example when:**
- Training ML models with SageMaker
- Need experiment tracking with MLflow
- Want environment-specific training parameters
- Building automated ML training pipelines

---

### 🤖 Machine Learning - Deployment
**Path:** [`examples/analytic-workflow/ml/deployment/`](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/experimental/SMUS-CICD-pipeline-cli/examples/analytic-workflow/ml/deployment)

Deploy trained ML models as SageMaker real-time inference endpoints. Uses SageMaker SDK for endpoint configuration and SageMaker Distribution images for serving.

**What it includes:**
- Model deployment scripts
- SageMaker endpoint configuration
- Model artifacts from training
- Inference testing workflows
- Airflow orchestration for deployment
- Environment-specific instance types

**Complete manifest:**
```yaml
applicationName: IntegrationTestMLDeployment

content:
  storage:
    - name: deployment-code
      connectionName: default.s3_shared
      include:
        - ml/deployment/code
    
    - name: deployment-workflows
      connectionName: default.s3_shared
      include:
        - ml/deployment/workflows
    
    - name: model-artifacts
      connectionName: default.s3_shared
      include:
        - ml/output/model-artifacts/latest
  
  workflows:
    - workflowName: ml_deployment_workflow
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-1
    project:
      name: test-ml-deployment
      create: true
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
      role:
        arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/SMUSCICDTestRole
    environment_variables:
      S3_PREFIX: test
      INSTANCE_TYPE: ml.t2.medium
      INSTANCE_COUNT: 1
    deployment_configuration:
      storage:
        - name: deployment-code
          connectionName: default.s3_shared
          targetDirectory: ml/bundle/deployment-code
        - name: deployment-workflows
          connectionName: default.s3_shared
          targetDirectory: ml/bundle/deployment-workflows
        - name: model-artifacts
          connectionName: default.s3_shared
          targetDirectory: ml/bundle/model-artifacts
    bootstrap:
      actions:
        - type: workflow.create
          workflowName: ml_deployment_workflow
        - type: workflow.run
          workflowName: ml_deployment_workflow
          trailLogs: true
```

**Key features explained:**
- **Model Artifacts**: Deploys latest trained model from training pipeline
- **Environment Variables**: Configure instance type and count per environment
- **Endpoint Management**: Workflow handles endpoint creation, update, and validation
- **Cost Optimization**: Use smaller instances in test, larger in production

**Production configuration example:**
```yaml
  prod:
    environment_variables:
      S3_PREFIX: prod
      INSTANCE_TYPE: ml.m5.xlarge
      INSTANCE_COUNT: 2
      AUTO_SCALING_MIN: 2
      AUTO_SCALING_MAX: 10
```

**Use this example when:**
- Deploying ML models to production
- Need different instance types per environment
- Want automated endpoint deployment
- Building ML inference services

---

### 📊 Analytics - QuickSight Dashboard
**Path:** [`examples/analytic-workflow/dashboard-glue-quick/`](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/experimental/SMUS-CICD-pipeline-cli/examples/analytic-workflow/dashboard-glue-quick)

Deploy interactive BI dashboards with automated Glue ETL pipelines for data preparation. Uses QuickSight asset bundles, Athena queries, and GitHub dataset integration with environment-specific configurations.

**What it includes:**
- Glue ETL jobs for database setup and data transformation
- QuickSight dashboard definitions (asset bundles)
- Athena queries for data access
- GitHub dataset integration (COVID-19 data)
- Automated dashboard deployment and refresh
- Permission management for QuickSight access

**Complete manifest:**
```yaml
applicationName: IntegrationTestETLWorkflow

content:
  storage:
    - name: dashboard-glue-quick
      connectionName: default.s3_shared
      include:
        - "*.py"
        - "*.yaml"
        - manifest.yaml
  
  git:
    - repository: covid-19-dataset
      url: https://github.com/datasets/covid-19.git
  
  quicksight:
    - name: TotalDeathByCountry
      type: dashboard
  
  workflows:
    - workflowName: covid_dashboard_glue_quick_pipeline
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-1
    project:
      name: test-marketing
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
    environment_variables:
      S3_PREFIX: test
      GRANT_TO: Admin,service-role/aws-quicksight-service-role-v0
    deployment_configuration:
      storage:
        - name: dashboard-glue-quick
          connectionName: default.s3_shared
          targetDirectory: dashboard-glue-quick/bundle
      git:
        - name: covid-19-dataset
          connectionName: default.s3_shared
          targetDirectory: repos
      quicksight:
        assets:
          - name: TotalDeathByCountry
            owners:
              - arn:aws:quicksight:${TEST_DOMAIN_REGION:us-east-1}:*:user/default/Admin/*
            viewers:
              - arn:aws:quicksight:${TEST_DOMAIN_REGION:us-east-1}:*:user/default/Admin/*
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: deployed-{stage.name}-covid-
          Dashboards:
            - DashboardId: e0772d4e-bd69-444e-a421-cb3f165dbad8
              Name: TotalDeathByCountry-{stage.name}
    bootstrap:
      actions:
        - type: workflow.create
          workflowName: covid_dashboard_glue_quick_pipeline
        - type: workflow.run
          workflowName: covid_dashboard_glue_quick_pipeline
          trailLogs: true
        - type: quicksight.refresh_dataset
          refreshScope: IMPORTED
          ingestionType: FULL_REFRESH
          wait: false

tests:
  folder: examples/analytic-workflow/dashboard-glue-quick/app_tests/
```

**Key features explained:**
- **Git Integration**: Clones COVID-19 dataset from GitHub during deployment
- **Glue Pipeline**: Three-step ETL process (setup DB → transform data → set permissions)
- **QuickSight Asset Bundle**: Deploys dashboard, datasets, and data sources together
- **Resource Prefixing**: Uses `{stage.name}` to create environment-specific resources
- **Dataset Refresh**: Automatically refreshes QuickSight data after ETL completes
- **Permission Management**: Grants access to specified QuickSight users/roles

**Workflow execution order:**
1. Deploy Glue scripts and workflow definition
2. Create workflow in MWAA Serverless
3. Run workflow (setup DB → ETL → permissions)
4. Refresh QuickSight datasets with new data

**Use this example when:**
- Building BI dashboards with QuickSight
- Need data preparation with Glue
- Want environment-specific dashboard configurations
- Integrating external datasets from GitHub

---

### 🧠 Generative AI
**Path:** [`examples/analytic-workflow/genai/`](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/experimental/SMUS-CICD-pipeline-cli/examples/analytic-workflow/genai)

Deploy GenAI applications with Bedrock agents and knowledge bases. Demonstrates RAG (Retrieval Augmented Generation) workflows with automated agent deployment and testing.

**What it includes:**
- Bedrock agent configurations
- Knowledge base setup scripts
- RAG workflow implementation
- Agent testing and validation
- Airflow orchestration for deployment
- Environment-specific model configurations

**Complete manifest:**
```yaml
applicationName: IntegrationTestGenAIWorkflow

content:
  storage:
    - name: agent-code
      connectionName: default.s3_shared
      include:
        - job-code
    
    - name: genai-workflows
      connectionName: default.s3_shared
      include:
        - workflows
  
  workflows:
    - workflowName: genai_dev_workflow
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-1
    project:
      name: test-marketing
      create: true
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
      role:
        arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/test-marketing-role
    environment_variables:
      S3_PREFIX: test
      BEDROCK_MODEL: anthropic.claude-v2
      KNOWLEDGE_BASE: test-kb
    deployment_configuration:
      storage:
        - name: agent-code
          connectionName: default.s3_shared
          targetDirectory: genai/bundle/agent-code
        - name: genai-workflows
          connectionName: default.s3_shared
          targetDirectory: genai/bundle/workflows
    bootstrap:
      actions:
        - type: workflow.create
          workflowName: genai_dev_workflow
        - type: workflow.run
          workflowName: genai_dev_workflow
          trailLogs: true

tests:
  folder: examples/analytic-workflow/genai/app_tests/
```

**Key features explained:**
- **Bedrock Integration**: Configures agents with foundation models
- **Knowledge Base**: Sets up vector database for RAG
- **Environment Variables**: Different models and knowledge bases per environment
- **Custom Role**: Project-specific IAM role with Bedrock permissions
- **Automated Testing**: Validates agent responses after deployment

**Production configuration example:**
```yaml
  prod:
    environment_variables:
      S3_PREFIX: prod
      BEDROCK_MODEL: anthropic.claude-v2:1
      KNOWLEDGE_BASE: prod-kb
      MAX_TOKENS: 4096
      TEMPERATURE: 0.7
```

**Use this example when:**
- Building GenAI applications with Bedrock
- Need knowledge base integration for RAG
- Want to deploy AI agents across environments
- Building conversational AI applications

---

## Bootstrap Actions Explained

All examples use bootstrap actions to automate deployment tasks. Here's the standard pattern:

```yaml
bootstrap:
  actions:
    # 1. Create connections (if needed)
    - type: datazone.create_connection
      name: mlflow-server
      connection_type: MLFLOW
      properties:
        trackingServerArn: arn:aws:sagemaker:${STS_REGION}:${STS_ACCOUNT_ID}:mlflow-tracking-server/name
    
    # 2. Create workflows (REQUIRED)
    - type: workflow.create
      workflowName: my_workflow
    
    # 3. Run workflows
    - type: workflow.run
      workflowName: my_workflow
      trailLogs: true  # Stream logs during deployment
    
    # 4. Additional actions
    - type: quicksight.refresh_dataset
      refreshScope: IMPORTED
```

**Why this order matters:**
1. **Connections first**: Workflows may reference connections (like MLflow)
2. **Create before run**: Workflows must exist before they can be executed
3. **Trail logs**: `trailLogs: true` provides real-time feedback during deployment

See [Bootstrap Actions Guide](bootstrap-actions.md) for complete documentation.

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
- Update IAM role ARNs to match your account

### 4. Validate
```bash
smus-cli describe --manifest manifest.yaml --connect
```

### 5. Deploy
```bash
# Deploy to test
smus-cli deploy --targets test --manifest manifest.yaml

# Run tests
smus-cli test --manifest manifest.yaml --targets test
```

---

## Example Structure

Each example follows this structure:
```
example-name/
├── manifest.yaml          # Application deployment manifest
├── notebooks/            # Jupyter notebooks (if applicable)
├── code/                 # Python scripts
├── workflows/            # Airflow DAG definitions
├── glue/                 # Glue job scripts (if applicable)
├── quicksight/           # QuickSight assets (if applicable)
├── app_tests/            # Integration tests
└── README.md             # Example-specific documentation
```

---

## Environment Variables

All examples support environment-specific configuration through variables:

**Common variables:**
- `S3_PREFIX`: Prefix for S3 paths (dev, test, prod)
- `AWS_REGION`: AWS region for resources
- `AWS_ACCOUNT_ID`: AWS account ID (auto-resolved)
- `STS_REGION`: Current STS region (auto-resolved)
- `STS_ACCOUNT_ID`: Current STS account (auto-resolved)

**Example-specific variables:**
- ML Training: `MODEL_TYPE`, `EPOCHS`, `LEARNING_RATE`
- ML Deployment: `INSTANCE_TYPE`, `INSTANCE_COUNT`
- GenAI: `BEDROCK_MODEL`, `KNOWLEDGE_BASE`, `MAX_TOKENS`
- QuickSight: `GRANT_TO` (users/roles with access)

See [Substitutions & Variables Guide](substitutions-and-variables.md) for complete documentation.

---

## Testing

All examples include integration tests in `app_tests/` directory:

```bash
# Run tests after deployment
smus-cli test --manifest manifest.yaml --targets test
```

**What tests validate:**
- Workflow execution completed successfully
- Resources created correctly
- Data processed as expected
- Endpoints responding (for ML deployment)
- Dashboards accessible (for QuickSight)

---

## Next Steps

- **[Manifest Guide](manifest.md)** - Learn about all manifest options
- **[CLI Commands](cli-commands.md)** - Explore available commands
- **[Bootstrap Actions](bootstrap-actions.md)** - Automate deployment tasks
- **[Substitutions & Variables](substitutions-and-variables.md)** - Use dynamic configuration
- **[GitHub Actions Integration](github-actions-integration.md)** - Automate deployments

---

## Need Help?

- Check the [Quick Start Guide](getting-started/quickstart.md) for step-by-step instructions
- Review the [Admin Guide](getting-started/admin-quickstart.md) for infrastructure setup
- Open an issue on [GitHub](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues)
