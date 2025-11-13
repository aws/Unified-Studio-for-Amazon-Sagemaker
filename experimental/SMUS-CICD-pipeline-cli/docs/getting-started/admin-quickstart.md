# Admin Quick Start

**Goal:** Understand and configure SMUS CI/CD infrastructure for data teams

**Audience:** Platform administrators and DevOps engineers setting up deployment pipelines

---

## Prerequisites

- ✅ AWS account with admin access
- ✅ SageMaker Unified Studio domain created
- ✅ Python 3.8+ and AWS CLI installed
- ✅ Understanding of AWS IAM and S3

---

## Overview

As an admin, you'll configure:
- **Bundle targets** - Test and Prod environments where data applications deploy
- **Project initialization** - Automated project creation with proper settings
- **CI/CD pipelines** - GitHub Actions or similar automation
- **Monitoring** - Deployment validation and health checks

**Key concept:** A SMUS project is a deployment target. Multiple data application bundles can deploy to the same target.

---

## Step 1: Install the CLI

```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

---

## Step 2: Understand Bundle Targets

A **target** is a SMUS project where bundles deploy. Data teams typically use:
- **Dev** - Local development (not a deployment target, used for bundling only)
- **Test** - Integration testing and validation
- **Prod** - Production deployment

### Target Configuration

Each target in `bundle.yaml` specifies:

```yaml
targets:
  test:
    domain:
      name: my-domain          # SMUS domain name
      region: us-east-1        # AWS region
    project:
      name: test-project       # SMUS project name
      create: true             # Let CLI create project
    initialization:            # Project creation settings
      project:
        create: true
        profileName: 'All capabilities'
        owners: [admin@example.com]
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
```

**Key points:**
- `create: false` - Project already exists (typical for dev)
- `create: true` - CLI will create project on first deployment
- `initialization` - Only used when `create: true`

---

## Step 3: Configure Project Initialization

When `create: true`, the CLI automatically creates projects with these settings:

### Basic Project Creation

```yaml
initialization:
  project:
    create: true
    profileName: 'All capabilities'    # Project profile
    owners:                             # Project owners
      - admin@example.com
      - arn:aws:iam::123456789:role/GitHubActionsRole
```

### With Environment Configuration

```yaml
initialization:
  project:
    create: true
    profileName: 'All capabilities'
    owners: [admin@example.com]
  environments:
    - EnvironmentConfigurationName: 'OnDemand Workflows'  # Enables MWAA
```

**Available profiles:**
- `All capabilities` - Full analytics, ML, and GenAI
- `Analytics` - Data engineering only
- `ML and AI` - Machine learning only

---

## Step 4: Set Up Multi-Target Configuration

Create a reference `bundle.yaml` for your organization:

```yaml
bundleName: CustomerChurnModel

bundle:
  storage:
    - name: data-platform-workflows
      connectionName: default.s3_shared
      include:
        - 'workflows/'

targets:
  test:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: test-data-platform
      create: true
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: [arn:aws:iam::123456789:role/GitHubActionsRole]
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
    
  prod:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: prod-data-platform
      create: true
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: [arn:aws:iam::123456789:role/GitHubActionsRole]
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
```

**Note:** Dev project is typically created manually in the console by data teams.

---

## Step 5: Configure Project Connections

Connections define integrations with AWS services and data sources. They can be created automatically during project initialization or manually via the console.

### Default Connections

SMUS projects automatically include these connections:
- `default.s3_shared` - Project S3 bucket
- `project.workflow_mwaa` - MWAA environment (if OnDemand Workflows enabled)
- `project.athena` - Athena workgroup
- `project.default_lakehouse` - Lakehouse connection

### Create Connections via Manifest

The recommended approach is to define connections in the bundle manifest under `initialization.connections`:

```yaml
targets:
  test:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: test-data-platform
      create: true
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: [admin@example.com]
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
      
      # Connections created automatically during initialization
      connections:
        - name: s3-raw-data
          type: S3
          properties:
            s3Uri: "s3://raw-data-bucket/incoming/"
        
        - name: spark-etl
          type: SPARK_GLUE
          properties:
            glueVersion: "4.0"
            workerType: "G.2X"
            numberOfWorkers: 10
        
        - name: athena-analytics
          type: ATHENA
          properties:
            workgroupName: "analytics-workgroup"
        
        - name: redshift-warehouse
          type: REDSHIFT
          properties:
            storage:
              clusterName: "analytics-cluster"
            databaseName: "analytics"
            host: "analytics-cluster.abc123.us-east-1.redshift.amazonaws.com"
            port: 5439
```

### Supported Connection Types

#### S3 - Object Storage
```yaml
- name: s3-data-lake
  type: S3
  properties:
    s3Uri: "s3://my-data-bucket/data/"
```

#### SPARK_GLUE - Spark on AWS Glue
```yaml
- name: spark-processing
  type: SPARK_GLUE
  properties:
    glueVersion: "4.0"
    workerType: "G.1X"
    numberOfWorkers: 5
