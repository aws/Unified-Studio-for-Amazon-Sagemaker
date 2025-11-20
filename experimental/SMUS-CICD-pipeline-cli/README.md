[![en](https://img.shields.io/badge/lang-en-brightgreen.svg?style=for-the-badge)](README.md)
[![pt](https://img.shields.io/badge/lang-pt-gray.svg)](docs/langs/pt/README.md)
[![fr](https://img.shields.io/badge/lang-fr-gray.svg)](docs/langs/fr/README.md)
[![it](https://img.shields.io/badge/lang-it-gray.svg)](docs/langs/it/README.md)
[![ja](https://img.shields.io/badge/lang-ja-gray.svg)](docs/langs/ja/README.md)
[![zh](https://img.shields.io/badge/lang-zh-gray.svg)](docs/langs/zh/README.md)
[![he](https://img.shields.io/badge/lang-he-gray.svg)](docs/langs/he/README.md)

# SMUS CI/CD Pipeline CLI

**Automate deployment of data applications across SageMaker Unified Studio environments**

Deploy Airflow DAGs, Jupyter notebooks, and ML workflows from development to production with confidence. Built for data scientists, data engineers, ML engineers, and GenAI app developers working with DevOps teams.

**Works with your deployment strategy:** Whether you use git branches (branch-based), versioned artifacts (bundle-based), git tags (tag-based), or direct deployment - this CLI supports your workflow. Define your application once, deploy it your way.

---

## Why SMUS CI/CD CLI?

✅ **AWS Abstraction Layer** - CLI encapsulates all AWS analytics, ML, and SMUS complexity - DevOps teams never call AWS APIs directly  
✅ **Separation of Concerns** - Data teams define WHAT to deploy (manifest.yaml), DevOps teams define HOW and WHEN (CI/CD workflows)  
✅ **Generic CI/CD Workflows** - Same workflow works for Glue, SageMaker, Bedrock, QuickSight, or any AWS service combination  
✅ **Deploy with Confidence** - Automated testing and validation before production  
✅ **Multi-Environment Management** - Test → Prod with environment-specific configuration  
✅ **Infrastructure as Code** - Version-controlled application manifests and reproducible deployments  
✅ **Event-Driven Workflows** - Trigger workflows automatically via EventBridge on deployment  

---

## Quick Start

**Install from source:**
```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

**Deploy your first application:**
```bash
# Validate configuration
smus-cli describe --manifest manifest.yaml --connect

# Create deployment bundle (optional)
smus-cli bundle --manifest manifest.yaml

# Deploy to test environment
smus-cli deploy --targets test --manifest manifest.yaml

# Run validation tests
smus-cli test --manifest manifest.yaml --targets test
```

**See it in action:** [Live GitHub Actions Example](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## Who Is This For?

### 👨‍💻 Data Teams (Data Scientists, Data Engineers, GenAI App Developers)
**You focus on:** Your application - what to deploy, where to deploy, and how it runs  
**You define:** Application manifest (`manifest.yaml`) with your code, workflows, and configurations  
**You don't need to know:** CI/CD pipelines, GitHub Actions, deployment automation  

→ **[Quick Start Guide](docs/getting-started/quickstart.md)** - Deploy your first application in 10 minutes  

**Includes examples for:**
- Data Engineering (Glue, Notebooks, Athena)
- ML Workflows (SageMaker, Notebooks)
- GenAI Applications (Bedrock, Notebooks)

### 🔧 DevOps Teams
**You focus on:** CI/CD best practices, security, compliance, and deployment automation  
**You define:** Workflow templates that enforce testing, approvals, and promotion policies  
**You don't need to know:** Application-specific details, AWS services used, DataZone APIs, SMUS project structures, or business logic  

→ **[Admin Guide](docs/getting-started/admin-quickstart.md)** - Configure infrastructure and pipelines in 15 minutes  
→ **[GitHub Workflow Templates](git-templates/)** - Generic, reusable workflow templates for automated deployment

**The CLI is your abstraction layer:** You just call `smus-cli deploy` - the CLI handles all AWS service interactions (DataZone, Glue, Athena, SageMaker, MWAA, S3, IAM, etc.). Your workflows stay simple and generic.

---

## Key Features

### 🚀 Automated Deployment
- **Application Manifest** - Define your application content, workflows, and deployment targets in YAML
- **Flexible Deployment** - Bundle-based (artifact) or direct (git-based) deployment modes
- **Multi-Target Deployment** - Deploy to test and prod with a single command
- **Environment Variables** - Dynamic configuration using `${VAR}` substitution
- **Version Control** - Track deployments in S3 or git for deployment history

### 🔍 Testing & Validation
- **Automated Tests** - Run validation tests before promoting to production
- **Quality Gates** - Block deployments if tests fail
- **Workflow Monitoring** - Track execution status and logs
- **Health Checks** - Verify deployment correctness

### 🔄 CI/CD Pipeline Integration
- **GitHub Actions** - Pre-built CI/CD pipeline workflows for automated deployment
- **GitLab CI** - Native support for GitLab CI/CD pipelines
- **Environment Variables** - Flexible configuration for any CI/CD platform
- **Webhook Support** - Trigger deployments from external events

### 🏗️ Infrastructure Management
- **Project Creation** - Automatically provision SageMaker Unified Studio projects
- **Connection Setup** - Configure S3, Airflow, Athena, and Lakehouse connections
- **Resource Mapping** - Link AWS resources to project connections
- **Permission Management** - Control access and collaboration

### ⚡ Bootstrap Actions
- **Automated Workflow Execution** - Trigger workflows automatically during deployment with `workflow.run` (use `trailLogs: true` to stream logs and wait for completion)
- **Log Retrieval** - Fetch workflow logs for validation and debugging with `workflow.logs`
- **QuickSight Dataset Refresh** - Automatically refresh dashboards after ETL deployment with `quicksight.refresh_dataset`
- **EventBridge Integration** - Emit custom events for downstream automation and CI/CD orchestration with `eventbridge.put_events`
- **DataZone Connections** - Provision MLflow and other service connections during deployment
- **Sequential Execution** - Actions run in order during `smus-cli deploy` for reliable initialization and validation

### 📊 Catalog Integration
- **Asset Discovery** - Automatically find required catalog assets (Glue, Lake Formation, DataZone)
- **Subscription Management** - Request access to tables and datasets
- **Approval Workflows** - Handle cross-project data access
- **Asset Tracking** - Monitor catalog dependencies

---

## What Can You Deploy?

**📊 Analytics & BI**
- Glue ETL jobs and crawlers
- Athena queries
- QuickSight dashboards
- EMR jobs (future)
- Redshift queries (future)

**🤖 Machine Learning**
- SageMaker training jobs
- ML models and endpoints
- MLflow experiments
- Feature Store (future)
- Batch transforms (future)

**🧠 Generative AI**
- Bedrock agents
- Knowledge bases
- Foundation model configurations (future)

**📓 Code & Workflows**
- Jupyter notebooks
- Python scripts
- Airflow DAGs (MWAA and Amazon MWAA Serverless)
- Lambda functions (future)

**💾 Data & Storage**
- S3 data files
- Git repositories
- Data catalogs (future)

---

## Supported AWS Services

Deploy workflows using these AWS services through Airflow YAML syntax:

### 🎯 Analytics & Data
**Amazon Athena** • **AWS Glue** • **Amazon EMR** • **Amazon Redshift** • **Amazon QuickSight** • **Lake Formation**

### 🤖 Machine Learning  
**SageMaker Training** • **SageMaker Pipelines** • **Feature Store** • **Model Registry** • **Batch Transform**

### 🧠 Generative AI
**Amazon Bedrock** • **Bedrock Agents** • **Bedrock Knowledge Bases** • **Guardrails**

### 📊 Additional Services
S3 • Lambda • Step Functions • DynamoDB • RDS • SNS/SQS • Batch

**See complete list:** [Airflow AWS Operators Reference](docs/airflow-aws-operators.md)

---

## Core Concepts

### Separation of Concerns: The Key Design Principle

**The Problem:** Traditional deployment approaches force DevOps teams to learn AWS analytics services (Glue, Athena, DataZone, SageMaker, MWAA, etc.) and understand SMUS project structures, or force data teams to become CI/CD experts.

**The Solution:** SMUS CLI is the abstraction layer that encapsulates all AWS and SMUS complexity:

```
Data Teams                    SMUS CLI                         DevOps Teams
    ↓                            ↓                                  ↓
manifest.yaml          smus-cli deploy                    GitHub Actions
(WHAT & WHERE)         (AWS ABSTRACTION)                  (HOW & WHEN)
```

**Data teams focus on:**
- Application code and workflows
- Which AWS services to use (Glue, Athena, SageMaker, etc.)
- Environment configurations
- Business logic

**SMUS CLI handles ALL AWS complexity:**
- DataZone domain and project management
- AWS Glue, Athena, SageMaker, MWAA APIs
- S3 storage and artifact management
- IAM roles and permissions
- Connection configurations
- Catalog asset subscriptions
- Workflow deployment to Airflow
- Infrastructure provisioning
- Testing and validation

**DevOps teams focus on:**
- CI/CD best practices (testing, approvals, notifications)
- Security and compliance gates
- Deployment orchestration
- Monitoring and alerting

**Result:** 
- Data teams never touch CI/CD configs
- **DevOps teams never call AWS APIs directly** - they just call `smus-cli deploy`
- **CI/CD workflows are generic** - same workflow works for Glue apps, SageMaker apps, or Bedrock apps
- Both teams work independently using their expertise

---

### Application Manifest
A declarative YAML file (`manifest.yaml`) that defines your data application:
- **Application details** - Name, version, description
- **Content** - Code from git repositories, data/models from storage, QuickSight dashboards
- **Workflows** - Airflow DAGs for orchestration and automation
- **Stages** - Where to deploy (dev, test, prod environments)
- **Configuration** - Environment-specific settings, connections, and bootstrap actions

**Created and owned by data teams.** Defines **what** to deploy and **where**. No CI/CD knowledge required.

### Application
Your data/analytics workload being deployed:
- Airflow DAGs and Python scripts
- Jupyter notebooks and data files
- ML models and training code
- ETL pipelines and transformations
- GenAI agents and MCP servers
- Foundation model configurations

### Stage
A deployment environment (dev, test, prod) mapped to a SageMaker Unified Studio project:
- Domain and region configuration
- Project name and settings
- Resource connections (S3, Airflow, Athena, Glue)
- Environment-specific parameters
- Optional branch mapping for git-based deployments

### Workflow
Orchestration logic that executes your application. Workflows serve two purposes:

**1. Deployment-time:** Create required AWS resources during deployment
- Provision infrastructure (S3 buckets, databases, IAM roles)
- Configure connections and permissions
- Set up monitoring and logging

**2. Runtime:** Execute ongoing data and ML pipelines
- Scheduled execution (daily, hourly, etc.)
- Event-driven triggers (S3 uploads, API calls)
- Data processing and transformations
- Model training and inference

Workflows are defined as Airflow DAGs (Directed Acyclic Graphs) in YAML format. Supports [MWAA (Managed Workflows for Apache Airflow)](https://aws.amazon.com/managed-workflows-for-apache-airflow/) and [Amazon MWAA Serverless](https://aws.amazon.com/blogs/big-data/introducing-amazon-mwaa-serverless/) ([User Guide](https://docs.aws.amazon.com/mwaa/latest/mwaa-serverless-userguide/what-is-mwaa-serverless.html)).

### CI/CD Automation
GitHub Actions workflows (or other CI/CD systems) that automate deployment:
- **Created and owned by DevOps teams**
- Defines **how** and **when** to deploy
- Runs tests and quality gates
- Manages promotion across targets
- Enforces security and compliance policies
- Example: `.github/workflows/deploy.yml`

**Key insight:** DevOps teams create generic, reusable workflows that work for ANY application. They don't need to know if the app uses Glue, SageMaker, or Bedrock - the CLI handles all AWS service interactions. The workflow just calls `smus-cli deploy` and the CLI does the rest.

### Deployment Modes

**Bundle-based (Artifact):** Create versioned archive → deploy archive to stages
- Good for: audit trails, rollback capability, compliance
- Command: `smus-cli bundle` then `smus-cli deploy --manifest app.tar.gz`

**Direct (Git-based):** Deploy directly from sources without intermediate artifacts
- Good for: simpler workflows, rapid iteration, git as source of truth
- Command: `smus-cli deploy --manifest manifest.yaml --stage test`

Both modes work with any combination of storage and git content sources.

---

### How It All Works Together

```
1. Data Team                    2. DevOps Team                 3. SMUS CLI (The Abstraction)
   ↓                               ↓                              ↓
Creates manifest.yaml          Creates generic workflow       Workflow calls:
- Glue jobs                    - Test on merge                smus-cli deploy --manifest manifest.yaml
- SageMaker training           - Approval for prod              ↓
- Athena queries               - Security scans               CLI handles ALL AWS complexity:
- S3 locations                 - Notification rules           - DataZone APIs
                                                              - Glue/Athena/SageMaker APIs
                               Works for ANY app!             - MWAA deployment
                               No AWS knowledge needed!       - S3 management
                                                              - IAM configuration
                                                              - Infrastructure provisioning
                                                                ↓
                                                              Success!
```

**The beauty:** 
- Data teams never learn GitHub Actions
- **DevOps teams never call AWS APIs** - the CLI encapsulates all AWS analytics, ML, and SMUS complexity
- CI/CD workflows are simple: just call `smus-cli deploy`
- Same workflow works for ANY application, regardless of AWS services used

---

## Example Applications

Real-world examples showing how to deploy different workloads with SMUS CI/CD.

### 📊 Analytics - QuickSight Dashboard
Deploy interactive BI dashboards with automated Glue ETL pipelines for data preparation. Uses QuickSight asset bundles, Athena queries, and GitHub dataset integration with environment-specific configurations.

**AWS Services:** QuickSight • Glue • Athena • S3 • MWAA Serverless

**What happens during deployment:** Application code is deployed to S3, Glue jobs and Airflow workflows are created and executed, QuickSight dashboard/data source/dataset are created, and QuickSight ingestion is initiated to refresh the dashboard with latest data.

<details>
<summary><b>View Manifest</b></summary>

```yaml
applicationName: IntegrationTestETLWorkflow

content:
  storage:
    - name: dashboard-glue-quick
      connectionName: default.s3_shared
      include: [dashboard-glue-quick]
  
  git:
    - repository: covid-19-dataset
      url: https://github.com/datasets/covid-19.git
  
  quicksight:
    - dashboardId: sample-dashboard
      assetBundle: quicksight/sample-dashboard.qs
      owners:
        - arn:aws:quicksight:${DEV_DOMAIN_REGION:us-east-2}:*:user/default/Admin/*
  
  workflows:
    - workflowName: covid_dashboard_glue_quick_pipeline
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-2
    project:
      name: test-marketing
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
    environment_variables:
      S3_PREFIX: test
      GRANT_TO: Admin,service-role/aws-quicksight-service-role-v0
    bootstrap:
      actions:
        - type: workflow.logs
          workflowName: covid_dashboard_glue_quick_pipeline
          live: true
          lines: 10000
        - type: quicksight.refresh_dataset
          refreshScope: IMPORTED
          ingestionType: FULL_REFRESH
          wait: false
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: deployed-{stage.name}-covid-
```

</details>

**[View Full Example →](docs/examples-guide.md#-analytics---quicksight-dashboard)**

---

### 📓 Data Engineering - Notebooks
Deploy Jupyter notebooks with parallel execution orchestration for data analysis and ETL workflows. Demonstrates notebook deployment with MLflow integration for experiment tracking.

**AWS Services:** SageMaker Notebooks • MLflow • S3 • MWAA Serverless

**What happens during deployment:** Notebooks and workflow definitions are uploaded to S3, Airflow DAG is created for parallel notebook execution, MLflow connection is provisioned for experiment tracking, and notebooks are ready to run on-demand or scheduled.

<details>
<summary><b>View Manifest</b></summary>

```yaml
applicationName: IntegrationTestNotebooks

content:
  storage:
    - name: notebooks
      connectionName: default.s3_shared
      include:
        - notebooks/
        - workflows/
      exclude:
        - .ipynb_checkpoints/
        - __pycache__/
  
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
    bootstrap:
      actions:
        - type: datazone.create_connection
          name: mlflow-server
          connection_type: MLFLOW
          properties:
            trackingServerArn: arn:aws:sagemaker:${STS_REGION}:${STS_ACCOUNT_ID}:mlflow-tracking-server/smus-integration-mlflow-use2
            trackingServerName: smus-integration-mlflow-use2
```

</details>

**[View Full Example →](docs/examples-guide.md#-data-engineering---notebooks)**

---

### 🤖 Machine Learning - Training
Train ML models with SageMaker using the [SageMaker SDK](https://sagemaker.readthedocs.io/) and [SageMaker Distribution](https://github.com/aws/sagemaker-distribution/tree/main/src) images. Track experiments with MLflow and automate training pipelines with environment-specific configurations.

**AWS Services:** SageMaker Training • MLflow • S3 • MWAA Serverless

**What happens during deployment:** Training code and workflow definitions are uploaded to S3 with compression, Airflow DAG is created for training orchestration, MLflow connection is provisioned for experiment tracking, and SageMaker training jobs are created and executed using SageMaker Distribution images.

<details>
<summary><b>View Manifest</b></summary>

```yaml
applicationName: IntegrationTestMLTraining

content:
  storage:
    - name: training-code
      connectionName: default.s3_shared
      include: [ml/training/code]
    
    - name: training-workflows
      connectionName: default.s3_shared
      include: [ml/training/workflows]
  
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
```

</details>

**[View Full Example →](docs/examples-guide.md#-machine-learning---training)**

---

### 🤖 Machine Learning - Deployment
Deploy trained ML models as SageMaker real-time inference endpoints. Uses SageMaker SDK for endpoint configuration and [SageMaker Distribution](https://github.com/aws/sagemaker-distribution/tree/main/src) images for serving.

**AWS Services:** SageMaker Endpoints • S3 • MWAA Serverless

**What happens during deployment:** Model artifacts, deployment code, and workflow definitions are uploaded to S3, Airflow DAG is created for endpoint deployment orchestration, SageMaker endpoint configuration and model are created, and the inference endpoint is deployed and ready to serve predictions.

<details>
<summary><b>View Manifest</b></summary>

```yaml
applicationName: IntegrationTestMLDeployment

content:
  storage:
    - name: deployment-code
      connectionName: default.s3_shared
      include: [ml/deployment/code]
    
    - name: deployment-workflows
      connectionName: default.s3_shared
      include: [ml/deployment/workflows]
    
    - name: model-artifacts
      connectionName: default.s3_shared
      include: [ml/output/model-artifacts/latest]
  
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
```

</details>

**[View Full Example →](docs/examples-guide.md#-machine-learning---deployment)**

---

### 🧠 Generative AI
Deploy GenAI applications with Bedrock agents and knowledge bases. Demonstrates RAG (Retrieval Augmented Generation) workflows with automated agent deployment and testing.

**AWS Services:** Amazon Bedrock • S3 • MWAA Serverless

**What happens during deployment:** Agent configuration and workflow definitions are uploaded to S3, Airflow DAG is created for agent deployment orchestration, Bedrock agents and knowledge bases are configured, and the GenAI application is ready for inference and testing.

<details>
<summary><b>View Manifest</b></summary>

```yaml
applicationName: IntegrationTestGenAIWorkflow

content:
  storage:
    - name: agent-code
      connectionName: default.s3_shared
      include: [genai/job-code]
    
    - name: genai-workflows
      connectionName: default.s3_shared
      include: [genai/workflows]
  
  workflows:
    - workflowName: genai_dev_workflow
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
        - name: agent-code
          connectionName: default.s3_shared
          targetDirectory: genai/bundle/agent-code
        - name: genai-workflows
          connectionName: default.s3_shared
          targetDirectory: genai/bundle/workflows
```

</details>

**[View Full Example →](docs/examples-guide.md#-generative-ai)**

---

**[See All Examples with Detailed Walkthroughs →](docs/examples-guide.md)**

---

---

<details>
<summary><h2>📋 Feature Checklist</h2></summary>

**Legend:** ✅ Supported | 🔄 Planned | 🔮 Future

### Core Infrastructure
| Feature | Status | Notes |
|---------|--------|-------|
| YAML configuration | ✅ | [Manifest Guide](docs/manifest.md) |
| Infrastructure as Code | ✅ | [Deploy Command](docs/cli-commands.md#deploy) |
| Multi-environment deployment | ✅ | [Stages](docs/manifest-schema.md#stages) |
| CLI tool | ✅ | [CLI Commands](docs/cli-commands.md) |
| Version control integration | ✅ | [GitHub Actions](docs/github-actions-integration.md) |

### Deployment & Bundling
| Feature | Status | Notes |
|---------|--------|-------|
| Artifact bundling | ✅ | [Bundle Command](docs/cli-commands.md#bundle) |
| Bundle-based deployment | ✅ | [Deploy Command](docs/cli-commands.md#deploy) |
| Direct deployment | ✅ | [Deploy Command](docs/cli-commands.md#deploy) |
| Deployment validation | ✅ | [Describe Command](docs/cli-commands.md#describe) |
| Incremental deployment | 🔄 | Upload only changed files |
| Rollback support | 🔮 | Automated rollback |
| Blue-green deployment | 🔮 | Zero-downtime deployments |

### Developer Experience
| Feature | Status | Notes |
|---------|--------|-------|
| Project templates | 🔄 | `smus-cli init` with templates |
| Manifest initialization | ✅ | [Create Command](docs/cli-commands.md#create) |
| Interactive setup | 🔄 | Guided configuration prompts |
| Local development | ✅ | [CLI Commands](docs/cli-commands.md) |
| VS Code extension | 🔮 | IntelliSense and validation |

### Configuration
| Feature | Status | Notes |
|---------|--------|-------|
| Variable substitution | ✅ | [Substitutions Guide](docs/substitutions-and-variables.md) |
| Environment-specific config | ✅ | [Stages](docs/manifest-schema.md#stages) |
| Secrets management | 🔮 | AWS Secrets Manager integration |
| Config validation | ✅ | [Manifest Schema](docs/manifest-schema.md) |
| Connection management | ✅ | [Connections Guide](docs/connections.md) |

### Resources & Workloads
| Feature | Status | Notes |
|---------|--------|-------|
| Airflow DAGs | ✅ | [Workflows](docs/manifest-schema.md#workflows) |
| Jupyter notebooks | ✅ | [SageMakerNotebookOperator](docs/airflow-aws-operators.md#amazon-sagemaker) |
| Glue ETL jobs | ✅ | [GlueJobOperator](docs/airflow-aws-operators.md#aws-glue) |
| Athena queries | ✅ | [AthenaOperator](docs/airflow-aws-operators.md#amazon-athena) |
| SageMaker training | ✅ | [SageMakerTrainingOperator](docs/airflow-aws-operators.md#amazon-sagemaker) |
| SageMaker endpoints | ✅ | [SageMakerEndpointOperator](docs/airflow-aws-operators.md#amazon-sagemaker) |
| QuickSight dashboards | ✅ | [QuickSight Deployment](docs/quicksight-deployment.md) |
| Bedrock agents | ✅ | [BedrockInvokeModelOperator](docs/airflow-aws-operators.md#amazon-bedrock) |
| Lambda functions | 🔄 | [LambdaInvokeFunctionOperator](docs/airflow-aws-operators.md#aws-lambda) |
| EMR jobs | ✅ | [EmrAddStepsOperator](docs/airflow-aws-operators.md#amazon-emr) |
| Redshift queries | ✅ | [RedshiftDataOperator](docs/airflow-aws-operators.md#amazon-redshift) |

### Bootstrap Actions
| Feature | Status | Notes |
|---------|--------|-------|
| Workflow execution | ✅ | [workflow.run](docs/bootstrap-actions.md#workflowrun---trigger-workflow-execution) |
| Log retrieval | ✅ | [workflow.logs](docs/bootstrap-actions.md#workflowlogs---fetch-workflow-logs) |
| QuickSight refresh | ✅ | [quicksight.refresh_dataset](docs/bootstrap-actions.md#quicksightrefresh_dataset---trigger-dataset-ingestion) |
| EventBridge events | ✅ | [eventbridge.put_events](docs/bootstrap-actions.md#customput_events---emit-custom-events) |
| DataZone connections | ✅ | [datazone.create_connection](docs/bootstrap-actions.md) |
| Sequential execution | ✅ | [Execution Flow](docs/bootstrap-actions.md#execution-flow) |

### CI/CD Integration
| Feature | Status | Notes |
|---------|--------|-------|
| GitHub Actions | ✅ | [GitHub Actions Guide](docs/github-actions-integration.md) |
| GitLab CI | ✅ | [CLI Commands](docs/cli-commands.md) |
| Azure DevOps | ✅ | [CLI Commands](docs/cli-commands.md) |
| Jenkins | ✅ | [CLI Commands](docs/cli-commands.md) |
| Service principals | ✅ | [GitHub Actions Guide](docs/github-actions-integration.md) |
| OIDC federation | ✅ | [GitHub Actions Guide](docs/github-actions-integration.md) |

### Testing & Validation
| Feature | Status | Notes |
|---------|--------|-------|
| Unit testing | ✅ | [Test Command](docs/cli-commands.md#test) |
| Integration testing | ✅ | [Test Command](docs/cli-commands.md#test) |
| Automated tests | ✅ | [Test Command](docs/cli-commands.md#test) |
| Quality gates | ✅ | [Test Command](docs/cli-commands.md#test) |
| Workflow monitoring | ✅ | [Monitor Command](docs/cli-commands.md#monitor) |

### Monitoring & Observability
| Feature | Status | Notes |
|---------|--------|-------|
| Deployment monitoring | ✅ | [Deploy Command](docs/cli-commands.md#deploy) |
| Workflow monitoring | ✅ | [Monitor Command](docs/cli-commands.md#monitor) |
| Custom alerts | ✅ | [Deployment Metrics](docs/pipeline-deployment-metrics.md) |
| Metrics collection | ✅ | [Deployment Metrics](docs/pipeline-deployment-metrics.md) |
| Deployment history | ✅ | [Bundle Command](docs/cli-commands.md#bundle) |

### AWS Service Integration
| Feature | Status | Notes |
|---------|--------|-------|
| Amazon MWAA | ✅ | [Workflows](docs/manifest-schema.md#workflows) |
| MWAA Serverless | ✅ | [Workflows](docs/manifest-schema.md#workflows) |
| AWS Glue | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#aws-glue) |
| Amazon Athena | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#amazon-athena) |
| SageMaker | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#amazon-sagemaker) |
| Amazon Bedrock | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#amazon-bedrock) |
| Amazon QuickSight | ✅ | [QuickSight Deployment](docs/quicksight-deployment.md) |
| DataZone | ✅ | [Manifest Schema](docs/manifest-schema.md) |
| EventBridge | ✅ | [Deployment Metrics](docs/pipeline-deployment-metrics.md) |
| Lake Formation | ✅ | [Connections Guide](docs/connections.md) |
| Amazon S3 | ✅ | [Storage](docs/manifest-schema.md#storage) |
| AWS Lambda | 🔄 | [Airflow Operators](docs/airflow-aws-operators.md#aws-lambda) |
| Amazon EMR | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#amazon-emr) |
| Amazon Redshift | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#amazon-redshift) |

### Advanced Features
| Feature | Status | Notes |
|---------|--------|-------|
| Multi-region deployment | ✅ | [Stages](docs/manifest-schema.md#stages) |
| Cross-project deployment | ✅ | [Stages](docs/manifest-schema.md#stages) |
| Dependency management | ✅ | [Airflow Operators](docs/airflow-aws-operators.md) |
| Catalog subscriptions | ✅ | [Manifest Schema](docs/manifest-schema.md) |
| Multi-service orchestration | ✅ | [Airflow Operators](docs/airflow-aws-operators.md) |
| Drift detection | 🔮 | Detect configuration drift |
| State management | 🔄 | Comprehensive state tracking |

</details>

---

## Documentation

### Getting Started
- **[Quick Start Guide](docs/getting-started/quickstart.md)** - Deploy your first application (10 min)
- **[Admin Guide](docs/getting-started/admin-quickstart.md)** - Set up infrastructure (15 min)

### Guides
- **[Application Manifest](docs/manifest.md)** - Complete YAML configuration reference
- **[CLI Commands](docs/cli-commands.md)** - All available commands and options
- **[Bootstrap Actions](docs/bootstrap-actions.md)** - Automated deployment actions and event-driven workflows
- **[Substitutions & Variables](docs/substitutions-and-variables.md)** - Dynamic configuration
- **[Connections Guide](docs/connections.md)** - Configure AWS service integrations
- **[GitHub Actions Integration](docs/github-actions-integration.md)** - CI/CD automation setup
- **[Deployment Metrics](docs/pipeline-deployment-metrics.md)** - Monitoring with EventBridge

### Reference
- **[Manifest Schema](docs/manifest-schema.md)** - YAML schema validation and structure
- **[Airflow AWS Operators](docs/airflow-aws-operators.md)** - Custom operator reference

### Examples
- **[Examples Guide](docs/examples-guide.md)** - Walkthrough of example applications
- **[Data Notebooks](docs/examples-guide.md#-data-engineering---notebooks)** - Jupyter notebooks with Airflow
- **[ML Training](docs/examples-guide.md#-machine-learning---training)** - SageMaker training with MLflow
- **[ML Deployment](docs/examples-guide.md#-machine-learning---deployment)** - SageMaker endpoint deployment
- **[QuickSight Dashboard](docs/examples-guide.md#-analytics---quicksight-dashboard)** - BI dashboards with Glue
- **[GenAI Application](docs/examples-guide.md#-generative-ai)** - Bedrock agents and knowledge bases

### Development
- **[Development Guide](docs/development.md)** - Contributing and testing
- **[Tests Overview](tests/README.md)** - Testing infrastructure

### Support
- **Issues**: [GitHub Issues](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues)
- **Documentation**: [docs/](docs/)
- **Examples**: [examples/](examples/)

---

## Security Notice

⚠️ **DO NOT** install from PyPI - always install from official AWS source code.

```bash
# ✅ Correct - Install from official AWS repository
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .

# ❌ Wrong - Do not use PyPI
pip install smus-cicd-cli  # May contain malicious code
```

---

## License

This project is licensed under the MIT-0 License. See [LICENSE](../../LICENSE) for details.

---

<div align="center">
  <img src="docs/readme-qr-code.png" alt="Scan to view README" width="200"/>
  <p><em>Scan QR code to view this README on GitHub</em></p>
</div>


