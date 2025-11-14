# SMUS CI/CD Pipeline Examples

This directory contains example pipelines and configurations demonstrating SMUS CI/CD capabilities.

## 📋 Table of Contents

- [Testing Overview](#testing-overview)
- [Integration Tests](#integration-tests)
- [Test Setup](#test-setup)
- [Running Tests Locally](#running-tests-locally)
- [Example Pipelines](#example-pipelines)

---

## Testing Overview

The SMUS CI/CD pipeline includes two test suites:

### Unit Tests
Located in `tests/unit/`, these tests validate individual components and helper functions without requiring AWS resources:
- **Context resolver** - Variable substitution and template resolution
- **Connection creator** - DataZone connection configuration
- **Pipeline manifest** - YAML schema validation and parsing
- **Monitoring** - Event emission and metadata collection

Run unit tests:
```bash
pytest tests/unit/ -v
```

### Integration Tests
Located in `tests/integration/`, these tests validate end-to-end pipeline workflows using real AWS resources:
- Deploy pipelines to DataZone domains
- Create and configure projects
- Execute workflows on Airflow Serverless
- Validate data processing results
- Test multi-target deployments

Run integration tests:
```bash
pytest tests/integration/ -v
```

---

## Integration Tests

### Core Pipeline Tests

#### 1. **Basic Pipeline** (`tests/integration/basic_pipeline/`)
Tests fundamental pipeline operations with simple workflows.

**What it tests:**
- Pipeline manifest validation
- Project creation and initialization
- Workflow deployment to Airflow Serverless
- Basic workflow execution
- Connection creation (S3, Athena)

**Key files:**
- `basic_bundle.yaml` - Simple pipeline with one workflow
- `test_basic_pipeline.py` - Test suite

---

#### 2. **Multi-Target Pipeline** (`tests/integration/multi_target_pipeline/`)
Tests deployment across multiple environments (dev → test → prod).

**What it tests:**
- Multi-target deployment workflow
- Environment-specific configuration
- Project auto-initialization
- Cross-environment promotion
- Target-specific testing

**Key files:**
- Pipeline manifest with dev/test/prod targets
- `test_multi_target_pipeline.py` - Multi-stage deployment tests
- `pipeline_tests/test_project_validation.py` - Per-target validation

---

#### 3. **Bundle Deploy Pipeline** (`tests/integration/bundle_deploy_pipeline/`)
Tests bundle creation and deployment workflow.

**What it tests:**
- Bundle creation from source environment
- Bundle storage in S3
- Bundle deployment to target environments
- Bundle validation and integrity checks

**Key files:**
- `test_bundle_deploy_pipeline.py` - Bundle workflow tests
- `pipeline_tests/test_bundle_validation.py` - Bundle content validation

---

### Analytics Workflow Tests

#### 4. **ETL Workflow** (`tests/integration/examples-analytics-workflows/etl/`)
Tests complete ETL pipeline with AWS Glue jobs processing COVID-19 data.

**What it tests:**
- Git repository cloning to S3
- AWS Glue job creation and execution
- Multi-stage ETL workflow (setup → discovery → summary)
- Glue Data Catalog table creation
- Parquet data generation
- Athena query validation

**Pipeline components:**
- `etl_bundle.yaml` - Pipeline manifest with git bundle
- `covid_etl_workflow.yaml` - Airflow DAG definition
- `glue_setup_covid_db.py` - Database/table setup
- `glue_s3_list_job.py` - Data discovery
- `glue_covid_summary_job.py` - Data aggregation
- `pipeline_tests/test_covid_data.py` - Data validation tests

**Data flow:**
1. Clone COVID-19 dataset from GitHub
2. Setup Glue database and table
3. Discover CSV files in S3
4. Read CSV with Spark, aggregate by country
5. Write Parquet summary to S3
6. Validate results with Athena

---

#### 5. **ML Workflow** (`tests/integration/examples-analytics-workflows/ml/`)
Tests machine learning pipeline with SageMaker training and MLflow tracking.

**What it tests:**
- SageMaker training job execution
- MLflow experiment tracking
- Model artifact storage
- Workflow orchestration with dependencies

**Key files:**
- `ml_bundle.yaml` - ML bundle manifest
- `test_ml_workflow.py` - ML workflow tests
- `job-code/` - Training scripts

---

#### 6. **Notebooks Workflow** (`tests/integration/examples-analytics-workflows/notebooks/`)
Tests parallel execution of multiple example notebooks.

**What it tests:**
- Parallel notebook execution (9 notebooks simultaneously)
- SageMakerNotebookOperator functionality
- Notebook bundle deployment
- Validation that all notebooks complete successfully

**Pipeline components:**
- `notebooks_bundle.yaml` - Pipeline manifest
- `parallel_notebooks_workflow.yaml` - Airflow DAG with 9 parallel tasks
- `notebooks/` - 9 example notebooks (Pandas, Spark, DuckDB, MLflow, etc.)
- `pipeline_tests/test_notebooks_execution.py` - Success validation

**Notebooks included:**
1. Basic Python with Pandas
2. GDC Read/Write with Athena
3. Customer Churn Analysis (Spark)
4. Purchase Analytics (DuckDB)
5. GenAI ETL (Pandas)
6. City Temperature ETL (Spark)
7. Time Series Forecasting (Chronos)
8. Movie Sales (DynamoDB)
9. Classification (MLflow)

---

### Connection Tests

#### 7. **DataZone Connections** (`tests/integration/connections_pipeline/`)
Tests DataZone connection creation and management.

**What it tests:**
- S3 connection creation
- Athena connection configuration
- Connection permissions
- Connection validation

---

### Specialized Tests

#### 8. **Create/Delete Pipeline** 
- `tests/integration/create_test_pipeline/` - Pipeline creation
- `tests/integration/delete_test_pipeline/` - Pipeline cleanup

#### 9. **Multi-Target Airless** (`tests/integration/multi_target_pipeline_airless/`)
Tests deployment without Airflow Serverless (notebooks only).

---

## Test Setup

### Prerequisites

1. **AWS Account** with permissions for:
   - SageMaker Unified Studio (DataZone)
   - CloudFormation
   - IAM role creation
   - S3, Glue, Athena, SageMaker

2. **SMUS CLI** installed:
   ```bash
   pip install -e .
   ```

3. **AWS Credentials** configured:
   ```bash
   aws configure
   # or use AWS SSO
   aws sso login --profile your-profile
   ```

### Setup Directory Structure

The `tests/scripts/` directory contains modular setup scripts:

```
tests/scripts/
├── config.yaml                      # Main configuration file
├── config-*.yaml                    # Environment-specific configs
├── README.md                        # Setup documentation
│
├── setup/                           # Infrastructure setup scripts
│   ├── deploy-all.sh               # Master deployment script
│   ├── 1-account-setup/            # GitHub OIDC, VPC
│   ├── 2-domain-creation/          # SMUS domain
│   ├── 3-domain-configuration/     # Blueprints, profiles
│   ├── 4-project-setup/            # Dev project
│   ├── 5-testing-infrastructure/   # MLflow, test data
│   └── 6-fix-project-roles/        # Role permissions
│
└── datazone/                        # DataZone helper scripts
    ├── create_project.py
    ├── list_projects.py
    └── ...
```

### Setup Steps

Each setup stage is independent and can be run separately:

#### **Stage 1: Account Setup**
Creates GitHub OIDC role and VPC infrastructure.

```bash
cd tests/scripts/setup/1-account-setup
./deploy.sh ../config.yaml
```

**Outputs:**
- VPC ID, subnet IDs
- GitHub Actions IAM role ARN

---

#### **Stage 2: Domain Creation**
Creates SageMaker Unified Studio domain.

```bash
cd tests/scripts/setup/2-domain-creation
./deploy.sh ../config.yaml
```

**Outputs:**
- Domain ID
- Domain ARN
- Portal URL

**Skip if:** Domain already exists (use existing domain ID in config)

---

#### **Stage 3: Domain Configuration**
Enables environment blueprints and project profiles.

```bash
cd tests/scripts/setup/3-domain-configuration
./deploy.sh ../config.yaml
```

**Outputs:**
- Enabled blueprint IDs
- Available project profiles

---

#### **Stage 4: Project Setup**
Creates dev project and adds members.

```bash
cd tests/scripts/setup/4-project-setup
./deploy.sh ../config.yaml
```

**Outputs:**
- Dev project ID
- Project membership details

---

#### **Stage 5: Testing Infrastructure**
Creates MLflow server, SageMaker role, and test data.

```bash
cd tests/scripts/setup/5-testing-infrastructure
./deploy.sh ../config.yaml
```

**Outputs:**
- MLflow tracking server ARN
- SageMaker execution role ARN
- S3 bucket for test data

**Note:** This stage is independent and can run anytime.

---

#### **Stage 6: Fix Project Roles** (if needed)
Updates project role permissions for Lake Formation.

```bash
cd tests/scripts/setup/6-fix-project-roles
./deploy.sh ../config.yaml
```

---

### Full Setup (All Stages)

Run all stages in sequence:

```bash
cd tests/scripts/setup
./deploy-all.sh ../config.yaml
```

---

## Running Tests Locally

### 1. Configure Test Environment

Create or update `tests/scripts/config.yaml`:

```yaml
account_id: "123456789012"
regions:
  primary:
    name: us-east-1
    enabled: true

domain:
  id: dzd_abc123xyz
  name: my-smus-domain
  admin_user: admin@example.com

projects:
  dev:
    id: 5330xnk7amt221
    name: dev-marketing
```

### 2. Run Specific Test

```bash
# Run ETL workflow test
pytest tests/integration/examples-analytics-workflows/etl/test_etl_workflow.py -v

# Run with output
pytest tests/integration/examples-analytics-workflows/etl/test_etl_workflow.py -v -s

# Run specific test method
pytest tests/integration/examples-analytics-workflows/etl/test_etl_workflow.py::TestETLWorkflow::test_etl_workflow_deployment -v
```

### 3. Run Test Suite

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run with coverage
pytest tests/integration/ --cov=src/smus_cicd --cov-report=html

# Run with markers
pytest tests/integration/ -m "not slow" -v
```

### 4. Debug Test Failures

Test outputs are saved to `tests/test-outputs/`:
- `TestName__test_method.log` - Detailed execution log
- `test-results.html` - HTML test report

```bash
# View test log
tail -f tests/test-outputs/TestETLWorkflow__test_etl_workflow_deployment.log

# Open HTML report
open tests/reports/test-results.html
```

---

## Example Pipelines

### Simple Pipeline

**File:** `TestPipeline.yaml`

Minimal pipeline for testing basic functionality:
- Single target (dev)
- One workflow
- S3 storage bundle

```bash
smus-cli describe --bundle examples/TestPipeline.yaml
smus-cli deploy dev --bundle examples/TestPipeline.yaml
```

---

### Demo Pipeline

**File:** `demo-bundle.yaml`

Comprehensive demo showing all features:
- Multi-target deployment (dev/test/prod)
- S3 bundle storage
- Auto-initialization
- Environment-specific parameters

```bash
smus-cli describe --bundle examples/demo-bundle.yaml --connect
smus-cli deploy test --bundle examples/demo-bundle.yaml
```

---

### Analytics Workflows

#### ETL Pipeline
**Location:** `analytic-workflow/etl/`

Complete ETL workflow with:
- Git repository cloning
- AWS Glue jobs
- Data transformation
- Athena queries

```bash
cd examples/analytic-workflow/etl
smus-cli deploy test --bundle etl_bundle.yaml
smus-cli run --workflow covid_etl_pipeline --targets test --bundle etl_bundle.yaml
smus-cli test --targets test --bundle etl_bundle.yaml
```

#### ML Pipeline
**Location:** `analytic-workflow/ml/`

Machine learning workflow with:
- SageMaker training
- MLflow tracking
- Model artifacts

```bash
cd examples/analytic-workflow/ml
smus-cli deploy test --bundle ml_bundle.yaml
```

---

## Additional Resources

- **Setup Guide:** `tests/scripts/setup/README.md`
- **CLI Documentation:** `docs/cli-commands.md`
- **Bundle Manifest Schema:** `docs/pipeline-manifest-schema.md`
- **Pipeline Deployment Metrics:** `docs/pipeline-deployment-metrics.md`
