# Pipeline Deployment Metrics with EventBridge

The SMUS CICD CLI emits deployment lifecycle events to Amazon EventBridge, enabling you to track pipeline deployments, build custom alerts, and automate workflows.

> **Note:** This is different from the `monitor` CLI command which tracks workflow execution status. This feature tracks pipeline deployment events.

## Quick Start

### 1. Enable Monitoring in Your Pipeline

Add to `pipeline.yaml`:

```yaml
pipelineName: MyPipeline

monitoring:
  eventbridge:
    enabled: true
    eventBusName: default
    includeMetadata: true

# ... rest of your pipeline config
```

### 2. Deploy with Monitoring

```bash
smus-cli deploy --targets prod --pipeline pipeline.yaml
```

### 3. Create EventBridge Rule

**Example: SNS Alert on Failures**

```bash
aws events put-rule \
  --name smus-prod-failures \
  --event-pattern '{
    "source": ["com.amazon.smus.cicd"],
    "detail-type": ["SMUS-CICD-Deploy-Failed"],
    "detail": {
      "target": {"stage": ["PROD"]}
    }
  }'

aws events put-targets \
  --rule smus-prod-failures \
  --targets "Id"="1","Arn"="arn:aws:sns:us-east-1:123456789012:prod-alerts"
```

**Example: Lambda on Success**

```bash
aws events put-rule \
  --name smus-prod-success \
  --event-pattern '{
    "source": ["com.amazon.smus.cicd"],
    "detail-type": ["SMUS-CICD-Deploy-Completed"],
    "detail": {
      "pipelineName": ["MyPipeline"],
      "target": {"stage": ["PROD"]}
    }
  }'

aws events put-targets \
  --rule smus-prod-success \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:123456789012:function:post-deploy"
```

---

## Overview

During deployment, the CLI emits events at key stages:
- Deploy started/completed/failed
- Project initialization started/completed/failed
- Bundle upload started/completed/failed
- Workflow creation started/completed/failed
- Catalog assets processing started/completed/failed

## Configuration

### Pipeline Manifest

Add monitoring configuration to your `pipeline.yaml`:

```yaml
pipelineName: MyPipeline

monitoring:
  eventbridge:
    enabled: true                # Enable/disable event emission
    eventBusName: default        # Event bus name or ARN
    includeMetadata: true        # Include git, CI/CD, user metadata

targets:
  prod:
    # ... target configuration
```

### CLI Options

Override manifest configuration with CLI flags:

```bash
# Enable events
smus-cli deploy --targets prod --emit-events

# Disable events
smus-cli deploy --targets prod --no-events

# Use custom event bus
smus-cli deploy --targets prod --event-bus-name my-custom-bus
```

## Event Types

| Event Type | When Emitted |
|------------|--------------|
| `SMUS-CICD-Deploy-Started` | Deployment begins |
| `SMUS-CICD-Deploy-Completed` | Deployment succeeds |
| `SMUS-CICD-Deploy-Failed` | Deployment fails |
| `SMUS-CICD-Deploy-ProjectInitialization-Started` | Project creation starts |
| `SMUS-CICD-Deploy-ProjectInitialization-Completed` | Project created |
| `SMUS-CICD-Deploy-ProjectInitialization-Failed` | Project creation fails |
| `SMUS-CICD-Deploy-BundleUpload-Started` | Bundle upload starts |
| `SMUS-CICD-Deploy-BundleUpload-Completed` | Bundle uploaded |
| `SMUS-CICD-Deploy-BundleUpload-Failed` | Bundle upload fails |
| `SMUS-CICD-Deploy-WorkflowCreation-Started` | Workflow creation starts |
| `SMUS-CICD-Deploy-WorkflowCreation-Completed` | Workflows created |
| `SMUS-CICD-Deploy-WorkflowCreation-Failed` | Workflow creation fails |
| `SMUS-CICD-Deploy-CatalogAssets-Started` | Asset processing starts |
| `SMUS-CICD-Deploy-CatalogAssets-Completed` | Assets processed |
| `SMUS-CICD-Deploy-CatalogAssets-Failed` | Asset processing fails |

## Event Schema

All events follow this structure:

