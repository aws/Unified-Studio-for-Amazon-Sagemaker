# SMUS CI/CD CLI

A CLI tool for managing CI/CD pipelines in SageMaker Unified Studio (SMUS), enabling automated deployment of data science workflows and assets across multiple environments.

## Pipeline Manifest Reference
See **[Pipeline Manifest Reference](docs/pipeline-manifest.md)** for complete guide to pipeline configuration.

## CLI Commands Reference
See **[CLI Commands Reference](docs/cli-commands.md)** for detailed command documentation and examples.

## GitHub Actions Integration
See **[GitHub Actions Integration](docs/github-actions-integration.md)** for automated CI/CD pipeline setup.

## What is a CI/CD Pipeline?

**Continuous Integration/Continuous Deployment (CI/CD)** is a software development practice that automates the process of integrating code changes, testing them, and deploying them to different environments. A CI/CD pipeline consists of:

- **Source Control**: Code and configuration stored in version control
- **Build/Package**: Creating deployable artifacts from source code
- **Test Environments**: Staging areas for validation and testing
- **Production Deployment**: Automated deployment to live environments
- **Monitoring**: Tracking deployment success and application health

In the context of **SageMaker Unified Studio**, a CI/CD pipeline manages:
- **Data Science Workflows**: Airflow DAGs, Jupyter notebooks, and ML pipelines
- **Data Assets**: Datasets, models, and analytical outputs
- **Environment Configuration**: Project settings, user permissions, and resource allocation
- **Cross-Environment Promotion**: Moving validated work from dev → test → production

## SMUS Pipeline Architecture

The SMUS CI/CD system consists of CLI operations that manage target environments. Each target represents a complete deployment environment with its own resources.

### CLI Operations Flow

```mermaid
graph LR
    subgraph "Pipeline Manifest"
        PM[Pipeline YAML]
    end
    
    subgraph "CLI Commands"
        C1[1. describe] --> C2[2. bundle] --> C3[3. deploy] --> C4[4. run] --> C5[5. test] --> C6[6. monitor] --> C7[7. delete]
    end
    
    PM --> C1
```

### Target Environment Composition

#### Development Environment
```mermaid
graph TB
    subgraph "Dev Target Environment"
        T1[Target: dev]
        
        subgraph "SageMaker Unified Studio"
            P1[SageMaker Unified Studio Project<br/>dev-marketing]
        end
        
        subgraph "Connections"
            SC1[Storage Connection<br/>default.s3_shared]
            WC1[Workflow Connection<br/>project.workflow_mwaa]
            AC1[Analytics Connection<br/>project.athena]
            LC1[Lakehouse Connection<br/>project.default_lakehouse]
        end
        
        subgraph "AWS Resources"
            S31[S3 Bucket<br/>sagemaker-unified-studio-...-shared/]
            MWAA1[MWAA Environment<br/>SageMaker Unified StudioMWAAEnv-...-dev]
            ATHENA1[Athena Workgroup<br/>workgroup-...-dev]
            GLUE1[Glue Database<br/>sagemaker_unified_studio_..._dev]
        end
    end
    
    T1 --> P1
    P1 --> SC1
    P1 --> WC1
    P1 --> AC1
    P1 --> LC1
    
    SC1 --> S31
    WC1 --> MWAA1
    AC1 --> ATHENA1
    LC1 --> GLUE1
```

#### Test Environment
```mermaid
graph TB
    subgraph "Test Target Environment"
        T2[Target: test]
        
        subgraph "SageMaker Unified Studio"
            P2[SageMaker Unified Studio Project<br/>test-marketing]
        end
        
        subgraph "Connections"
            SC2[Storage Connection<br/>default.s3_shared]
            WC2[Workflow Connection<br/>project.workflow_mwaa]
            AC2[Analytics Connection<br/>project.athena]
            LC2[Lakehouse Connection<br/>project.default_lakehouse]
        end
        
        subgraph "AWS Resources"
            S32[S3 Bucket<br/>sagemaker-unified-studio-...-shared/]
            MWAA2[MWAA Environment<br/>SageMaker Unified StudioMWAAEnv-...-test]
            ATHENA2[Athena Workgroup<br/>workgroup-...-test]
            GLUE2[Glue Database<br/>sagemaker_unified_studio_..._test]
        end
    end
    
    T2 --> P2
    P2 --> SC2
    P2 --> WC2
    P2 --> AC2
    P2 --> LC2
    
    SC2 --> S32
    WC2 --> MWAA2
    AC2 --> ATHENA2
    LC2 --> GLUE2
```

#### Production Environment
```mermaid
graph TB
    subgraph "Prod Target Environment"
        T3[Target: prod]
        
        subgraph "SageMaker Unified Studio"
            P3[SageMaker Unified Studio Project<br/>prod-marketing]
        end
        
        subgraph "Connections"
            SC3[Storage Connection<br/>default.s3_shared]
            WC3[Workflow Connection<br/>project.workflow_mwaa]
            AC3[Analytics Connection<br/>project.athena]
            LC3[Lakehouse Connection<br/>project.default_lakehouse]
        end
        
        subgraph "AWS Resources"
            S33[S3 Bucket<br/>sagemaker-unified-studio-...-shared/]
            MWAA3[MWAA Environment<br/>SageMaker Unified StudioMWAAEnv-...-prod]
            ATHENA3[Athena Workgroup<br/>workgroup-...-prod]
            GLUE3[Glue Database<br/>sagemaker_unified_studio_..._prod]
        end
    end
    
    T3 --> P3
    P3 --> SC3
    P3 --> WC3
    P3 --> AC3
    P3 --> LC3
    
    SC3 --> S33
    WC3 --> MWAA3
    AC3 --> ATHENA3
    LC3 --> GLUE3
```

