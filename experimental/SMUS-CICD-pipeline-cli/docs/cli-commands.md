# CLI Commands Reference

← [Back to Main README](../README.md)

The SMUS CLI provides seven main commands for managing CI/CD pipelines in SageMaker Unified Studio.

## Command Overview

| Command | Purpose | Example |
|---------|---------|---------|
| `create` | Create new pipeline manifest | `smus-cli create --output pipeline.yaml` |
| `describe` | Validate and show pipeline configuration | `smus-cli describe --pipeline pipeline.yaml --connect` |
| `bundle` | Package files from source environment | `smus-cli bundle --targets dev` |
| `deploy` | Deploy bundle to target environment | `smus-cli deploy --targets test --bundle bundle.zip` |
| `run` | Execute Airflow commands or trigger workflows | `smus-cli run --command version` or `smus-cli run --workflows dag1,dag2` |
| `monitor` | Monitor workflow status | `smus-cli monitor --pipeline pipeline.yaml` |
| `test` | Run tests for pipeline targets | `smus-cli test --targets marketing-test-stage` |
| `delete` | Remove target environments | `smus-cli delete --targets marketing-test-stage --force` |

## Detailed Command Examples

### 1. Describe Pipeline Configuration
```bash
# Basic describe
smus-cli describe --pipeline pipeline.yaml

# Describe with connection details and AWS connectivity
smus-cli describe --pipeline pipeline.yaml --connect
```
**Example Output:**
```
Pipeline: IntegrationTestMultiTarget
Domain: cicd-test-domain (us-east-1)

Targets:
  - dev: dev-marketing
    Project Name: dev-marketing
    Project ID: <dev-project-id>
    Status: ACTIVE
    Owners: Admin, eng1
    Connections:
      project.workflow_mwaa:
        connectionId: 6f58emph2gtciv
        type: WORKFLOWS_MWAA
        region: us-east-1
        awsAccountId: <aws-account-id>
        description: Connection for MWAA environment
        environmentName: DataZoneMWAAEnv-<domain-id>-<project-id>-dev
      default.s3_shared:
        connectionId: dqbxjn28zehzjb
        type: S3
        region: us-east-1
        awsAccountId: <aws-account-id>
        description: This is the connection to interact with s3 shared storage location if enabled in the project.
        s3Uri: s3://sagemaker-unified-studio-<aws-account-id>-us-east-1-your-domain-name/<domain-id>/<dev-project-id>/shared/
        status: READY

Manifest Workflows:
  - test_dag
    Connection: project.workflow_mwaa
    Engine: MWAA
  - execute_notebooks_dag
    Connection: project.workflow_mwaa
    Engine: MWAA
```

### 2. Bundle Creation
```bash
# Bundle for specific target
smus-cli bundle --targets dev --output-dir ./bundles

# Bundle for multiple targets
smus-cli bundle --targets dev,test --output-dir /tmp/bundles
```

### 3. Deploy Bundle
```bash
# Deploy using auto-created bundle
smus-cli deploy --targets test

# Deploy using pre-created bundle file
smus-cli deploy --targets test --bundle /path/to/bundle.zip

# Deploy with JSON output
smus-cli deploy --targets test --bundle bundle.zip --output JSON
```

### 4. Run Commands and Workflows

#### Execute Airflow CLI Commands
```bash
# Get Airflow version
smus-cli run --command version

# List all DAGs
smus-cli run --command "dags list"

# Get DAG state
smus-cli run --command "dags state my_dag"
```

#### Trigger Workflows
```bash
# Trigger single workflow
smus-cli run --workflows test_dag

# Trigger multiple workflows
smus-cli run --workflows test_dag,execute_notebooks_dag

# Trigger all manifest workflows
smus-cli run --workflows all
```

#### Combined Usage
```bash
# Run command on specific workflow context
smus-cli run --workflows test_dag --command "dags trigger test_dag"
```

**Example Output (TEXT format):**
```
🔍 Checking MWAA health for target 'test' (project: integration-test-test)
🎯 Target: test
🚀 Triggering workflow: test_dag
🔧 Connection: project.workflow_mwaa (DataZoneMWAAEnv-dzd_6je2k8b63qse07-broygppc8vw17r-dev)
📋 Command: dags trigger test_dag
✅ Command executed successfully
📤 Output:
2.10.1
```

**Example Output (JSON format):**
```json
{
  "workflows": ["test_dag"],
  "command": "dags trigger test_dag",
  "results": [
    {
      "target": "test",
      "connection": "project.workflow_mwaa",
      "environment": "DataZoneMWAAEnv-dzd_6je2k8b63qse07-broygppc8vw17r-dev",
      "success": true,
      "status_code": 200,
      "command": "dags trigger test_dag",
      "raw_stdout": "...",
      "raw_stderr": "..."
    }
  ],
  "success": true
}
```

