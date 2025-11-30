# Bootstrap Actions

← [Back to Main README](../README.md)

Bootstrap actions allow you to execute automated tasks during deployment, including triggering workflows, fetching logs, and emitting custom EventBridge events to integrate with CI/CD pipelines and event-driven automation.

## Quick Reference

| Action Type | Description |
|------------|-------------|
| **workflow.create** | Create MWAA Serverless workflows from manifest |
| **workflow.run** | Trigger workflow execution |
| **workflow.logs** | Fetch workflow execution logs |
| **workflow.monitor** | Monitor workflow status |
| **project.create_environment** | Create DataZone environment |
| **project.create_connection** | Create DataZone connection |
| **quicksight.refresh_dataset** | Refresh QuickSight dataset |
| **cli.print** | Print message to console or log |
| **cli.wait** | Wait for specified duration |
| **cli.validate_deployment** | Validate deployment status |
| **cli.notify** | Send notification |

## Overview

When you deploy your application, the SMUS CLI can automatically execute bootstrap actions. These actions can:
- **Trigger workflow runs** automatically during deployment
- **Fetch workflow logs** for validation or debugging
- **Emit EventBridge events** to trigger downstream automation
- **Integrate with CI/CD pipelines** without separate workflow execution jobs

## Available Actions

### 1. Workflow Actions

#### workflow.create - Create MWAA Serverless Workflows

Create workflows from the `workflows:` section in manifest after connections are established.

**IMPORTANT:** This action must be added to all manifests with workflows. Workflow creation during deploy is deprecated.

```yaml
workflows:
  - workflowName: ml_training_workflow
    connectionName: default.workflow_serverless

stages:
  test:
    bootstrap:
      actions:
        - type: project.create_connection
          name: mlflow-server
          # ... connection config
        
        - type: workflow.create
          workflowName: ml_training_workflow  # Optional: omit to create all
        
        - type: workflow.run
          workflowName: ml_training_workflow
```

**Properties:**
- `workflowName` (optional): Specific workflow name to create. Omit to create all workflows defined in `workflows:` section.

**Use Case:** Create workflows after all required connections exist, allowing workflow definitions to reference connections like MLflow tracking servers.

**Example - Create all workflows:**
```yaml
bootstrap:
  actions:
    - type: workflow.create  # Creates all workflows from workflows: section
```

---

#### workflow.run - Trigger Workflow Execution

Automatically trigger a workflow run during deployment.

```yaml
bootstrap:
  actions:
    - type: workflow.run
      workflowName: etl_pipeline
      wait: false  # optional, default: false
      trailLogs: false  # optional, default: false
```

**Properties:**
- `workflowName` (required): Name of the workflow to trigger
- `wait` (optional): Wait for workflow completion without streaming logs (default: false)
- `trailLogs` (optional): Stream logs and wait for workflow completion (default: false)
  - Note: `trailLogs: true` implies `wait: true`
