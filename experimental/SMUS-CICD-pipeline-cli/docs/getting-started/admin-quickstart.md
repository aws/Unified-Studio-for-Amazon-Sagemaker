# Admin Quick Start

**Goal:** Set up complete multi-environment CI/CD infrastructure in 15-20 minutes

**Audience:** Platform administrators configuring SageMaker Unified Studio for data science teams

---

## Prerequisites

- ✅ AWS account with admin access
- ✅ SageMaker Unified Studio domain created
- ✅ Understanding of AWS IAM, S3, and MWAA
- ✅ Python 3.8+ and AWS CLI installed
- ✅ Terraform or CloudFormation knowledge (optional)

---

## Overview

You'll set up a complete 3-environment pipeline:
- **Dev** - Development and experimentation
- **Test** - Integration testing and validation  
- **Prod** - Production deployment

Each environment gets its own:
- SageMaker Unified Studio project
- S3 bucket for storage
- MWAA environment for workflows
- Athena workgroup for analytics
- Glue database for catalog

---

## Step 1: Install the CLI

```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

---

## Step 2: Create OIDC Role for GitHub Actions

If using GitHub Actions for CI/CD, create an OIDC role for secure authentication:

```bash
# 1. Create OIDC identity provider (one-time setup)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# 2. Create trust policy for GitHub Actions
cat > github-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR-ORG/YOUR-REPO:*"
        }
      }
    }
  ]
}
EOF

# 3. Create IAM role
aws iam create-role \
  --role-name GitHubActionsRole-SMUS-Pipeline \
  --assume-role-policy-document file://github-trust-policy.json

# 4. Attach required permissions
aws iam attach-role-policy \
  --role-name GitHubActionsRole-SMUS-Pipeline \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
```

**Note:** Replace `111122223333` with your AWS account ID and `YOUR-ORG/YOUR-REPO` with your GitHub repository.

---

## Step 3: Create Dev Project in Console

1. Navigate to SageMaker Unified Studio console
2. Select your domain
3. Create the dev project:
   - Name: `dev-data-platform`
   - Profile: `All capabilities`
   - Add yourself as owner
4. Add the OIDC role to the project:
   - Go to **Settings** → **Members**
   - Click **Add member** → **IAM role**
   - Enter: `arn:aws:iam::111122223333:role/GitHubActionsRole-SMUS-Pipeline`
   - Assign role: **Project owner**

---

## Step 4: Create Master Pipeline Configuration

Create `infrastructure/pipeline.yaml`:

```yaml
pipelineName: DataPlatformPipeline

targets:
  dev:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: dev-data-platform
      create: false  # Already created in console
    
  test:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: test-data-platform
      create: true  # CLI will create this
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: [arn:aws:iam::111122223333:role/GitHubActionsRole-SMUS-Pipeline]
      environments: 
        - EnvironmentConfigurationName: 'OnDemand Workflows'
    
  prod:
    domain:
      name: my-domain
      region: us-east-1
    project:
      name: prod-data-platform
      create: true  # CLI will create this
    initialization:
      project:
        create: true
        profileName: 'All capabilities'
        owners: [arn:aws:iam::111122223333:role/GitHubActionsRole-SMUS-Pipeline]
      environments: 
        - EnvironmentConfigurationName: 'OnDemand Workflows'

bundle:
  storage:
    - name: workflows
      connectionName: default.s3_shared
      include:
        - 'workflows/'
```

**Note:** The CLI will automatically create test and prod projects with the OIDC role as owner when you first deploy.

---

## Step 5: Validate Infrastructure

```bash
smus-cli describe --pipeline infrastructure/pipeline.yaml --connect
```

**Expected output:**
```
Pipeline: DataPlatformPipeline

Targets: 3
  ✓ dev (dev-data-platform)
  ✓ test (test-data-platform)  
  ✓ prod (prod-data-platform)

Connections per target:
  Dev:
    ✓ default.s3_shared
    ✓ project.workflow_mwaa
    ✓ project.athena
    ✓ project.default_lakehouse
  
  Test:
    ✓ default.s3_shared
    ✓ project.workflow_mwaa
    ✓ project.athena
    ✓ project.default_lakehouse
  
  Prod:
    ✓ default.s3_shared
    ✓ project.workflow_mwaa
    ✓ project.athena
    ✓ project.default_lakehouse