### 5. Monitor Workflows
```bash
# Monitor all targets
smus-cli monitor --pipeline pipeline.yaml

# Monitor specific targets with JSON output
smus-cli monitor --targets test --output JSON
```

### 6. Test Pipeline
```bash
# Run tests for all targets
smus-cli test --pipeline pipeline.yaml

# Run tests for specific targets
smus-cli test --targets test --verbose
```

### 7. Delete Resources
```bash
# Delete with confirmation
smus-cli delete --targets test

# Force delete without confirmation
smus-cli delete --targets test --force

# Async delete (don't wait for completion)
smus-cli delete --targets test --force --async
```

## Universal Options

All commands support these universal options:

| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--pipeline` | `-p` | Path to pipeline manifest file | `--pipeline my-pipeline.yaml` |
| `--targets` | `-t` | Target environment(s) | `--targets dev,test` |
| `--output` | `-o` | Output format (TEXT/JSON) | `--output JSON` |

## Output Formats

### TEXT Format (Default)
- Human-readable output with emojis and formatting
- Raw stdout/stderr for run commands
- Suitable for interactive use

### JSON Format
- Structured data output
- Suitable for automation and scripting
- All commands support JSON output via `--output JSON`

## Error Handling

The CLI provides comprehensive error handling:
- **Exit Code 0**: Success
- **Exit Code 1**: Error occurred
- **Graceful Failures**: Commands handle missing infrastructure gracefully
- **Detailed Error Messages**: Clear indication of what went wrong and how to fix it

## MWAA Integration

The CLI automatically validates MWAA environment health before executing workflow commands:
- ✅ **MWAA Available**: Commands execute successfully
- ❌ **MWAA Unavailable**: Commands fail with clear error message
- 🔍 **Auto-Detection**: CLI automatically finds and validates MWAA connections
        workgroup: workgroup-<dev-project-id>-xyz123
      project.spark.compatibility:
        connectionId: 6236xbz8cowo4n
        type: SPARK
        region: us-east-1
        awsAccountId: <aws-account-id>
        description: Glue-ETL compute with Permission Mode set to compatibility. (Auto-created by project).
        glueVersion: 5.0
        workerType: G.1X
        numberOfWorkers: 10
      project.workflow_mwaa:
        connectionId: d5jq3vs4ol9s13
        type: WORKFLOWS_MWAA
        region: us-east-1
        awsAccountId: <aws-account-id>
        description: Connection for MWAA environment
        environmentName: SageMaker Unified StudioMWAAEnv-<domain-id>-<dev-project-id>-dev

Manifest Workflows:
  - test_dag (Connection: project.workflow_mwaa, Engine: MWAA)
  - runGettingStartedNotebook (Connection: project.workflow_mwaa, Engine: MWAA)
```

**What this shows:** The describe command validates your pipeline configuration and displays the structure of your CI/CD pipeline. It shows each target environment (dev, test, prod) with their associated SageMaker Unified Studio projects, available connections for data storage and workflow execution, and the workflows defined in your manifest. This is essential for understanding your pipeline setup and ensuring all resources are properly configured before deployment.

### 2. Create Bundle from Dev Environment
```bash
smus-cli bundle --pipeline pipeline.yaml --targets dev
```
**Example Output:**
```
Creating bundle for target: dev
Project: dev-marketing
Downloading workflows from S3: default.s3_shared (append: True)
  Downloaded: workflows/dags/test_dag.py
  Downloaded: workflows/.visual/runGettingStartedNotebook.wf
  Downloaded 17 workflow files from S3
Downloading storage from S3: default.s3_shared (append: False)
  Downloaded: src/test-notebook1.ipynb
  Downloaded 1 storage files from S3
Creating archive: IntegrationTestMultiTarget.zip
✅ Bundle created: s3://my-datazone-bucket/bundles/IntegrationTestMultiTarget.zip (279462 bytes)

📦 Bundle Contents:
==================================================
├── storage/
│   └── src/
│       └── test-notebook1.ipynb
└── workflows/
    ├── .visual/
    │   └── runGettingStartedNotebook.wf
    ├── dags/
    │   ├── test_dag.py
    │   └── visual/
    │       └── runGettingStartedNotebook.py
    └── config/
        ├── requirements.txt
        └── startup.sh
==================================================
📊 Total files: 18
Bundle creation complete for target: dev
```