```

#### ATHENA - SQL Query Engine
```yaml
- name: athena-analytics
  type: ATHENA
  properties:
    workgroupName: "primary"
```

#### REDSHIFT - Data Warehouse
```yaml
- name: redshift-warehouse
  type: REDSHIFT
  properties:
    storage:
      clusterName: "analytics-cluster"
    databaseName: "analytics"
    host: "analytics-cluster.abc123.us-east-1.redshift.amazonaws.com"
    port: 5439
```

#### SPARK_EMR - Spark on EMR
```yaml
- name: spark-emr
  type: SPARK_EMR
  properties:
    computeArn: "arn:aws:emr-serverless:us-east-1:123456789012:/applications/00abc123def456"
    runtimeRole: "arn:aws:iam::123456789012:role/EMRServerlessExecutionRole"
```

#### MLFLOW - ML Experiment Tracking
```yaml
- name: mlflow-experiments
  type: MLFLOW
  properties:
    trackingServerName: "ml-tracking-server"
    trackingServerArn: "arn:aws:sagemaker:us-east-1:123456789012:mlflow-tracking-server/ml-tracking-server"
```

#### WORKFLOWS_MWAA - Apache Airflow
```yaml
- name: mwaa-workflows
  type: WORKFLOWS_MWAA
  properties:
    mwaaEnvironmentName: "production-airflow-env"
```

#### WORKFLOWS_SERVERLESS - Serverless Airflow
```yaml
- name: serverless-workflows
  type: WORKFLOWS_SERVERLESS
  properties: {}
```

**See more:** [Bundle Manifest Reference - Connections](../bundle-manifest.md#connections)

### Create Connections Manually (Console)

For existing projects, you can also create connections via the SMUS console:

1. Navigate to SMUS project
2. Go to **Connections** tab
3. Click **Create connection**
4. Select connection type and configure properties

### Reference Connections in Workflows

Data teams reference these connections in their workflows using variable substitution:

```yaml
# workflows/data_processing.yaml
tasks:
  load_from_redshift:
    operator: "airflow.providers.amazon.aws.transfers.redshift_to_s3.RedshiftToS3Operator"
    redshift_conn_id: "${proj.connection.redshift_warehouse.id}"
    s3_bucket: "${proj.s3.root}"
    s3_key: "data/export.csv"
```

**See more:** [Substitutions and Variables Guide](../substitutions-and-variables.md)

---

## Step 6: Understand CLI Usage Across Stages

The CLI is used differently at each stage:

### Development Stage (Data Teams)
```bash
# Data teams work in their dev project
# They create bundles FROM dev environment
smus-cli bundle --bundle bundle.yaml --targets dev
```

### Testing Stage (CI/CD or Data Teams)
```bash
# Deploy bundle TO test environment
smus-cli deploy --targets test --bundle bundle.yaml

# Validate deployment
smus-cli test --targets test --bundle bundle.yaml

# Check logs
smus-cli logs --targets test --workflow my_workflow --live

# Monitor health
smus-cli monitor --targets test --bundle bundle.yaml
```

### Production Stage (CI/CD)
```bash
# Deploy to production after test validation
smus-cli deploy --targets prod --bundle bundle.yaml

# Monitor production deployment
smus-cli monitor --targets prod --bundle bundle.yaml
```

**Key insight:** 
- `bundle` creates from dev
- `deploy` deploys to test/prod
- `test`, `logs`, `monitor` validate deployments

---

## Step 7: Understand Multiple Bundles per Target

A single SMUS project (target) can host multiple data application bundles. Each bundle is self-contained and can be deployed and promoted to production independently:

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

Each bundle deploys independently to the same target:
```bash
# Deploy and promote monthly-metrics bundle
cd monthly-metrics
smus-cli deploy --targets test --bundle bundle.yaml
smus-cli deploy --targets prod --bundle bundle.yaml

# Deploy and promote churn-model bundle separately
cd ../churn-model
smus-cli deploy --targets test --bundle bundle.yaml
smus-cli deploy --targets prod --bundle bundle.yaml
```

All workflows from both bundles appear in the same MWAA environment within the project.

---

## Step 8: Set Up GitHub Actions CI/CD

Create `.github/workflows/deploy.yml` for automated deployments:

```yaml
name: Deploy Data Application

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install SMUS CLI
        run: |
          git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
          cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
          pip install -e .
      
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: arn:aws:iam::123456789:role/GitHubActionsRole
          aws-region: us-east-1
      
      - name: Create Bundle
        run: smus-cli bundle --bundle bundle.yaml --targets dev
      
      - name: Deploy to Test
        run: smus-cli deploy --targets test --bundle bundle.yaml
      
      - name: Validate Deployment
        run: smus-cli test --targets test --bundle bundle.yaml
      
      - name: Check Deployment Health
        run: smus-cli monitor --targets test --bundle bundle.yaml

  deploy-prod:
    needs: deploy-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Production
        run: smus-cli deploy --targets prod --bundle bundle.yaml
      
      - name: Monitor Production
        run: smus-cli monitor --targets prod --bundle bundle.yaml
