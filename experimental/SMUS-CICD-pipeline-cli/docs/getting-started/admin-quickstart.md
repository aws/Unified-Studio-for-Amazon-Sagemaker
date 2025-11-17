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
- **Deployment stages** - Test and Prod environments where data applications deploy
- **Project initialization** - Automated project creation with proper settings
- **CI/CD pipelines** - GitHub Actions or similar automation
- **Monitoring** - Deployment validation and health checks

**Key concept:** A SMUS project is a deployment target. Multiple data applications can deploy to the same target using different deployment approaches (direct git-based, bundle-based, or hybrid).

---

## Step 1: Install the CLI

```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

---

## Step 2: Understand Deployment Stages

A **stage** is a SMUS project where data applications deploy. Data teams typically use:
- **Dev** - Local development (optional deployment target, used for testing)
- **Test** - Integration testing and validation
- **Prod** - Production deployment

### Deployment Approaches

The CLI supports three deployment approaches:

1. **Direct Git-Based** - Deploy directly from git branches to stages (no bundle creation)
2. **Bundle-Based** - Create versioned bundles, then deploy them to stages (all content from bundle)
3. **Hybrid** - Create bundle for static content (data, configs), pull workflows from git branches per stage

**See more:** [Deployment Approaches Guide](../deployment-approaches.md)

### Stage Configuration

Each stage in `manifest.yaml` specifies:

```yaml
stages:
  test:
    domain:
      name: my-domain          # SMUS domain name
      region: us-east-1        # AWS region
    project:
      name: test-project       # SMUS project name
      create: true             # Let CLI create project
    bootstrap:            # Project creation settings
      project:
        create: true
        profileName: 'All capabilities'
        owners: [admin@example.com]
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
```

**Key points:**
- `create: false` - Project already exists, CLI will deploy to it
- `create: true` - CLI will create project on first deployment
- `initialization` - Only used when `create: true`

### Project Isolation Models

The `create` flag enables two organizational models:

**Shared Projects (create: false)** - Multiple applications deploy to the same test/prod projects:
```yaml
# Application 1: monthly-metrics/manifest.yaml
stages:
  test:
    project:
      name: shared-data-platform-test
      create: false  # Use existing shared project
  prod:
    project:
      name: shared-data-platform-prod
      create: false

# Application 2: churn-model/manifest.yaml
stages:
  test:
    project:
      name: shared-data-platform-test
      create: false  # Same shared project
  prod:
    project:
      name: shared-data-platform-prod
      create: false
```

**Isolated Projects (create: true)** - Each application gets its own dedicated projects:
```yaml
# Application 1: monthly-metrics/manifest.yaml
stages:
  test:
    project:
      name: monthly-metrics-test
      create: true  # Create dedicated project
    bootstrap:
      project:
        create: true
        profileName: 'Analytics'
        owners: [metrics-team@example.com]
  prod:
    project:
      name: monthly-metrics-prod
      create: true

# Application 2: churn-model/manifest.yaml
stages:
  test:
    project:
      name: churn-model-test
      create: true  # Create separate dedicated project
    bootstrap:
      project:
        create: true
        profileName: 'ML and AI'
        owners: [ml-team@example.com]
  prod:
    project:
      name: churn-model-prod
      create: true
```

**When to use each model:**
- **Shared projects** - Teams collaborating, shared resources, centralized governance
- **Isolated projects** - Team autonomy, different profiles/permissions, cost isolation

---

## Step 3: Configure Project Initialization

When `create: true`, the CLI automatically creates projects with these settings:

### Basic Project Creation

```yaml
bootstrap:
  project:
    create: true
    profileName: 'All capabilities'    # Project profile
    owners:                             # Project owners
      - admin@example.com
      - arn:aws:iam::123456789:role/GitHubActionsRole
```

### With Environment Configuration

```yaml
bootstrap:
  project:
    create: true
    profileName: 'All capabilities'
    owners: [admin@example.com]
  environments:
    - EnvironmentConfigurationName: 'OnDemand Workflows'  # Enables MWAA
```

---

## Step 4: Set Up Multi-Stage Configuration

Create a reference `manifest.yaml` for your organization:

```yaml
applicationName: CustomerChurnModel

content:
  git:
    - repository: customer-churn-model
      url: https://github.com/myorg/customer-churn-model.git
  storage:
    - name: data-platform-workflows
      connectionName: default.s3_shared
      include:
        - 'workflows/'

stages:
  test:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: test-data-platform
      create: true
    bootstrap:
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
    bootstrap:
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

The recommended approach is to define connections in the bundle manifest under `bootstrap.connections`:

```yaml
stages:
  test:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: test-data-platform
      create: true
    bootstrap:
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

The CLI is used differently depending on your deployment approach:

### Direct Git-Based Deployment
```bash
# Deploy directly from git to test
smus-cli deploy --stages test --manifest manifest.yaml

# Deploy to production
smus-cli deploy --stages prod --manifest manifest.yaml
```

### Bundle-Based Deployment
```bash
# Create bundle (typically from dev)
smus-cli bundle --manifest manifest.yaml --stages dev