- `region` (optional): AWS region override (defaults to target's domain region)

**Use Cases:**
- **Fire and forget**: No `wait` or `trailLogs` - trigger workflow and continue deployment
- **Wait for completion**: `wait: true` - block until workflow completes, no log output
- **Monitor execution**: `trailLogs: true` - stream logs and wait for completion (recommended for CI/CD)

**Example - CI/CD with log monitoring:**
```yaml
bootstrap:
  actions:
    - type: workflow.run
      workflowName: data_processing_pipeline
      trailLogs: true
```

#### workflow.logs - Fetch Workflow Logs

Fetch logs from a workflow run for validation or debugging.

```yaml
bootstrap:
  actions:
    - type: workflow.logs
      workflowName: etl_pipeline
      lines: 100  # optional, default: 100
      runId: abc123  # optional, defaults to most recent run
```

**Properties:**
- `workflowName` (required): Name of the workflow
- `live` (optional): Stream logs continuously (default: false)
- `lines` (optional): Number of log lines to fetch (default: 100)
- `runId` (optional): Specific run ID (defaults to most recent)
- `region` (optional): AWS region override

**Use Case:** Validate workflow execution after deployment or debug issues.

#### workflow.monitor - Monitor Workflow Status

Get workflow status and recent run history.

```yaml
bootstrap:
  actions:
    - type: workflow.monitor
      workflowName: etl_pipeline
```

**Properties:**
- `workflowName` (required): Name of the workflow
- `region` (optional): AWS region override

**Returns:**
- `workflow_name`: Full workflow name
- `workflow_arn`: Workflow ARN
- `recent_runs`: List of last 5 workflow runs with status

**Use Case:** Check workflow health and recent execution history after deployment.

### 2. QuickSight Actions

#### quicksight.refresh_dataset - Trigger Dataset Ingestion

Trigger QuickSight dataset ingestion to refresh dashboard data after deployment.

```yaml
bootstrap:
  actions:
    # Default: Refresh datasets imported by deploy command
    - type: quicksight.refresh_dataset
      refreshScope: IMPORTED  # default
      ingestionType: FULL_REFRESH  # default
      wait: false
```

**Properties:**
- `refreshScope` (optional): Scope of datasets to refresh (default: IMPORTED)
  - `IMPORTED`: Refresh only datasets imported during QuickSight dashboard deployment (default)
  - `ALL`: Refresh all datasets in the AWS account
  - `SPECIFIC`: Refresh specific datasets (requires datasetIds)
- `datasetIds` (required if refreshScope=SPECIFIC): List of dataset IDs to refresh
- `ingestionType` (optional): Type of refresh (default: FULL_REFRESH)
  - `FULL_REFRESH`: Full data refresh
  - `INCREMENTAL_REFRESH`: Incremental refresh (if supported by dataset)
- `wait` (optional): Whether to wait for ingestion to complete (default: false)
- `timeout` (optional): Maximum seconds to wait if wait=true (default: 300)
- `region` (optional): AWS region override (defaults to target's domain region)

**Note:** Uses the current AWS account from the deployment session.

**Returns:**
- `refresh_scope`: Scope used (IMPORTED, ALL, or SPECIFIC)
- `ingestion_type`: Type of ingestion performed
- `datasets_refreshed`: Number of successfully refreshed datasets
- `total_datasets`: Total number of datasets attempted
- `results`: List of ingestion results for each dataset

**Use Case:** Automatically refresh QuickSight dashboards after deploying new data pipelines or ETL workflows.

**Examples:**

```yaml
# Example 1: Refresh imported datasets (default)
bootstrap:
  actions:
    - type: workflow.run
      workflowName: etl_pipeline
      wait: true
    
    - type: quicksight.refresh_dataset
      # refreshScope: IMPORTED is default
      wait: true

# Example 2: Refresh specific datasets
bootstrap:
  actions:
    - type: quicksight.refresh_dataset
      refreshScope: SPECIFIC
      datasetIds:
        - sales-dashboard-dataset
        - inventory-dataset
      ingestionType: FULL_REFRESH
      wait: true
      timeout: 600

# Example 3: Refresh all datasets in account
bootstrap:
  actions:
    - type: quicksight.refresh_dataset
      refreshScope: ALL
      ingestionType: INCREMENTAL_REFRESH
      wait: false

# Example 4: Complete ETL + Dashboard refresh workflow
bootstrap:
  actions:
    # Step 1: Run ETL workflow
    - type: workflow.run
      workflowName: data_processing_dag
      wait: true
    
    # Step 2: Refresh imported QuickSight datasets
    - type: quicksight.refresh_dataset
      refreshScope: IMPORTED
      ingestionType: FULL_REFRESH
      wait: true
      timeout: 600
    
    # Step 3: Verify workflow logs
    - type: workflow.logs
      workflowName: data_processing_dag
      lines: 50
```

### 3. EventBridge Actions

#### custom.put_events - Emit Custom Events

Events are configured in the `bootstrap.actions` section of your manifest:

```yaml
applicationName: my-app

bootstrap:
  actions:
    - type: eventbridge.put_events
      eventSource: com.mycompany.myapp
      eventDetailType: ApplicationDeployed
      eventBusName: default  # Optional, defaults to "default"
      detail:
        deployedBy: ${application.name}
        environment: ${stage}
        projectName: ${project.name}
        region: ${domain.region}
      resources:  # Optional
        - arn:aws:s3:::my-bucket

stages:
  dev:
    domain:
      region: us-east-1
    project:
      name: dev-project
```

## Event Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Must be `"eventbridge.put_events"` |
| `eventSource` | string | Event source identifier (e.g., `com.mycompany.myapp`) |
| `eventDetailType` | string | Event detail type (e.g., `ApplicationDeployed`) |

### Optional Fields

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `eventBusName` | string | EventBridge event bus name or ARN | `"default"` |
| `detail` | object | Event detail payload with variable support | `{}` |
| `resources` | array | List of resource ARNs related to the event | `[]` |

## Variable Resolution

Event details support variable substitution using `${variable.path}` syntax:

### Available Variables

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `${application.name}` | Application name from manifest | `my-app` |
| `${stage}` | Target stage name | `dev`, `test`, `prod` |
| `${project.name}` | DataZone project name | `dev-project` |
| `${domain.name}` | DataZone domain name | `my-domain` |
| `${domain.region}` | AWS region | `us-east-1` |

### Variable Examples

```yaml
bootstrap:
  actions:
    - type: eventbridge.put_events
      eventSource: com.example.app
      eventDetailType: DeploymentCompleted
      detail:
        # Simple variable
        appName: ${application.name}
        
        # Nested object
        metadata:
          environment: ${stage}
          project: ${project.name}
          region: ${domain.region}
        
        # Array with variables
        tags:
          - app:${application.name}
          - stage:${stage}
        
        # Mixed content
        message: "Deployed ${application.name} to ${stage}"
```

## Use Cases

### 1. Trigger Post-Deployment Validation

```yaml
bootstrap:
  actions:
    - type: eventbridge.put_events
      eventSource: com.mycompany.cicd
      eventDetailType: DeploymentCompleted
      detail:
        application: ${application.name}
        stage: ${stage}
        validationRequired: true
```

**EventBridge Rule:**
```json
{
  "source": ["com.mycompany.cicd"],
  "detail-type": ["DeploymentCompleted"],
  "detail": {
    "validationRequired": [true]
  }
}
```

### 2. Notify External Systems

```yaml
bootstrap:
  actions:
    - type: eventbridge.put_events
      eventSource: com.mycompany.notifications
      eventDetailType: ApplicationDeployed
      detail:
        app: ${application.name}
        environment: ${stage}
        timestamp: "{{timestamp}}"
        deployedBy: "CICD Pipeline"
```

### 3. Custom Event Bus

```yaml
bootstrap:
  actions:
    - type: eventbridge.put_events
      eventSource: com.mycompany.app
      eventDetailType: ProductionDeployment
      eventBusName: arn:aws:events:us-east-1:123456789012:event-bus/production-events
      detail:
        application: ${application.name}
        region: ${domain.region}
```

### 4. Multiple Events

```yaml
bootstrap:
  actions:
    # Notify deployment started
    - type: eventbridge.put_events
      eventSource: com.mycompany.cicd
      eventDetailType: DeploymentStarted
      detail:
        application: ${application.name}
        stage: ${stage}
    
    # Trigger data refresh
    - type: eventbridge.put_events
      eventSource: com.mycompany.data
      eventDetailType: RefreshRequired
      detail:
        project: ${project.name}
        region: ${domain.region}
```

## Event Processing

Events are processed **sequentially** during the bootstrap phase before bundle deployment:

1. Project creation/validation completes
2. **Bootstrap actions execute** (events emitted here)
3. Bundle deployment begins
4. Workflows created

### Execution Flow

```
Deploy Command
├── Create/Validate Project
├── Execute Bootstrap Actions  ← Events emitted here
│   ├── Event 1: Emitted
│   ├── Event 2: Emitted
│   └── Event 3: Emitted
├── Deploy Bundle
└── Create Workflows
```

## Error Handling

- Event emission failures are **logged but don't fail the deployment**
- Each event is processed independently
- Failed events are reported in the deployment summary

Example output:
```
Processing bootstrap actions...
  ✓ Processed 2 actions successfully
  ✗ 1 actions failed
```

## EventBridge Event Structure

Events emitted by SMUS CLI follow this structure:

```json
{
  "version": "0",
  "id": "event-id",
  "detail-type": "ApplicationDeployed",
  "source": "com.mycompany.myapp",
  "account": "123456789012",
  "time": "2025-01-16T12:00:00Z",
  "region": "us-east-1",
  "resources": [
    "arn:aws:s3:::my-bucket"
  ],
  "detail": {
    "deployedBy": "my-app",
    "environment": "dev",
    "projectName": "dev-project",
    "region": "us-east-1"
  }
}
```

## Examples

See complete examples in:
- `examples/DemoMarketingBundle.yaml` - Basic event initialization
- `examples/analytic-workflow/etl/manifest.yaml` - ETL pipeline events

## Related Documentation

- [Manifest Schema](manifest-schema.md)
- [CLI Commands](cli-commands.md)
- [Amazon EventBridge Documentation](https://docs.aws.amazon.com/eventbridge/)
