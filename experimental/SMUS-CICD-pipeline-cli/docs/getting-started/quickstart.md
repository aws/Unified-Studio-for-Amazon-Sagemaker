# Data Team Quick Start

****Goal:** Deploy your first data application bundle in 10-15 minutes

**Audience:** DevOps teams building automated deployment pipelines for data engineering, ML, and GenAI workflows

---

## Prerequisites

- ✅ Python 3.8+ installed
- ✅ AWS CLI configured with credentials
- ✅ SageMaker Unified Studio domain and projects (dev, test, prod)
- ✅ Basic understanding of Airflow DAGs or Jupyter notebooks
- ✅ Git repository for your code (optional but recommended)

---

## Step 1: Install the CLI

```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

---

## Step 2: Create Bundle Manifest

Create a `bundle.yaml` file defining your deployment:

```yaml
bundleName: MonthlyReportAnalysis

bundle:
  storage:
    - name: monthly-report-metrics
      connectionName: default.s3_shared
      include:
        - 'workflows/'
      exclude:
        - '__pycache__/'
        - '*.pyc'

targets:
  dev:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: dev-data-project
      create: false
    
  test:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: test-data-project
      create: true
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: [admin@example.com]
    
  prod:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: prod-data-project
      create: true
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: [admin@example.com]
```

**Key sections:**
- `bundleName`: Name of your data application bundle
- `bundle`: Specify what files to deploy
- `targets`: Define dev/test/prod environments
- `initialization`: Auto-create projects with settings

**See more:** [Bundle Manifest Reference](../bundle-manifest.md)

---

## Step 3: Create Your Workflow

Choose the example that matches your use case. Workflows use SMUS YAML format for Airflow Serverless.

### Example 1: Data Engineering with Glue

Create `workflows/data_etl.yaml`:

```yaml
data_etl_pipeline:
  dag_id: "data_etl_pipeline"
  schedule_interval: "0 2 * * *"
  default_args:
    owner: "devops"
  tasks:
    transform_data:
      operator: "airflow.providers.amazon.aws.operators.glue.GlueJobOperator"
      job_name: "customer-data-transform"
      script_location: "s3://${proj.s3.root}/scripts/transform.py"
      arguments:
        --DATABASE: "${proj.connection.athena.database}"
        --OUTPUT_PATH: "s3://${proj.s3.root}/processed/"
    
    validate_data:
      operator: "airflow.providers.amazon.aws.operators.athena.AthenaOperator"
      query: |
        SELECT COUNT(*) as record_count 
        FROM ${proj.connection.athena.database}.processed_data
      output_location: "s3://${proj.s3.root}/query-results/"
      database: "${proj.connection.athena.database}"
```

### Example 2: Data Engineering with Notebooks

Create `workflows/notebook_etl.yaml`:

```yaml
notebook_etl_pipeline:
  dag_id: "notebook_etl_pipeline"
  schedule_interval: "0 3 * * *"
  default_args:
    owner: "devops"
  tasks:
    process_with_notebook:
      operator: "airflow.providers.amazon.aws.operators.sagemaker_unified_studio.SageMakerNotebookOperator"
      input_config:
        input_path: "notebooks/data_processing.ipynb"
        input_params:
          input_path: "s3://${proj.s3.root}/raw-data/"
          output_path: "s3://${proj.s3.root}/processed/"
      output_config:
        output_formats: ['NOTEBOOK']
      wait_for_completion: true
```

### Example 3: ML Training with Notebooks

Create `workflows/ml_training.yaml`:

```yaml
ml_training_pipeline:
  dag_id: "ml_training_pipeline"
  schedule_interval: "0 4 * * *"
  default_args:
    owner: "devops"
  tasks:
    prepare_data:
      operator: "airflow.providers.amazon.aws.operators.sagemaker_unified_studio.SageMakerNotebookOperator"
      input_config:
        input_path: "notebooks/prepare_features.ipynb"
        input_params:
          data_source: "${proj.connection.athena.database}.customer_features"
          output_path: "s3://${proj.s3.root}/training-data/"
      output_config:
        output_formats: ['NOTEBOOK']
      wait_for_completion: true
    
    train_model:
      operator: "airflow.providers.amazon.aws.operators.sagemaker_unified_studio.SageMakerNotebookOperator"
      input_config:
        input_path: "notebooks/train_model.ipynb"
        input_params:
          training_data: "s3://${proj.s3.root}/training-data/"
          model_output: "s3://${proj.s3.root}/models/"
      output_config:
        output_formats: ['NOTEBOOK']
      wait_for_completion: true
