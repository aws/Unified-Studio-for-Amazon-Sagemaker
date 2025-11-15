# Stage 1: Account Minimal Setup

Deploys minimal account-level resources required for SMUS integration testing.

**📚 User documentation:** [Admin Quick Start - CI/CD Authentication](../../../../docs/getting-started/admin-quickstart.md#step-8-set-up-cicd-authentication-optional)

## What Gets Deployed

1. **GitHub OIDC Integration** - IAM role for GitHub Actions workflows
2. **VPC Infrastructure** - Multi-AZ VPC with private subnets for SageMaker Unified Studio

## Usage

```bash
./deploy.sh [path/to/config.yaml]
```

If no config file is specified, uses `../../config.yaml`.

## Prerequisites

- AWS CLI configured with admin permissions
- `yq` installed: `brew install yq`
- Valid `config.yaml` with account_id and regions

## Outputs

Saved to `/tmp/`:
- `vpc_id_<region>.txt` - VPC ID
- `subnets_<region>.txt` - Private subnet IDs (comma-separated)
- `azs_<region>.txt` - Availability zones (comma-separated)

## CloudFormation Stacks Created

- `smus-cli-github-integration` - GitHub OIDC role
- `sagemaker-unified-studio-vpc` - VPC infrastructure (per region)

## Next Steps

After Stage 1 completes:
- **Option A:** Run Stage 2 to create domain via CloudFormation
- **Option B:** Create domain manually in AWS console, then run Stage 3

## Idempotency

- VPC deployment checks for existing VPCs with tag `CreatedForUseWithSageMakerUnifiedStudio=true`
- Reuses existing VPCs if found
- Safe to re-run