```

**See more:** [GitHub Actions Integration Guide](../github-actions-integration.md)

---

## Step 9: Validate Deployment with Monitoring

After deployment, use these commands to verify everything works:

### Check Deployment Status
```bash
# View overall bundle health
smus-cli monitor --targets test --bundle bundle.yaml
```

**Output:**
```
Target: test
Project: test-data-platform
Status: ✓ Healthy

Workflows:
  ✓ metrics_etl (Active, Last run: Success)
  ✓ model_training (Active, Last run: Success)

Storage:
  ✓ workflows/ (3 files synced)

Connections:
  ✓ default.s3_shared
  ✓ project.workflow_mwaa
```

### View Workflow Logs
```bash
# Live logs for specific workflow
smus-cli logs --targets test --workflow metrics_etl --live

# Historical logs
smus-cli logs --targets test --workflow metrics_etl --date 2025-01-13
```

### Run Tests
```bash
# Execute validation tests
smus-cli test --targets test --bundle bundle.yaml
```

**Output:**
```
Running tests for target: test

✓ Workflow files validated
✓ Connections accessible
✓ S3 storage accessible
✓ MWAA environment healthy

All tests passed
```

---

## Step 10: Set Up Monitoring and Metrics Integration

### CloudWatch Integration

The CLI automatically creates CloudWatch metrics for deployments:

```bash
# View deployment metrics
aws cloudwatch get-metric-statistics \
  --namespace SMUS/CICD \
  --metric-name DeploymentSuccess \
  --dimensions Name=Target,Value=test \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-13T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

### Create CloudWatch Dashboard

```bash
# Create monitoring dashboard
aws cloudwatch put-dashboard \
  --dashboard-name SMUS-CICD-Monitor \
  --dashboard-body file://dashboard.json
```

**dashboard.json:**
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["SMUS/CICD", "DeploymentSuccess", {"stat": "Sum"}],
          [".", "DeploymentFailure", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Deployment Status"
      }
    }
  ]
}
```

### Set Up Alerts

```bash
# Create SNS topic for alerts
aws sns create-topic --name smus-cicd-alerts

# Create alarm for deployment failures
aws cloudwatch put-metric-alarm \
  --alarm-name smus-deployment-failures \
  --alarm-description "Alert on SMUS deployment failures" \
  --metric-name DeploymentFailure \
  --namespace SMUS/CICD \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-east-1:123456789:smus-cicd-alerts
```

---

## Step 11: Document for Data Teams

Create team documentation explaining the setup:

**`docs/deployment-guide.md`:**
```markdown
# Data Application Deployment Guide

## Overview
Our SMUS projects are configured as deployment targets:
- **test-data-platform** - Testing and validation
- **prod-data-platform** - Production deployment

Multiple data applications can deploy to the same project.

## Deployment Process
1. Develop in your dev project
2. Create bundle: `smus-cli bundle --bundle bundle.yaml --targets dev`
3. Push to GitHub → Automatic deployment to test
4. After validation → Automatic deployment to prod

## Monitoring Your Deployment
- Check status: `smus-cli monitor --targets test --bundle bundle.yaml`
- View logs: `smus-cli logs --targets test --workflow YOUR_WORKFLOW --live`
- Run tests: `smus-cli test --targets test --bundle bundle.yaml`

## Support
- Slack: #data-platform-support
- Email: platform-team@example.com
```

---

## Troubleshooting

### Project Creation Fails
```bash
# Check initialization settings
smus-cli describe --bundle bundle.yaml --targets test --verbose

# Verify IAM permissions for project creation
aws sts get-caller-identity
```

### Deployment Not Syncing
```bash
# Check bundle contents
smus-cli bundle --bundle bundle.yaml --targets dev --verbose

# Verify MWAA connection
smus-cli monitor --targets test --workflows
```

### Multiple Bundles Conflicting
```bash
# List all workflows in target
smus-cli monitor --targets test --all-workflows

# Check for naming conflicts
smus-cli describe --targets test --bundle bundle.yaml
```

---

## Next Steps

### For Data Teams
- **[Data Team Quick Start](quickstart.md)** - Guide for building and deploying bundles

### Advanced Configuration
- **[Bundle Manifest Reference](../bundle-manifest.md)** - Complete YAML specification
- **[CLI Commands Reference](../cli-commands.md)** - All available commands
- **[Monitoring and Metrics](../monitoring-and-metrics.md)** - Detailed monitoring setup

### Examples
- See [examples directory](../../examples/) for complete working examples

---

## Key Takeaways

1. **Projects are targets** - One SMUS project can host multiple data application bundles
2. **Dev is for bundling** - Data teams create bundles FROM dev, deploy TO test/prod
3. **Initialization is automatic** - CLI creates projects with proper settings on first deployment
4. **Monitoring is essential** - Use `monitor`, `logs`, and `test` commands to validate deployments
5. **CI/CD automates flow** - GitHub Actions handles bundle → test → prod progression

**Questions?** Contact the platform team for support.