```

**Example notebook:** See [ml_deployment_notebook.ipynb](../../examples/analytic-workflow/ml/deployment/workflows/ml_deployment_notebook.ipynb) for a complete example showing SageMaker training, MLflow tracking, and model deployment.

### Example 4: GenAI with Bedrock

Create `workflows/bedrock_inference.yaml`:

```yaml
bedrock_inference_pipeline:
  dag_id: "bedrock_inference_pipeline"
  schedule_interval: "0 5 * * *"
  default_args:
    owner: "devops"
  tasks:
    prepare_prompts:
      operator: "airflow.providers.amazon.aws.operators.sagemaker_unified_studio.SageMakerNotebookOperator"
      input_config:
        input_path: "notebooks/prepare_prompts.ipynb"
        input_params:
          input_data: "s3://${proj.s3.root}/customer-data/"
          output_path: "s3://${proj.s3.root}/prompts/"
      output_config:
        output_formats: ['NOTEBOOK']
      wait_for_completion: true
    
    generate_insights:
      operator: "airflow.providers.amazon.aws.operators.bedrock.BedrockInvokeModelOperator"
      model_id: "anthropic.claude-v2"
      input:
        prompt: "Analyze customer feedback and provide insights"
        max_tokens: 2000
      output_location: "s3://${proj.s3.root}/insights/"
```

**Note:** For complete workflow syntax and more examples, see the [examples directory](../../examples/).

### Supported Services

**🎯 Analytics & Data Processing**
- **AWS Glue** - ETL jobs and data catalog
- **Amazon Athena** - SQL queries on S3 data
- **Amazon EMR** - Big data processing
- **Amazon Redshift** - Data warehouse operations

**🤖 Machine Learning**
- **SageMaker Notebook Operator** - Execute Jupyter notebooks in SMUS
- **Amazon SageMaker** - Training, tuning, and inference
- **SageMaker Pipelines** - ML workflow orchestration

**🧠 Generative AI**
- **Amazon Bedrock** - Foundation model inference
- **Bedrock Agents** - AI agent orchestration
- **Bedrock Knowledge Bases** - RAG applications

**📊 Other Services**
- S3, Lambda, Step Functions, DynamoDB, RDS
- See [Airflow AWS Operators](../airflow-aws-operators.md) for complete list

**See more:** [Workflow Examples](../../examples/) | [Airflow Operators Reference](../airflow-aws-operators.md)

---

## Step 4: Add Environment-Specific Configuration

Use variable substitution for environment-specific values:

**Your workflow YAML automatically uses substitution:**
```yaml
# workflows/data_processing.yaml
data_processing:
  dag_id: "data_processing"
  tasks:
    process_data:
      operator: "airflow.providers.amazon.aws.operators.athena.AthenaOperator"
      # Variables are automatically replaced during deployment
      database: "${proj.connection.athena.database}"
      output_location: "s3://${proj.s3.root}/results/"
      region: "${target.region}"
```

**Variables are automatically replaced during deployment:**
- Dev: `dev_database`, `s3://dev-bucket`, `us-east-1`
- Test: `test_database`, `s3://test-bucket`, `us-east-1`
- Prod: `prod_database`, `s3://prod-bucket`, `us-west-2`

**Available variables:**
- `${proj.s3.root}` - Project S3 bucket
- `${proj.connection.NAME.PROPERTY}` - Connection properties
- `${target.region}` - Target region
- `${target.name}` - Target name (dev/test/prod)

**See more:** [Substitutions and Variables Guide](../substitutions-and-variables.md)

---

## Step 5: Validate Configuration

```bash
smus-cli describe --bundle bundle.yaml --connect
```

**Expected output:**
```
Pipeline: MyDataPipeline
Version: 1.0.0

Targets:
  ✓ dev (dev-data-project)
  ✓ test (test-data-project)
  ✓ prod (prod-data-project)

Workflows:
  ✓ data_processing_dag (Airflow)
  ✓ ml_training_notebook (Notebook)

Bundle includes:
  - workflows/ (1 file)
  - notebooks/ (1 file)
  - config/ (0 files)

✅ Configuration valid
```

