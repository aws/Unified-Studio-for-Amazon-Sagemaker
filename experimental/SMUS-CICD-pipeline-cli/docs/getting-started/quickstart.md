# Quick Start Guide

← [Back to Main README](../../README.md)

**Goal:** Deploy your first data application in 10 minutes

**What you'll build:** A notebook-based data pipeline with Airflow orchestration

---

## Prerequisites

- ✅ Python 3.8+ installed
- ✅ AWS CLI configured with credentials
- ✅ SageMaker Unified Studio domain and project created
- ✅ Basic understanding of Jupyter notebooks

---

## Step 1: Install the CLI

```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

---

## Step 2: Use the Notebook Example

Copy the data notebooks example:

```bash
cp -r examples/analytic-workflow/data-notebooks my-notebook-app
cd my-notebook-app
```

This example includes:
- Sample Jupyter notebooks for data processing
- Airflow workflow for parallel execution
- Complete manifest configuration

---

## Step 3: Customize the Manifest

Edit `manifest.yaml` to match your environment:

```yaml
applicationName: MyNotebookApp  # Change this

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
      region: us-east-1  # Your AWS region
    project:
      name: my-dev-project  # Your project name
```

**What to change:**
- `applicationName`: Your application name
- `domain.region`: Your AWS region
- `project.name`: Your SageMaker Unified Studio project name

---

## Step 4: Deploy

Deploy to your dev environment:

```bash
smus-cli deploy --targets dev --manifest manifest.yaml
```

**What happens:**
1. ✅ Uploads notebooks to S3
2. ✅ Deploys Airflow workflow
3. ✅ Configures project connections
4. ✅ Ready to run!

---

## Step 5: Verify Deployment

Check your deployment in SageMaker Unified Studio console:

1. Navigate to your project
2. Go to **Workflows** section
3. Find `parallel_notebooks_execution` workflow
4. Click **Run** to execute

---

## Next Steps

### Explore More Examples

- **[ML Training](../../examples/analytic-workflow/ml/training/)** - Train models with SageMaker
- **[QuickSight Dashboard](../../examples/analytic-workflow/dashboard-glue-quick/)** - Deploy BI dashboards
- **[GenAI Application](../../examples/analytic-workflow/genai/)** - Build with Bedrock

See all examples: **[Examples Guide](../examples-guide.md)**

### Learn More

- **[Manifest Guide](../manifest.md)** - Complete configuration reference
- **[CLI Commands](../cli-commands.md)** - All available commands
- **[GitHub Actions Integration](../github-actions-integration.md)** - Automate deployments

### Set Up CI/CD

For DevOps teams: **[Admin Guide](admin-quickstart.md)** - Configure automated pipelines

---

## Troubleshooting

**Connection not found?**
- Verify your project has `default.s3_shared` and `default.workflow_serverless` connections
- Check connection names in SageMaker Unified Studio console

**Deployment fails?**
- Run `smus-cli describe --manifest manifest.yaml --connect` to validate configuration
- Check AWS credentials: `aws sts get-caller-identity`

**Need help?**
- Open an issue: [GitHub Issues](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues)
- Check documentation: [docs/](../)


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
      region: "${stage.region}"
```

**Variables are automatically replaced during deployment:**
- Dev: `dev_database`, `s3://dev-bucket`, `us-east-1`
- Test: `test_database`, `s3://test-bucket`, `us-east-1`
- Prod: `prod_database`, `s3://prod-bucket`, `us-west-2`

**Available variables:**
- `${proj.s3.root}` - Project S3 bucket
- `${proj.connection.NAME.PROPERTY}` - Connection properties
- `${stage.region}` - Target region
- `${stage.name}` - Target name (dev/test/prod)

**See more:** [Substitutions and Variables Guide](../substitutions-and-variables.md)

---

## Step 5: Validate Configuration

```bash
smus-cli describe --manifest manifest.yaml --connect
```

**Expected output:**
```
Pipeline: MyDataPipeline
Version: 1.0.0

Stages:
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

## Step 6: Create Bundle (Optional - for Bundle-Based Approach)

If using bundle-based deployment, create a versioned artifact:

```bash
# Create bundle from dev environment
smus-cli bundle --manifest manifest.yaml --stages dev
```

This creates a versioned archive containing your application content. Skip this step if using direct git-based deployment.

**See more:** [CLI Commands - bundle](../cli-commands.md#bundle)

---

## Step 7: Deploy to Test

Deploy your application to the test environment:

```bash
# Option 1: Direct deployment (git-based)
smus-cli deploy --stages test --manifest manifest.yaml

# Option 2: Bundle-based deployment (if you created a bundle in Step 6)
smus-cli deploy --stages test --manifest manifest.yaml --manifest path/to/bundle.tar.gz
```

**See more:** [CLI Commands - deploy](../cli-commands.md#deploy)

---

## Step 8: Validate in Test Environment

```bash
# Run validation tests
smus-cli test --stages test --manifest manifest.yaml

# Trigger workflow manually
smus-cli run --stages test --workflow data_processing_dag
```

**See more:** [CLI Commands - test & run](../cli-commands.md#test)

---

## Step 9: Deploy to Production

After validating in test, deploy to production:

```bash
# Deploy to production
smus-cli deploy --stages prod --manifest manifest.yaml
```

**See more:** [CLI Commands - deploy](../cli-commands.md#deploy)

---

## Step 9: Add Catalog Asset Integration (Optional)

If your workflows need DataZone catalog assets:

**Update `manifest.yaml`:**
```yaml
content:
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
smus-cli deploy --stages test --manifest manifest.yaml
```

The CLI will automatically request subscriptions to catalog assets for your project.

**See more:** [Bundle Manifest Reference - Catalog Assets](../bundle-manifest.md#catalog-assets)

---

## Step 10: Monitor and Maintain

```bash
# Monitor workflow status
smus-cli monitor --stages test --manifest manifest.yaml

# View workflow logs
smus-cli logs --workflow data_processing_dag --stages test --live

# Check deployment history
smus-cli describe --stages test --manifest manifest.yaml
```

**See more:** [CLI Commands - monitor & logs](../cli-commands.md#monitor)

---

## Advanced Features

### Multi-Stage Deployment

```yaml
# manifest.yaml
stages:
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
content:
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
  environment: ${stage.name}
  max_workers: ${config.max_workers}
  retry_count: ${config.retry_count}

tasks:
  - task_id: run_job
    operator: glue.operators.glue.GlueJobOperator
    params:
      job_name: data-processing-${stage.name}
      script_location: s3://${proj.s3.root}/scripts/process.py
      arguments:
        --ENVIRONMENT: ${stage.name}
        --MAX_WORKERS: ${config.max_workers}
```

---

## Project Structure Best Practices

A single project can contain multiple data applications, each with its own bundle:

```
my-smus-project/
├── monthly-metrics/           # Data application 1
│   ├── manifest.yaml
│   ├── workflows/
│   │   ├── metrics_etl.yaml
│   │   └── metrics_report.yaml
│   └── notebooks/
│       └── metrics_analysis.ipynb
│
├── churn-model/               # Data application 2
│   ├── manifest.yaml
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

**Ready for production?** See [Admin Quick Start](admin-quickstart.md) to set up complete infrastructure.