**What this shows:** The bundle command downloads all workflows and storage files from your development environment and packages them into a deployment-ready ZIP file. When using S3 bundle storage (configured via `bundlesDirectory: s3://bucket/path`), the bundle is automatically uploaded to S3 after creation. This creates a centralized bundle that can be accessed by team members and CI/CD systems from anywhere.

### 3. Deploy to Test Environment
```bash
smus-cli deploy --targets test --pipeline pipeline.yaml
```
**Example Output:**
```
Deploying to target: test
Project: integration-test-test
Domain: cicd-test-domain
Region: us-east-1
🔧 Auto-initializing target infrastructure...
✅ Target infrastructure ready
✅ Project 'integration-test-test' exists
Bundle file: s3://my-datazone-bucket/bundles/IntegrationTestMultiTarget.zip
Downloading bundle from S3...
Deploying storage to: default.s3_shared/src (append: False)
  S3 Location: s3://sagemaker-unified-studio-<aws-account-id>-us-east-1-your-domain-name/.../shared/src/
    Synced: test-notebook1.ipynb
  Storage files synced: 1
Deploying workflows to: default.s3_shared/workflows (append: True)
  S3 Location: s3://sagemaker-unified-studio-<aws-account-id>-us-east-1-your-domain-name/.../shared/workflows/
    Synced: test_dag.py
    Synced: runGettingStartedNotebook.py
  Workflow files synced: 17
✅ Deployment complete! Total files synced: 18

🚀 Starting workflow validation...
✅ MWAA environment is available
🆕 New DAGs detected: runGettingStartedNotebook
```

**What this shows:** The deploy command downloads the bundle from S3 (if using S3 bundle storage) and uploads the files to the target environment's SageMaker Unified Studio project storage and workflow connections. It shows the deployment progress, file counts, and validates that the MWAA environment can access the new workflows. This ensures your code changes are properly deployed and ready for execution.

### 4. Monitor Workflow Status
```bash
smus-cli monitor --pipeline pipeline.yaml
```
**Example Output:**
```
Pipeline: IntegrationTestMultiTarget
Domain: cicd-test-domain (us-east-1)

🔍 Monitoring Status:

🎯 Target: test
   Project: integration-test-test
   Project ID: <test-project-id>
   Status: ACTIVE
   Owners: Admin, eng1

   📊 Workflow Status:
      🔧 project.workflow_mwaa (SageMaker Unified StudioMWAAEnv-<domain-id>-<test-project-id>-dev)
         🌐 Airflow UI: https://your-mwaa-environment.airflow.us-east-1.on.aws
         🔄 ✓ test_dag
            Schedule: Manual | Status: ACTIVE | Recent: Unknown
         🔄 ✓ runGettingStartedNotebook
            Schedule: Manual | Status: ACTIVE | Recent: Unknown

📋 Manifest Workflows:
   - test_dag (Connection: project.workflow_mwaa)
   - runGettingStartedNotebook (Connection: project.workflow_mwaa)
```

**What this shows:** The monitor command provides real-time status of your pipeline's workflow environments. It displays project information, workflow connection details, and the current state of all DAGs in your MWAA environments. This is essential for tracking workflow health, identifying issues, and understanding the operational status of your data pipelines across different environments.

### 5. Trigger Workflow Execution
```bash
smus-cli run --pipeline pipeline.yaml --targets test --workflow test_dag --command trigger
```
**Example Output:**
```
🎯 Target: test
🔧 Connection: project.workflow_mwaa (SageMaker Unified StudioMWAAEnv-<domain-id>-<test-project-id>-dev)
📋 Command: trigger
✅ Workflow triggered successfully
📤 Run ID: manual__2025-08-25T11:45:00+00:00
```

**What this shows:** The run command executes Airflow CLI commands against your MWAA environments. In this example, it triggers a workflow execution and returns the run ID for tracking. This allows you to programmatically control workflow execution, check status, and manage your data pipelines from the command line.

### 6. Run Tests
```bash
smus-cli test --pipeline pipeline.yaml --targets marketing-test-stage
```
**Example Output:**
```
Pipeline: IntegrationTestMultiTarget
Domain: cicd-test-domain (us-east-1)

🎯 Target: test
  📁 Test folder: tests/
  🔧 Project: integration-test-test (your-project-id)
  🧪 Running tests...
  ✅ Tests passed

🎯 Test Summary:
  ✅ Passed: 1
  ❌ Failed: 0
  ⚠️  Skipped: 0
  🚫 Errors: 0
```

**What this shows:** The test command runs Python tests from the configured test folder against your deployed pipeline. Tests receive environment variables with domain ID, project ID, and other context information to validate the deployment. This ensures your pipeline is working correctly after deployment and provides automated validation of your data workflows.

