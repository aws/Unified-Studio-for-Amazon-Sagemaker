# Cleanup Scripts

This directory contains cleanup scripts for removing Account Pool Factory resources.

## ⚠️ Warning

Cleanup scripts will **delete resources and data**. Use with caution, especially in production environments.

## Cleanup Order

### Complete Cleanup (All Resources)

To remove all Account Pool Factory resources:

```bash
# Run from project root
./scripts/cleanup/cleanup-all.sh
```

This script will:
1. Clean up Domain account resources
2. Clean up Organization Management account resources
3. Optionally clean up project accounts

### Selective Cleanup

#### Domain Account Only

```bash
# Ensure you're authenticated to the Domain account
aws sts get-caller-identity

# Clean up Domain account resources
./scripts/cleanup/02-domain-account/cleanup-domain-account.sh
```

Removes:
- Lambda functions
- DynamoDB table (⚠️ data loss)
- SNS topic
- EventBridge bus
- SSM parameters
- CloudWatch dashboards

#### Organization Management Account Only

```bash
# Ensure you're authenticated to the Organization Management account
aws sts get-caller-identity

# Manually delete stacks
aws cloudformation delete-stack --stack-name AccountPoolFactory-StackSetRoles --region us-east-2
aws cloudformation delete-stack --stack-name AccountPoolFactory-AccountCreationRole --region us-east-2

# Delete StackSet (requires removing all instances first)
aws cloudformation delete-stack-set --stack-set-name AccountPoolFactory-TrustPolicy --region us-east-2
```

## Utility Cleanup Scripts

### Clean Up Failed Accounts

Remove accounts that failed setup:

```bash
./scripts/utils/cleanup-failed-accounts.sh
```

This script:
- Queries DynamoDB for FAILED accounts
- Closes accounts via Organizations API
- Removes DynamoDB records

### Clean Up Accounts (Retain Infrastructure)

Remove project accounts but keep infrastructure:

```bash
./scripts/utils/cleanup-retain-accounts.sh
```

Useful for:
- Resetting test environment
- Removing old accounts while keeping infrastructure

## Test Environment Cleanup

For test environments only:

```bash
./tests/cleanup/cleanup-test-accounts.sh
```

This removes:
- All test accounts
- Test OUs
- Test domain resources

## What Gets Deleted

### Domain Account Cleanup
- ✅ Lambda functions (code and configuration)
- ✅ DynamoDB table (⚠️ all account state data)
- ✅ SNS topic and subscriptions
- ✅ EventBridge bus and rules
- ✅ SSM parameters
- ✅ CloudWatch dashboards and alarms
- ✅ IAM roles created by infrastructure stack

### Organization Management Account Cleanup
- ✅ StackSet Administration Role
- ✅ StackSet Management Role
- ✅ Account Creation Role
- ✅ Trust Policy StackSet
- ✅ StackSet instances in project accounts

### Project Account Cleanup
- ✅ VPC and networking resources
- ✅ IAM roles
- ✅ EventBridge rules
- ✅ S3 buckets (⚠️ data loss)
- ✅ DataZone blueprint configurations
- ⚠️ Account closure (if DELETE strategy)

## Data Loss Warning

The following operations cause **permanent data loss**:

1. **DynamoDB table deletion**: All account state history lost
2. **S3 bucket deletion**: All blueprint artifacts lost
3. **Account closure**: Cannot be undone (30-day quota limit)

## Recovery

If you accidentally delete resources:

1. **Infrastructure**: Redeploy using deployment scripts
2. **DynamoDB data**: Cannot be recovered (enable point-in-time recovery before cleanup)
3. **Closed accounts**: Cannot be reopened (create new accounts)

## Best Practices

1. **Backup first**: Export DynamoDB data before cleanup
   ```bash
   aws dynamodb scan --table-name AccountPoolFactory-AccountState > backup.json
   ```

2. **Test in non-production**: Always test cleanup scripts in test environment first

3. **Verify account**: Double-check you're in the correct AWS account
   ```bash
   aws sts get-caller-identity
   ```

4. **Review resources**: List resources before deletion
   ```bash
   aws cloudformation list-stacks --region us-east-2
   ```

## Related Documentation

- [Deployment Scripts](../deploy/README.md)
- [User Guide](../../docs/UserGuide.md)
