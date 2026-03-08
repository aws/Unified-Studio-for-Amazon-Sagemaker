# Project Account Deployment

## Overview

Project account resources are deployed **automatically** via the Setup Orchestrator Lambda function. There are no manual deployment scripts for project accounts.

## Deployment Process

When a new account is created by the Pool Manager:

1. **Wave 0**: StackSet deploys the `SMUS-AccountPoolFactory-DomainAccess` role (automatic)
2. **Wave 1**: Setup Orchestrator deploys VPC stack
3. **Wave 2**: Setup Orchestrator deploys IAM roles and EventBridge rules (parallel)
4. **Wave 3**: Setup Orchestrator creates S3 bucket and RAM share (parallel)
5. **Wave 4**: Setup Orchestrator enables blueprints
6. **Wave 5**: Setup Orchestrator creates policy grants
7. **Wave 6**: Setup Orchestrator verifies domain visibility

## CloudFormation Templates

Templates are located in `templates/cloudformation/03-project-account/project-account/deploy/`:

- `01-stackset-execution-role.yaml` - Deployed via StackSet from Org Admin account
- `02-vpc-setup.yaml` - VPC with 3 private subnets
- `03-iam-roles.yaml` - DataZone ManageAccessRole and ProvisioningRole
- `04-eventbridge-rules.yaml` - Forward events to Domain account
- `05-s3-bucket.yaml` - S3 bucket for DataZone projects
- `06-blueprint-enablement.yaml` - Enable DataZone blueprints

## Monitoring

Monitor deployment progress:

```bash
# Check account state in DynamoDB
aws dynamodb get-item \
  --table-name AccountPoolFactory-AccountState \
  --key '{"accountId": {"S": "ACCOUNT_ID"}}' \
  --region us-east-2

# Check Setup Orchestrator logs
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
```

## Troubleshooting

If an account fails during setup:

1. Check CloudWatch Logs for Setup Orchestrator
2. Check CloudFormation stacks in the project account
3. Review DynamoDB record for error details
4. Use `scripts/utils/cleanup-failed-accounts.sh` to clean up and retry

## Manual Intervention

In rare cases, you may need to manually deploy to a project account:

```bash
# Assume the DomainAccess role
aws sts assume-role \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/SMUS-AccountPoolFactory-DomainAccess \
  --role-session-name manual-deploy \
  --external-id <DOMAIN_ID_FROM_CONFIG>

# Deploy a specific stack
aws cloudformation deploy \
  --template-file templates/cloudformation/03-project-account/project-account/deploy/02-vpc-setup.yaml \
  --stack-name AccountPoolFactory-VPC \
  --region us-east-2
```

## Related Documentation

- `docs/Architecture.md` - System architecture
- `docs/UserGuide.md` - Operational procedures
- `IMPLEMENTATION_STATUS.md` - Current deployment status