### 7. Clean Up Resources
```bash
smus-cli delete --targets test --pipeline pipeline.yaml --force
```
**Example Output:**
```
Pipeline: IntegrationTestMultiTarget
Domain: cicd-test-domain (us-east-1)

Targets to delete:
  - test: integration-test-test

🗑️  Deleting target: test
✅ Successfully deleted project: integration-test-test

🎯 Deletion Summary
  ✅ test: Project deleted successfully
```

**What this shows:** The delete command removes SageMaker Unified Studio projects and their associated resources. It provides a summary of deletion operations, showing which projects were successfully removed. This is useful for cleaning up test environments and managing resource lifecycle in your CI/CD pipeline.

```bash
smus-cli --help
```

### Pipeline Commands

0. **`create`** - Create new pipeline manifest
1. **`describe`** - Describe and validate pipeline configuration
2. **`bundle`** - Create deployment packages from source
3. **`deploy`** - Deploy packages to targets (auto-initializes if needed)
4. **`monitor`** - Monitor workflow status
5. **`run`** - Run Airflow CLI commands
6. **`delete`** - Delete projects and environments

## Command Details

### 0. create - Create New Pipeline Manifest

Creates a new pipeline manifest file with basic structure.

```bash
smus-cli create [OPTIONS]
```

#### Options
- **`-o, --output`**: Output file path for the new pipeline manifest (default: `pipeline.yaml`)
- **`-n, --name`**: Pipeline name (optional, will use placeholder if not provided)
- **`-t, --targets`**: Target name(s) - single target or comma-separated list (optional)
- **`--help`**: Show command help

#### Examples

```bash
# Create basic pipeline manifest
smus-cli create

# Create with custom output file and name
smus-cli create -o my-pipeline.yaml -n MyPipeline

# Create with specific targets
smus-cli create -o pipeline.yaml -t dev,test,prod
```

### 1. describe - Describe Pipeline Configuration

Validates and displays information about your pipeline manifest.

```bash
smus-cli describe [OPTIONS]
```

#### Options
- **`-p, --pipeline`**: Path to pipeline manifest file (default: `pipeline.yaml`)
- **`-t, --targets`**: Target name(s) - single target or comma-separated list (optional, defaults to all targets)
- **`-o, --output`**: Output format: TEXT (default) or JSON
- **`-w, --workflows`**: Show workflow information
- **`-c, --connections`**: Show connection information
- **`--connect`**: Connect to AWS account and pull additional information
- **`--help`**: Show command help

#### Examples

```bash
# Basic describe
smus-cli describe

# Describe specific targets with workflows
smus-cli describe -t dev,test -w

# Describe with AWS connection info in JSON format
smus-cli describe --connect -o JSON

# Describe specific pipeline file
smus-cli describe -p my-pipeline.yaml
```

### 2. bundle - Create Deployment Packages

Creates bundle zip files by downloading from S3.

```bash
smus-cli bundle [OPTIONS]
```

#### Options
- **`-p, --pipeline`**: Path to pipeline manifest file (default: `pipeline.yaml`)
- **`-t, --targets`**: Target name(s) - single target or comma-separated list (uses default target if not specified)
- **`-d, --output-dir`**: Output directory for bundle files (default: `./bundles`)
- **`-o, --output`**: Output format: TEXT (default) or JSON
- **`--help`**: Show command help

#### Bundle Storage Locations

The bundle command supports both local and S3 storage locations via the `bundlesDirectory` configuration in your pipeline manifest:

**Local Storage:**
```yaml
bundlesDirectory: ./bundles
```
- Bundles are created directly in the specified local directory
- Suitable for development and single-user workflows

**S3 Storage:**
```yaml
bundlesDirectory: s3://my-datazone-bucket/bundles
```
- Bundles are created locally then uploaded to S3
- Enables team collaboration and CI/CD integration
- Works with DataZone domain S3 buckets
- Requires appropriate S3 permissions

#### Examples

```bash
# Bundle default target
smus-cli bundle

# Bundle specific targets
smus-cli bundle -t dev,test

# Bundle to custom directory
smus-cli bundle -d /path/to/bundles

# Bundle with JSON output
smus-cli bundle -o JSON
```

### 3. deploy - Deploy to Targets

Deploys bundle files to target environments (auto-initializes if needed).

```bash
smus-cli deploy [OPTIONS]
```

#### Options
- **`-p, --pipeline`**: Path to pipeline manifest file (default: `pipeline.yaml`)
- **`-t, --targets`**: Target name(s) - single target or comma-separated list (uses default target if not specified)
- **`--help`**: Show command help