✅ All infrastructure validated
```

---

## Supported Services & Capabilities

The SMUS CI/CD CLI enables deployment of workflows using these AWS services:

### 🎯 Analytics & Data Processing (Primary Focus)
- **Amazon Athena** - Interactive SQL queries on S3 data lakes
- **AWS Glue** - Serverless ETL and data catalog management
- **Amazon EMR** - Managed Hadoop and Spark clusters
- **Amazon Redshift** - Cloud data warehouse operations
- **AWS Lake Formation** - Data lake security and governance

### 🤖 Machine Learning (Primary Focus)
- **Amazon SageMaker Training** - Distributed ML model training
- **SageMaker Pipelines** - End-to-end ML workflow orchestration
- **SageMaker Feature Store** - Centralized feature repository
- **SageMaker Model Registry** - Model versioning and deployment
- **SageMaker Batch Transform** - Large-scale batch inference
- **SageMaker Endpoints** - Real-time model serving

### 🧠 Generative AI (Primary Focus)
- **Amazon Bedrock** - Foundation model inference (Claude, Titan, etc.)
- **Bedrock Agents** - Autonomous AI agent orchestration
- **Bedrock Knowledge Bases** - RAG (Retrieval Augmented Generation)
- **Bedrock Guardrails** - Content filtering and safety controls

### 📊 Additional Supported Services
- **Amazon S3** - Object storage operations
- **AWS Lambda** - Serverless function execution
- **AWS Step Functions** - Workflow orchestration
- **Amazon DynamoDB** - NoSQL database operations
- **Amazon RDS** - Relational database management
- **Amazon SNS/SQS** - Messaging and notifications
- **AWS Batch** - Batch computing jobs

**Complete operator list:** See [Airflow AWS Operators Reference](../airflow-aws-operators.md)

---

---

## Step 6: Set Up GitHub Actions for Teams

Create organization-level GitHub Actions workflow template:

**`.github/workflows/deploy-template.yml`:**
```yaml
name: Deploy to SMUS

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  AWS_REGION: us-east-1
  PIPELINE_FILE: pipeline.yaml

jobs:
  validate:
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
      
      - name: Configure AWS
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Validate Pipeline
        run: smus-cli describe --pipeline ${{ env.PIPELINE_FILE }} --connect

  deploy-dev:
    needs: validate
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Dev
        run: |
          smus-cli bundle --pipeline ${{ env.PIPELINE_FILE }} --targets dev
          smus-cli deploy --targets dev --pipeline ${{ env.PIPELINE_FILE }}

  deploy-test:
    needs: validate
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Test
        run: |
          smus-cli bundle --pipeline ${{ env.PIPELINE_FILE }} --targets dev
          smus-cli deploy --targets test --pipeline ${{ env.PIPELINE_FILE }}
      
      - name: Run Tests
        run: smus-cli test --targets test --pipeline ${{ env.PIPELINE_FILE }}

  deploy-prod:
    needs: deploy-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Production
        run: smus-cli deploy --targets prod --pipeline ${{ env.PIPELINE_FILE }}
```

---

## Step 7: Document for Teams

Create team documentation:

**`docs/team-guide.md`:**
```markdown
# Data Platform CI/CD Guide

## Quick Start
1. Clone this repository
2. Create your pipeline.yaml
3. Push to develop branch → deploys to dev
4. Push to main branch → deploys to test → prod

## Environments
- Dev: Automatic deployment on develop branch
- Test: Automatic deployment on main branch (requires tests to pass)
- Prod: Automatic deployment after test (requires manual approval)

## Getting Help
- Slack: #data-platform-support
- Email: data-platform-team@example.com
- Docs: https://wiki.example.com/data-platform
```

---

## Step 8: Test End-to-End

Deploy a test workflow to verify everything works:

```bash
# Create test workflow
mkdir -p workflows
cat > workflows/test_dag.yaml << 'EOF'
test_workflow:
  dag_id: "test_dag"
  default_args:
    owner: "admin"
  tasks:
    hello_task:
      operator: "airflow.operators.bash.BashOperator"
      bash_command: "echo 'Hello from SMUS CI/CD!'"
EOF

# Deploy to all environments
smus-cli bundle --pipeline infrastructure/pipeline.yaml --targets dev
smus-cli deploy --targets dev --pipeline infrastructure/pipeline.yaml
smus-cli deploy --targets test --pipeline infrastructure/pipeline.yaml
smus-cli deploy --targets prod --pipeline infrastructure/pipeline.yaml

# Verify deployment
smus-cli monitor --pipeline infrastructure/pipeline.yaml
```

---

## Maintenance Tasks

### Regular Health Checks
```bash
# Check all environments
smus-cli monitor --pipeline infrastructure/pipeline.yaml --targets dev,test,prod

# View deployment history
smus-cli describe --pipeline infrastructure/pipeline.yaml --history
```

### Update Infrastructure
```bash
# Redeploy with updated configuration
smus-cli deploy --targets test --pipeline infrastructure/pipeline.yaml
```

### Manage Catalog Subscriptions
```bash
# List pending subscriptions
smus-cli monitor --targets test --catalog-subscriptions

# Approve subscription
aws datazone approve-subscription --subscription-id sub_abc123
```

---

---

## Next Steps

### For Your Team
- **[Quick Start Guide](quickstart.md)** - Guide for DevOps teams

### Advanced Configuration
- **[Pipeline Manifest Reference](../pipeline-manifest.md)** - Complete YAML guide
- **[GitHub Actions Integration](../github-actions-integration.md)** - CI/CD automation

### Examples
- See [examples directory](../../examples/) for complete working examples

---

**Questions?** Contact the platform team for support.