# Deploy bundle to test
smus-cli deploy --stages test --manifest manifest.yaml --manifest path/to/bundle.tar.gz

# Deploy same bundle to production
smus-cli deploy --stages prod --manifest manifest.yaml --manifest path/to/bundle.tar.gz
```

### Hybrid Deployment
```bash
# Create bundle once (contains some content like data files, configs)
smus-cli bundle --manifest manifest.yaml --stages dev

# Deploy to test: pulls workflows from release_test branch + data from bundle
smus-cli deploy --stages test --manifest manifest.yaml --manifest path/to/bundle.tar.gz

# Deploy to prod: pulls workflows from release_prod branch + data from bundle
smus-cli deploy --stages prod --manifest manifest.yaml --manifest path/to/bundle.tar.gz
```

### Validation Commands (All Approaches)
```bash
# Validate deployment
smus-cli test --stages test --manifest manifest.yaml

# Check logs
smus-cli logs --stages test --workflow my_workflow --live

# Monitor health
smus-cli monitor --stages test --manifest manifest.yaml
```

**Key insight:** 
- Direct git-based: Fast iteration, everything from git branches
- Bundle-based: Versioned artifacts, everything from bundle
- Hybrid: Bundle for static content (data, configs), git branches for workflows

---

## Step 7: Choose Your Project Organization Model

Organizations can choose between shared or isolated project models using the `create` flag.

### Shared Projects Model (create: false)

Multiple applications deploy to the same test/prod projects. Best for teams that collaborate and share resources.

```
my-organization/
├── monthly-metrics/           # Data application 1
│   ├── manifest.yaml          # Points to shared-data-platform-test/prod
│   ├── workflows/
│   │   ├── metrics_etl.yaml
│   │   └── metrics_report.yaml
│   └── notebooks/
│       └── metrics_analysis.ipynb
│
├── churn-model/               # Data application 2
│   ├── manifest.yaml          # Points to shared-data-platform-test/prod
│   ├── workflows/
│   │   ├── feature_engineering.yaml
│   │   └── model_training.yaml
│   └── notebooks/
│       └── train_model.ipynb
│
└── README.md
```

**Deployment:**
```bash
# Both applications deploy to the same shared projects
cd monthly-metrics
smus-cli deploy --stages test --manifest manifest.yaml  # → shared-data-platform-test

cd ../churn-model
smus-cli deploy --stages test --manifest manifest.yaml  # → shared-data-platform-test
```

All workflows from both applications appear in the same MWAA environment.

**Benefits:**
- Shared resources and connections
- Centralized governance
- Lower infrastructure costs
- Easier cross-application workflows

### Isolated Projects Model (create: true)

Each application gets its own dedicated projects. Best for team autonomy and cost isolation.

```
my-organization/
├── monthly-metrics/           # Data application 1
│   ├── manifest.yaml          # Creates monthly-metrics-test/prod
│   └── workflows/
│
├── churn-model/               # Data application 2
│   ├── manifest.yaml          # Creates churn-model-test/prod
│   └── workflows/
│
└── README.md
```

**Deployment:**
```bash
# Each application creates and deploys to its own projects
cd monthly-metrics
smus-cli deploy --stages test --manifest manifest.yaml  # → monthly-metrics-test (created)

cd ../churn-model
smus-cli deploy --stages test --manifest manifest.yaml  # → churn-model-test (created)
```

Each application has its own isolated MWAA environment and resources.

**Benefits:**
- Team autonomy and ownership
- Different profiles/permissions per application
- Cost tracking per application
- No naming conflicts between applications

### Hybrid Model

You can also mix both approaches - shared test, isolated prod:

```yaml
# manifest.yaml
stages:
  test:
    project:
      name: shared-test-platform
      create: false  # Shared test environment
  
  prod:
    project:
      name: my-app-prod
      create: true   # Isolated production
    bootstrap:
      project:
        create: true
        profileName: 'All capabilities'
        owners: [my-team@example.com]
```

---

## Step 8: Set Up CI/CD Authentication (Optional)

If you want to automate deployments via CI/CD, configure authentication between your CI/CD platform and AWS.

### Quick Setup for GitHub Actions

```bash
# Deploy OIDC integration using CloudFormation
aws cloudformation deploy \
  --template-file tests/scripts/setup/1-account-setup/github-oidc-role.yaml \
  --stack-name smus-cli-github-integration \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    GitHubOrg=your-org \
    GitHubRepo=your-repo \
    GitHubEnvironment=aws-env
```

**Get the role ARN:**
```bash
aws cloudformation describe-stacks \
  --stack-name smus-cli-github-integration \
  --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
  --output text