#### Examples

```bash
# Deploy to default target
smus-cli deploy

# Deploy to specific targets
smus-cli deploy -t test,prod

# Deploy specific pipeline
smus-cli deploy -p my-pipeline.yaml -t prod
```

### 4. monitor - Monitor Workflow Status

Monitors workflow status across target environments.

```bash
smus-cli monitor [OPTIONS]
```

#### Options
- **`-p, --pipeline`**: Path to pipeline manifest file (default: `pipeline.yaml`)
- **`-t, --targets`**: Target name(s) - single target or comma-separated list (shows all targets if not specified)
- **`-o, --output`**: Output format: TEXT (default) or JSON
- **`--help`**: Show command help

#### Examples

```bash
# Monitor all targets
smus-cli monitor

# Monitor specific targets
smus-cli monitor -t dev,test

# Monitor with JSON output
smus-cli monitor -o JSON
```

### 5. run - Run Airflow CLI Commands

Executes Airflow CLI commands on target environments.

```bash
smus-cli run [OPTIONS]
```

#### Options
- **`-w, --workflow`**: Workflow name to target (required)
- **`-c, --command`**: Airflow command to execute (required)
- **`-t, --targets`**: Target name(s) - single target or comma-separated list (optional, defaults to first available)
- **`-p, --pipeline`**: Path to pipeline manifest file (default: `pipeline.yaml`)
- **`-o, --output`**: Output format: TEXT (default) or JSON
- **`--help`**: Show command help

#### Examples

```bash
# Run Airflow version command
smus-cli run -w my_dag -c version

# Run DAG list command on specific target
smus-cli run -w my_dag -c "dags list" -t prod

# Run with JSON output
smus-cli run -w my_dag -c version -o JSON
```

### 6. delete - Delete Target Environments

Deletes DataZone projects and associated resources for specified targets.

```bash
smus-cli delete [OPTIONS]
```

#### Options
- **`-p, --pipeline`**: Path to pipeline manifest file (default: `pipeline.yaml`)
- **`-t, --targets`**: Target name(s) - single target or comma-separated list (required)
- **`-f, --force`**: Skip confirmation prompt
- **`--async`**: Don't wait for deletion to complete
- **`-o, --output`**: Output format: TEXT (default) or JSON
- **`--help`**: Show command help

#### Examples

```bash
# Delete single target with confirmation
smus-cli delete -t test

# Delete multiple targets without confirmation
smus-cli delete -t test,prod --force

# Delete asynchronously (don't wait for completion)
smus-cli delete -t test --force --async

# Delete with JSON output
smus-cli delete -t test --force -o JSON
```

#### Behavior
- **Confirmation Required**: By default, prompts for confirmation before deletion
- **Force Mode**: `--force` skips confirmation and deletes immediately
- **Async Mode**: `--async` returns immediately without waiting for completion
- **Error Handling**: Properly handles AWS errors (e.g., projects with MetaDataForms)
- **Resource Cleanup**: Deletes DataZone projects and associated CloudFormation stacks

#### Notes
- Some DataZone projects cannot be deleted if they contain MetaDataForms
- CloudFormation stacks are deleted automatically when projects are removed
- Use `--async` for faster execution when managing multiple targets

## Global Options

All commands support:
- **`--help`**: Show command help

## Exit Codes

- **0**: Success
- **1**: Error (check error message for details)

## Configuration Files

### Pipeline Manifest
- Default location: `pipeline.yaml` (current directory)
- Override with `--pipeline` option
- See [Pipeline Manifest Reference](pipeline-manifest.md) for format
- **Error handling**: CLI will error if the default file doesn't exist and no alternative is specified

### AWS Configuration
- Uses standard AWS credential chain
- Supports AWS profiles and environment variables
- Region can be specified in pipeline manifest or AWS config

## Common Workflows

### Development Workflow
```bash
# 1. Create new pipeline
smus-cli create -o my-pipeline.yaml

# 2. Validate configuration
smus-cli describe -p my-pipeline.yaml

# 3. Create bundle from dev
smus-cli bundle -p my-pipeline.yaml -t dev

# 4. Deploy to test
smus-cli deploy -p my-pipeline.yaml -t test

# 5. Monitor deployment
smus-cli monitor -p my-pipeline.yaml -t test

# 6. Run workflow commands
smus-cli run -w my_dag -c "dags list" -t test
```

### Cleanup Workflow
```bash
# Delete test environment
smus-cli delete -t test --force

# Delete multiple environments
smus-cli delete -t test,staging --force --async
```
