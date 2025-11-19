# Stage 3: Domain Configuration

Configures SMUS domain with environment blueprints and project profiles.

## What Gets Deployed

- **Environment Blueprints** - LakehouseCatalog, Bedrock Guardrail, etc.
- **Project Profiles** - Configuration for project environments

## Usage

```bash
./deploy.sh [path/to/config.yaml]
```

## Prerequisites

- Domain exists (from Stage 2 or manual creation)
- Domain ID available in config or CloudFormation outputs

## CloudFormation Stack Created

- `blueprints-profiles` - Environment blueprints and profiles

## Enabled Blueprints

- LakehouseCatalog
- AmazonBedrockGuardrail
- AmazonSageMakerStudio
- AmazonEMRServerless
- AmazonAthena
- AmazonRedshiftServerless
- AmazonManagedWorkflowsApacheAirflow

## Next Steps

Run Stage 4 to create dev project and configure memberships.

## Use Case

Run this stage even if domain was created manually to enable all required blueprints.