```json
{
  "version": "1.0",
  "timestamp": "2025-11-04T12:30:00Z",
  "pipelineName": "MyPipeline",
  "stage": "deploy|project-init|bundle-upload|workflow-creation|catalog-assets",
  "status": "started|completed|failed",
  "target": {
    "name": "prod",
    "stage": "PROD",
    "domain": {
      "name": "my-domain",
      "region": "us-east-1"
    },
    "project": {
      "name": "prod-project"
    }
  },
  "metadata": {
    "user": "username",
    "gitCommit": "abc123",
    "gitBranch": "main",
    "gitRepository": "https://github.com/...",
    "cicdPlatform": "github-actions",
    "runId": "12345",
    "runUrl": "https://github.com/.../actions/runs/12345"
  }
}
```

## Setup Approaches

### Approach 1: CloudFormation Template (Recommended for Production)

Deploy EventBridge infrastructure once using CloudFormation:

**Benefits:**
- Persistent event capture across all deployments
- S3 storage with lifecycle policies
- Infrastructure as code
- Easy to replicate across accounts/regions

**Resources created:**
- S3 bucket for event storage (with 90-day retention)
- EventBridge rule to capture SMUS CICD events
- IAM role for EventBridge → S3 permissions
- CloudWatch Logs group (optional)

**Deployment:**
```bash
# Create CloudFormation stack
aws cloudformation create-stack \
  --stack-name smus-cicd-monitoring \
  --template-body file://eventbridge-to-s3.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=EventPrefix,ParameterValue=smus-events/

# Or use existing bucket
aws cloudformation create-stack \
  --stack-name smus-cicd-monitoring \
  --template-body file://eventbridge-to-s3.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=BucketName,ParameterValue=my-existing-bucket \
    ParameterKey=EventPrefix,ParameterValue=smus-events/
```

**Event Pattern:**
```json
{
  "source": ["com.amazon.smus.cicd"],
  "detail-type": [{"prefix": "SMUS-CICD-"}]
}
```

**Query events in S3:**
```bash
# List events
aws s3 ls s3://smus-cicd-events-123456789012-us-east-1/smus-events/

# Download specific event
aws s3 cp s3://smus-cicd-events-123456789012-us-east-1/smus-events/2025/11/07/event.json -

# Query with Athena (create table first)
SELECT * FROM smus_events 
WHERE pipelineName = 'MyPipeline' 
  AND status = 'failed'
ORDER BY timestamp DESC
LIMIT 10;
```

---

### Approach 2: Programmatic Setup (For Testing)

Create EventBridge resources programmatically using boto3:

**Benefits:**
- Full control over resource lifecycle
- Easy cleanup between test runs
- No CloudFormation stack management
- Suitable for integration tests

**Example:**
```python
import boto3
import json

events_client = boto3.client('events')
logs_client = boto3.client('logs')

# Create log group
log_group = '/aws/events/smus-cicd-test'
logs_client.create_log_group(logGroupName=log_group)

# Add resource policy
account_id = boto3.client('sts').get_caller_identity()['Account']
policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "events.amazonaws.com"},
        "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
        "Resource": f"arn:aws:logs:us-east-1:{account_id}:log-group:{log_group}:*"
    }]
}
logs_client.put_resource_policy(
    policyName='EventBridgeToCloudWatchLogs',
    policyDocument=json.dumps(policy)
)

# Create EventBridge rule
events_client.put_rule(
    Name='smus-cicd-test-rule',
    EventPattern=json.dumps({
        "source": ["com.amazon.smus.cicd"],
        "detail-type": [{"prefix": "SMUS-CICD-"}]
    }),
    State='ENABLED'
)

# Add target
events_client.put_targets(
    Rule='smus-cicd-test-rule',
    Targets=[{
        'Id': '1',
        'Arn': f'arn:aws:logs:us-east-1:{account_id}:log-group:{log_group}'
    }]
)
```

**Cleanup:**
```python
# Remove target and delete rule
events_client.remove_targets(Rule='smus-cicd-test-rule', Ids=['1'])
events_client.delete_rule(Name='smus-cicd-test-rule')

# Delete log group
logs_client.delete_log_group(logGroupName=log_group)
```

---

## Common Event Patterns

### Pattern 1: Alert on Any Failure

```json
{
  "source": ["com.amazon.smus.cicd"],
  "detail-type": [{"suffix": "-Failed"}]
}
```

### Pattern 2: Track Specific Pipeline

```json
{
  "source": ["com.amazon.smus.cicd"],
  "detail": {
    "pipelineName": ["MyPipeline"]
  }
}
```

### Pattern 3: Production Only