## Key Concepts

### Pipeline Stages → SMUS Projects

Each **pipeline stage** (dev, test, prod) maps to a **SageMaker Unified Studio Project**:

- **Dev Stage** → **Dev Project** (`dev-marketing`)
  - Development and experimentation
  - Rapid iteration and testing
  - Individual developer workspaces

- **Test Stage** → **Test Project** (`test-marketing`)
  - Integration testing and validation
  - Staging environment for QA
  - Pre-production verification

- **Prod Stage** → **Prod Project** (`prod-marketing`)
  - Production deployment
  - Live data processing
  - Business-critical workflows

### Resource Mapping

Each project contains:
- **S3 Storage Connections** - For data assets and notebooks
- **Workflow Connections** - For Airflow DAGs and ML pipelines
- **Environment Configurations** - Compute and runtime settings
- **User Permissions** - Access control and collaboration

## Installation

### From Source
```bash
# Clone the repository
git clone https://github.com/your-org/smus-cicd-pipeline-cli.git
cd smus-cicd-pipeline-cli

# Install in development mode
pip install -e ".[dev]"

# Or install normally
pip install .
```

### From PyPI (when published)
```bash
pip install smus-cicd-cli
```

## Quick Start

For detailed command examples and outputs, see **[CLI Commands Reference](docs/cli-commands.md)**.

### Basic Workflow
```bash
# 1. Validate pipeline configuration
smus-cli describe --pipeline pipeline.yaml --connect

# 2. Create deployment bundle from dev environment
smus-cli bundle --pipeline pipeline.yaml --targets dev

# 3. Deploy to marketing test stage
smus-cli deploy --targets marketing-test-stage --pipeline pipeline.yaml

# 4. Monitor workflow status
smus-cli monitor --pipeline pipeline.yaml

# 5. Trigger workflow execution
smus-cli run --pipeline pipeline.yaml --targets marketing-test-stage --workflow test_dag --command trigger

# 6. Run tests to validate deployment
smus-cli test --pipeline pipeline.yaml --targets marketing-test-stage

# 7. Clean up resources (when needed)
smus-cli delete --targets marketing-test-stage --pipeline pipeline.yaml --force
```

## Common Workflows

### Development Workflow
1. **Update code** in dev environment S3 location
2. **Create bundle**: `smus-cli bundle` (downloads latest from dev)
3. **Deploy to test**: `smus-cli deploy --targets test` (deploys and triggers workflows)
4. **Verify execution**: Check workflow runs in SageMaker Unified Studio console
5. **Deploy to prod**: `smus-cli deploy --targets prod` (when ready)

### Complete CI/CD Flow
```bash
# 1. Analyze pipeline configuration
smus-cli describe --pipeline pipeline.yaml --workflows --targets --connect

# 2. Create deployment bundle from current dev state
smus-cli bundle dev

# 3. Deploy to staging (auto-initializes if needed)
smus-cli deploy --targets staging

# 4. After validation, deploy to production (auto-initializes if needed)
smus-cli deploy --targets prod
```

## Testing

The project includes comprehensive unit and integration tests with coverage analysis.

### Quick Testing Commands

```bash
# Run all tests with coverage and HTML reports (default)
python scripts/run_tests.py

# Run only unit tests
python scripts/run_tests.py --type unit

# Run only integration tests
python scripts/run_tests.py --type integration

# Skip HTML report generation
python scripts/run_tests.py --no-html-report

# Skip slow tests (useful for CI)
python scripts/run_tests.py --skip-slow

# Run without coverage (faster)
python scripts/run_tests.py --no-coverage
```

### Direct pytest Commands

```bash
# Run all tests with coverage
pytest --cov=src/smus_cicd --cov-report=html

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run tests excluding slow ones
pytest -m "not slow"

# Run specific test file
pytest tests/integration/test_new_commands.py -v
```

### Coverage Reports

Coverage reports are automatically generated:
- **Terminal**: Shows coverage summary in terminal
- **HTML**: Detailed report in `htmlcov/index.html` (use `--html-report`)
- **XML**: Machine-readable report in `coverage.xml` for CI systems

### Test Categories

- **Unit Tests**: Fast tests that don't require AWS resources (`tests/unit/`)
- **Integration Tests**: Tests that interact with AWS services (`tests/integration/`)
- **Slow Tests**: Long-running tests marked with `@pytest.mark.slow`

### AWS Configuration for Integration Tests

Integration tests require AWS credentials. Configure using:

1. **AWS Profile**: `export AWS_PROFILE=your-profile`
2. **Environment Variables**: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
3. **Config File**: `tests/integration/config.local.yaml`

See [tests/README.md](tests/README.md) for detailed testing documentation.
