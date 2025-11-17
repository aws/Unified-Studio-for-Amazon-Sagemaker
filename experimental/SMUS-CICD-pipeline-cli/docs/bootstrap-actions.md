# Bootstrap Actions - EventBridge Integration

← [Back to Main README](../README.md)

Bootstrap actions allow you to emit custom EventBridge events during deployment to trigger downstream automation, notify external systems, or integrate with event-driven workflows.

## Overview

When you deploy your application, the SMUS CLI can automatically emit events to Amazon EventBridge. These events can trigger:
- AWS Lambda functions
- Step Functions workflows
- SNS notifications
- Custom event-driven automation

## Configuration

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

## Troubleshooting

### Event Not Appearing in EventBridge

1. **Check event bus name**: Verify the event bus exists
   ```bash
   aws events describe-event-bus --name my-event-bus
   ```

2. **Check IAM permissions**: Ensure deployment role has `events:PutEvents` permission

3. **Check CloudWatch Logs**: Look for event emission errors in deployment logs

### Variable Not Resolving

1. **Check variable syntax**: Must use `${variable.path}` format
2. **Check variable availability**: Only documented variables are available
3. **Check nesting**: Variables work in nested objects and arrays

### Event Bus Access Denied

Ensure your deployment role has permissions:
```json
{
  "Effect": "Allow",
  "Action": "events:PutEvents",
  "Resource": "arn:aws:events:*:*:event-bus/*"
}
```

## Best Practices

1. **Use descriptive event sources**: Follow reverse-DNS naming (e.g., `com.company.app`)
2. **Keep detail payloads small**: EventBridge has a 256KB limit
3. **Use custom event buses**: Separate production events from development
4. **Test with default bus first**: Easier to debug
5. **Document your events**: Maintain a registry of event types and their schemas

## Examples

See complete examples in:
- `examples/DemoMarketingBundle.yaml` - Basic event initialization
- `examples/analytic-workflow/etl/manifest.yaml` - ETL pipeline events

## Related Documentation

- [Manifest Schema](manifest-schema.md)
- [CLI Commands](cli-commands.md)
- [Amazon EventBridge Documentation](https://docs.aws.amazon.com/eventbridge/)