```json
{
  "source": ["com.amazon.smus.cicd"],
  "detail": {
    "target": {"stage": ["PROD"]}
  }
}
```

### Pattern 4: Workflow Failures

```json
{
  "source": ["com.amazon.smus.cicd"],
  "detail-type": ["SMUS-CICD-Deploy-WorkflowCreation-Failed"]
}
```

## Integration Examples

### SNS Notification on Production Failures

```json
{
  "EventPattern": {
    "source": ["com.amazon.smus.cicd"],
    "detail-type": ["SMUS-CICD-Deploy-Failed"],
    "detail": {
      "target": {"stage": ["PROD"]}
    }
  },
  "Targets": [{
    "Arn": "arn:aws:sns:us-east-1:123456789012:prod-alerts",
    "Id": "1"
  }]
}
```

### Lambda Post-Deployment Validation

```json
{
  "EventPattern": {
    "source": ["com.amazon.smus.cicd"],
    "detail-type": ["SMUS-CICD-Deploy-Completed"],
    "detail": {
      "pipelineName": ["MyPipeline"],
      "target": {"stage": ["PROD"]}
    }
  },
  "Targets": [{
    "Arn": "arn:aws:lambda:us-east-1:123456789012:function:validate-deployment",
    "Id": "1"
  }]
}
```

### Step Functions Smoke Tests

```json
{
  "EventPattern": {
    "source": ["com.amazon.smus.cicd"],
    "detail-type": ["SMUS-CICD-Deploy-WorkflowCreation-Completed"]
  },
  "Targets": [{
    "Arn": "arn:aws:states:us-east-1:123456789012:stateMachine:smoke-tests",
    "RoleArn": "arn:aws:iam::123456789012:role/EventBridgeToStepFunctions",
    "Id": "1"
  }]
}
```

### CloudWatch Logs for All Events

```bash
# Create log group
aws logs create-log-group --log-group-name /aws/events/smus-deploy

# Create rule
aws events put-rule \
  --name smus-all-events \
  --event-pattern '{
    "source": ["com.amazon.smus.cicd"]
  }'

# Add target
aws events put-targets \
  --rule smus-all-events \
  --targets "Id"="1","Arn"="arn:aws:logs:us-east-1:123456789012:log-group:/aws/events/smus-deploy"
```

## IAM Permissions

The CLI requires `events:PutEvents` permission:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "events:PutEvents",
      "Resource": "arn:aws:events:*:*:event-bus/default"
    }
  ]
}
```

## Metadata Collection

When `includeMetadata: true`, events include:

- **User:** Current system user
- **Git Info:** Commit hash, branch, repository URL
- **CI/CD Platform:** Detected platform (GitHub Actions, GitLab CI, Jenkins, etc.)
- **Run Info:** Run ID and URL (when available)

Supported CI/CD platforms:
- GitHub Actions
- GitLab CI
- Jenkins
- CircleCI
- AWS CodeBuild
- Travis CI

## Best Practices

1. **Use specific event patterns** - Filter by pipeline name and stage to reduce noise
2. **Enable metadata** - Helps with debugging and audit trails
3. **Monitor event delivery** - Set up CloudWatch alarms for failed event deliveries
4. **Test integrations** - Use test deployments to verify event rules work correctly
5. **Secure event buses** - Use IAM policies to control who can put events

## Troubleshooting

### Events not appearing

1. Check IAM permissions for `events:PutEvents`
2. Verify event bus name is correct
3. Check EventBridge rule patterns match event structure
4. Enable CLI debug logging: `export SMUS_LOG_LEVEL=DEBUG`

### Missing metadata

1. Ensure `includeMetadata: true` in manifest
2. Check git repository is initialized
3. Verify CI/CD environment variables are set

## Example Workflows

### Slack Notifications

Use EventBridge → SNS → Lambda → Slack webhook to send deployment notifications.

### Automated Rollback

Use EventBridge → Lambda to trigger rollback on deployment failures.

### Deployment Dashboard

Use EventBridge → CloudWatch Logs → CloudWatch Insights to build deployment dashboards.

### Approval Workflows

Use EventBridge → Step Functions to implement manual approval gates for production deployments.

## Working Example

See `tests/integration/basic_pipeline/` for a complete working example that:
- Enables monitoring in pipeline manifest
- Creates EventBridge rule programmatically
- Captures events to CloudWatch Logs
- Validates event delivery in tests