**See more:** [CLI Commands - describe](../cli-commands.md#describe)

---

## Step 6: Create Bundle and Deploy to Test

```bash
# Create bundle from dev environment
smus-cli bundle --bundle bundle.yaml --targets dev

# Deploy to test environment
smus-cli deploy --targets test --bundle bundle.yaml
```

**See more:** [CLI Commands - bundle & deploy](../cli-commands.md#bundle)

---

## Step 7: Validate in Test Environment

```bash
# Run validation tests
smus-cli test --targets test --bundle bundle.yaml

# Trigger workflow manually
smus-cli run --targets test --workflow data_processing_dag
```

**See more:** [CLI Commands - test & run](../cli-commands.md#test)

---

## Step 8: Deploy to Production

After validating in test, deploy to production:

```bash
# Deploy to production
smus-cli deploy --targets prod --bundle bundle.yaml
```

**See more:** [CLI Commands - deploy](../cli-commands.md#deploy)

---

## Step 9: Add Catalog Asset Integration (Optional)

If your workflows need DataZone catalog assets:

**Update `bundle.yaml`:**
```yaml
bundle:
  catalog:
    assets:
      - selector:
          search:
            assetType: GlueTable
            identifier: my_database.my_table
        permission: READ
        requestReason: Required for data processing pipeline
```

**Deploy with catalog integration:**
```bash
smus-cli deploy --targets test --bundle bundle.yaml
```

The CLI will automatically request subscriptions to catalog assets for your project.

**See more:** [Bundle Manifest Reference - Catalog Assets](../bundle-manifest.md#catalog-assets)

---

## Step 10: Monitor and Maintain

```bash
# Monitor workflow status
smus-cli monitor --targets test --bundle bundle.yaml

# View workflow logs
smus-cli logs --workflow data_processing_dag --targets test --live

# Check deployment history
smus-cli describe --targets test --bundle bundle.yaml
```

**See more:** [CLI Commands - monitor & logs](../cli-commands.md#monitor)

---

## Advanced Features

### Multi-Stage Deployment

```yaml
# bundle.yaml
targets:
  test:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: test-data-project
    
  prod:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: prod-data-project
```

### Custom Bundle Configuration

```yaml
bundle:
  include:
    - workflows/
    - notebooks/
    - data/*.csv
  exclude:
    - "**/__pycache__"
    - "**/.pytest_cache"
    - "**/test_*.py"
```

### Parameterized Workflows

```yaml
# workflows/parameterized_dag.yaml
dag_id: parameterized_processing
schedule: "0 * * * *"

# Parameters injected at deployment time
default_args:
  environment: ${target.name}
  max_workers: ${config.max_workers}
  retry_count: ${config.retry_count}

tasks:
  - task_id: run_job
    operator: glue.operators.glue.GlueJobOperator
    params:
      job_name: data-processing-${target.name}
      script_location: s3://${proj.s3.root}/scripts/process.py
      arguments:
        --ENVIRONMENT: ${target.name}
        --MAX_WORKERS: ${config.max_workers}
```

---

## Project Structure Best Practices

A single project can contain multiple data applications, each with its own bundle:

```
my-smus-project/
├── monthly-metrics/           # Data application 1
│   ├── bundle.yaml
│   ├── workflows/
│   │   ├── metrics_etl.yaml
│   │   └── metrics_report.yaml
│   └── notebooks/
│       └── metrics_analysis.ipynb
│
├── churn-model/               # Data application 2
│   ├── bundle.yaml
│   ├── workflows/
│   │   ├── feature_engineering.yaml
│   │   └── model_training.yaml
│   ├── notebooks/
│   │   ├── prepare_features.ipynb
│   │   └── train_model.ipynb
│   └── tests/
│       └── test_model.py
│
└── README.md
```

Each data application is self-contained with its own bundle manifest and can be deployed independently.

---

## Next Steps

### Learn More
- **[Bundle Manifest Reference](../bundle-manifest.md)** - Complete YAML guide
- **[Variable Substitution](../substitutions-and-variables.md)** - Dynamic configuration
- **[CLI Commands](../cli-commands.md)** - All available commands
- **[GitHub Actions Integration](../github-actions-integration.md)** - CI/CD automation

### Explore Examples
- See [examples directory](../../examples/) for complete working examples

### Set Up Infrastructure
- **[Admin Quick Start](admin-quickstart.md)** - Configure projects and resources

---

## Troubleshooting

### Variable Substitution Not Working
```bash
# Debug variable resolution
smus-cli describe --bundle bundle.yaml --targets test --verbose
```

### Workflow Not Syncing to MWAA
```bash
# Check bundle contents
smus-cli bundle --bundle bundle.yaml --targets dev --verbose

# Verify deployment
smus-cli monitor --targets test --workflows
```

### Tests Failing
```bash
# Run tests with verbose output
smus-cli test --targets test --bundle bundle.yaml --verbose

# Check individual workflow execution
smus-cli run --targets test --workflow my_dag
```

---

**Ready for production?** See [Admin Quick Start](admin-quickstart.md) to set up complete infrastructure.
