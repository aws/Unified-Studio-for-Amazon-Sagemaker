# Stage 2: Domain Creation

Creates SageMaker Unified Studio (DataZone) domain.

## What Gets Deployed

- **SageMaker Unified Studio Domain** - DataZone domain with IAM roles

## Usage

```bash
./deploy.sh [path/to/config.yaml]
```

## Prerequisites

- Stage 1 completed (VPC must exist)
- AWS Identity Center (IDC) enabled
- Admin user email configured in `config.yaml`

## Required Config

```yaml
domain:
  name: smus-integration-domain
  admin_user: admin@example.com
```

## CloudFormation Stack Created

- `sagemaker-unified-studio-domain` - SMUS domain

## Outputs

- Domain ID
- Domain ARN
- Portal URL

## Next Steps

Run Stage 3 to configure domain with blueprints and profiles.

## Skip This Stage If

You created the domain manually in the AWS console. Proceed directly to Stage 3.
