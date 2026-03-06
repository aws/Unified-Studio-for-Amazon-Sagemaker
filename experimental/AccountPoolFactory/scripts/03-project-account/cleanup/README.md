# Project Account Cleanup

## Overview

Project account cleanup is handled **automatically** by the Pool Manager Lambda when accounts are reclaimed. Manual cleanup is only needed for troubleshooting or emergency situations.

## Automatic Cleanup

When a DataZone project is deleted:

1. EventBridge forwards the event to Domain account
2. Pool Manager marks the account for reclaim
3. Pool Manager either:
   - **DELETE strategy**: Closes the account via Organizations API
   - **REUSE strategy**: Cleans up resources and returns to pool

## Manual Cleanup

If you need to manually clean up a project account:

```bash
# 1. Switch to the project account
# (Use your preferred method for credential switching)

# 2. Delete CloudFormation stacks in reverse order
aws cloudformation delete-stack --stack-name AccountPoolFactory-Blueprints --region us-east-2
aws cloudformation wait stack-delete-complete --stack-name AccountPoolFactory-Blueprints --region us-east-2

aws cloudformation delete-stack --stack-name AccountPoolFactory-S3Bucket --region us-east-2
aws cloudformation wait stack-delete-complete --stack-name AccountPoolFactory-S3Bucket --region us-east-2

aws cloudformation delete-stack --stack-name AccountPoolFactory-EventBridge --region us-east-2
aws cloudformation wait stack-delete-complete --stack-name AccountPoolFactory-EventBridge --region us-east-2

aws cloudformation delete-stack --stack-name AccountPoolFactory-IAMRoles --region us-east-2
aws cloudformation wait stack-delete-complete --stack-name AccountPoolFactory-IAMRoles --region us-east-2

aws cloudformation delete-stack --stack-name AccountPoolFactory-VPC --region us-east-2
aws cloudformation wait stack-delete-complete --stack-name AccountPoolFactory-VPC --region us-east-2

# 3. Delete the DomainAccess role (deployed via StackSet)
aws cloudformation delete-stack --stack-name AccountPoolFactory-TrustPolicy --region us-east-2
aws cloudformation wait stack-delete-complete --stack-name AccountPoolFactory-TrustPolicy --region us-east-2

# 4. Delete the StackSet execution role
aws cloudformation delete-stack --stack-name SMUS-AccountPoolFactory-StackSetExecutionRole --region us-east-2
aws cloudformation wait stack-delete-complete --stack-name SMUS-AccountPoolFactory-StackSetExecutionRole --region us-east-2
```

## Cleanup Failed Accounts

Use the utility script to clean up accounts that failed during setup:

```bash
# From Domain account
./scripts/utils/cleanup-failed-accounts.sh
```

This script:
- Queries DynamoDB for accounts in FAILED state
- Attempts to delete CloudFormation stacks
- Removes DynamoDB records
- Optionally closes accounts via Organizations API

## Cleanup Test Accounts

For test accounts created during development:

```bash
# From Domain account
./tests/cleanup/cleanup-test-accounts.sh
```

This script:
- Removes all accounts from DynamoDB
- Closes accounts via Organizations API (if DELETE strategy)
- Cleans up test-specific resources

## Emergency Cleanup

If the Pool Manager is not functioning:

```bash
# 1. List all accounts in the pool
aws dynamodb scan \
  --table-name AccountPoolFactory-AccountState \
  --region us-east-2

# 2. For each account, manually clean up (see Manual Cleanup above)

# 3. Remove from DynamoDB
aws dynamodb delete-item \
  --table-name AccountPoolFactory-AccountState \
  --key '{"accountId": {"S": "ACCOUNT_ID"}}' \
  --region us-east-2
```

## Related Documentation

- `scripts/cleanup/README.md` - Overall cleanup procedures
- `scripts/utils/cleanup-failed-accounts.sh` - Utility script
- `docs/UserGuide.md` - Operational procedures