```

### Other CI/CD Platforms

- **GitLab CI:** [GitLab AWS OIDC](https://docs.gitlab.com/ee/ci/cloud_services/aws/)
- **Azure DevOps:** [Azure AWS Connection](https://learn.microsoft.com/en-us/azure/devops/pipelines/library/connect-to-azure)
- **Jenkins:** Use AWS credentials plugin

### Required Permissions

> **⚠️ TODO:** Document minimum required IAM permissions.
> 
> **Current reference:** See `tests/scripts/setup/1-account-setup/github-oidc-role.yaml`

**For detailed CI/CD setup:**
- [GitHub Actions Workflows](../../git-templates/) - Pre-built templates
- [Application Guide](../github-workflow-application-guide.md) - For data teams
- [DevOps Guide](../github-workflow-devops-guide.md) - For platform teams

---

## Step 9: Set Up CI/CD Workflows (Optional)

Automate deployments using your CI/CD platform. The SMUS CLI commands are the same across all platforms.

### GitHub Actions - Direct Git-Based Deployment

```yaml
name: Deploy Data Application (Direct)

on:
  push:
    branches: [main, release_test, release_prod]

jobs:
  deploy:
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
      
      - name: Deploy to Test
        if: github.ref == 'refs/heads/release_test'
        run: smus-cli deploy --stages test --manifest manifest.yaml
      
      - name: Deploy to Production
        if: github.ref == 'refs/heads/release_prod'
        run: smus-cli deploy --stages prod --manifest manifest.yaml
      
      - name: Validate Deployment
        run: smus-cli test --stages test --manifest manifest.yaml
```

### GitHub Actions - Bundle-Based Deployment

```yaml
name: Deploy Data Application (Bundle)

on:
  push:
    branches: [main]

jobs:
  deploy-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
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
        run: smus-cli bundle --manifest manifest.yaml --stages dev
      
      - name: Upload Bundle
        uses: actions/upload-artifact@v3
        with:
          name: application-bundle
          path: "*.tar.gz"
      
      - name: Deploy to Test
        run: smus-cli deploy --stages test --manifest manifest.yaml --manifest *.tar.gz
      
      - name: Validate Deployment
        run: smus-cli test --stages test --manifest manifest.yaml

  deploy-prod:
    needs: deploy-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v3
      
      - name: Download Bundle
        uses: actions/download-artifact@v3
        with:
          name: application-bundle
      
      - name: Deploy to Production
        run: smus-cli deploy --stages prod --manifest manifest.yaml --manifest *.tar.gz
      
      - name: Monitor Production
        run: smus-cli monitor --stages prod --manifest manifest.yaml
```

**For complete CI/CD setup:**
- **GitHub Actions:** See [git-templates/](../../git-templates/) for pre-built workflows
  - `direct-branch/` - Direct git-based deployment
  - `bundle-based/` - Bundle-based deployment
  - `hybrid-bundle-branch/` - Hybrid approach
- **Other platforms:** Adapt the CLI commands to your platform's syntax

**Key insight:** CI/CD just automates the CLI commands you'd run manually.

**See more:** [GitHub Actions Integration Guide](../github-actions-integration.md)

---

## Step 10: Validate Deployment with Monitoring

After deployment, use these commands to verify everything works:

### Check Deployment Status
```bash
# View overall bundle health
smus-cli monitor --stages test --manifest manifest.yaml
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
smus-cli logs --stages test --workflow metrics_etl --live

# Historical logs
smus-cli logs --stages test --workflow metrics_etl --date 2025-01-13
```

### Run Tests
```bash
# Execute validation tests
smus-cli test --stages test --manifest manifest.yaml
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

## Step 11: Set Up Monitoring and Metrics Integration

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

## Step 12: Document for Data Teams

Create team documentation explaining the setup:

**`docs/deployment-guide.md`:**
```markdown
# Data Application Deployment Guide

## Overview
Our SMUS projects are configured as deployment stages:
- **test-data-platform** - Testing and validation
- **prod-data-platform** - Production deployment

Multiple data applications can deploy to the same project.

## Deployment Process
1. Develop in your dev project
2. Create bundle: `smus-cli bundle --manifest manifest.yaml --stages dev`
3. Push to GitHub → Automatic deployment to test
4. After validation → Automatic deployment to prod

## Monitoring Your Deployment
- Check status: `smus-cli monitor --stages test --manifest manifest.yaml`
- View logs: `smus-cli logs --stages test --workflow YOUR_WORKFLOW --live`
- Run tests: `smus-cli test --stages test --manifest manifest.yaml`

## Support
- Slack: #data-platform-support
- Email: platform-team@example.com
```

---

## Next Steps

### For Data Teams
- **[Data Team Quick Start](quickstart.md)** - Guide for building and deploying applications

### Advanced Configuration
- **[Bundle Manifest Reference](../bundle-manifest.md)** - Complete YAML specification
- **[CLI Commands Reference](../cli-commands.md)** - All available commands
- **[Monitoring and Metrics](../monitoring-and-metrics.md)** - Detailed monitoring setup

### Examples
- See [examples directory](../../examples/) for complete working examples

---

## Key Takeaways

1. **Projects are deployment stages** - One SMUS project can host multiple data applications
2. **Three deployment approaches** - Direct git-based, bundle-based, or hybrid
3. **Initialization is automatic** - CLI creates projects with proper settings on first deployment
4. **Monitoring is essential** - Use `monitor`, `logs`, and `test` commands to validate deployments
5. **CI/CD automates flow** - GitHub Actions handles test → prod progression

**Questions?** Contact the platform team for support.
