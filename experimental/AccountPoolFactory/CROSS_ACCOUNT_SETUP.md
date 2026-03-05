# Cross-Account Role Setup - Quick Reference

## Current Status
- ✅ Lambda code deployed with cross-account role support
- ✅ Infrastructure deployed in Domain account (994753223772)
- ⏳ Cross-account role needs deployment in Org Admin account (495869084367)

## Steps to Complete

### Step 1: Deploy Cross-Account Role (Org Admin Account)

**Switch to Org Admin account credentials:**
```bash
# Option 1: Using AWS CLI profiles
export AWS_PROFILE=org-admin

# Option 2: Using Isengard or other credential manager
# Follow your organization's process to assume role in account 495869084367

# Verify you're in the correct account
aws sts get-caller-identity
# Should show Account: 495869084367
```

**Deploy the role:**
```bash
cd experimental/AccountPoolFactory
./deploy-org-admin-role.sh
```

**Expected output:**
```
🚀 Deploying Account Creation Role in Org Admin Account
========================================================
Org Admin Account: 495869084367
Domain Account: 994753223772
Region: us-east-2

✅ Running in correct account

📦 Deploying cross-account role...
Successfully created/updated stack - AccountPoolFactory-AccountCreationRole

✅ Role deployed successfully

📊 Role Details:
  Role ARN: arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation
  External ID: AccountPoolFactory-994753223772

📄 Role details saved to: org-admin-role-details.json
```

**Save these values:**
- Role ARN: `arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation`
- External ID: `AccountPoolFactory-994753223772`

### Step 2: Configure Domain Account (Switch Back)

**Switch back to Domain account:**
```bash
export AWS_PROFILE=domain-account
# or use your credential manager

# Verify you're in the correct account
aws sts get-caller-identity
# Should show Account: 994753223772
```

**Add SSM parameters:**
```bash
cd experimental/AccountPoolFactory

# Add role ARN
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/OrgAdminRoleArn \
  --value 'arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation' \
  --type String \
  --region us-east-2

# Add external ID
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/ExternalId \
  --value 'AccountPoolFactory-994753223772' \
  --type String \
  --region us-east-2
```

**Verify parameters:**
```bash
aws ssm get-parameters \
  --names /AccountPoolFactory/PoolManager/OrgAdminRoleArn /AccountPoolFactory/PoolManager/ExternalId \
  --region us-east-2
```

### Step 3: Test Pool Seeding

**Trigger pool replenishment:**
```bash
./seed-initial-pool.sh
```

**Monitor Pool Manager logs:**
```bash
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
```

**Expected log output:**
```
📥 Received event: {"action": "force_replenishment"}
✅ Configuration loaded
🔐 Assuming cross-account role: arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation
✅ Successfully assumed role in Org Admin account
🔄 Force replenishment triggered
📊 Checking pool size...
📈 Pool status: 0 available, 0 setting up, 0 failed
🚀 Triggering replenishment: creating 3 accounts
📧 Creating account 1/3: DataZone-Pool-TIMESTAMP-0
✅ Account creation initiated: request_id=car-xxxxx
✅ Account created successfully: 123456789012
✅ Moved account to OU ou-n5om-otvkrtx2
✅ Created DynamoDB record for account 123456789012
✅ Invoked Setup Orchestrator for account 123456789012
```

**Monitor Setup Orchestrator logs:**
```bash
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
```

**Check DynamoDB for account states:**
```bash
aws dynamodb scan \
  --table-name AccountPoolFactory-AccountState \
  --region us-east-2 \
  --query 'Items[*].[accountId.S, state.S, accountName.S]' \
  --output table
```

## Troubleshooting

### Issue: "AccessDenied" when creating accounts
**Cause**: Cross-account role not deployed or SSM parameters not configured
**Solution**: Complete Steps 1 and 2 above

### Issue: "Could not assume role"
**Cause**: Trust policy or External ID mismatch
**Solution**: 
1. Verify role exists in Org Admin account
2. Check trust policy allows Domain account Lambda role
3. Verify External ID matches in both role and SSM parameter

### Issue: Accounts created but stuck in SETTING_UP
**Cause**: Setup Orchestrator encountering errors
**Solution**: Check Setup Orchestrator logs for specific errors

## Quick Commands Reference

```bash
# Check current account
aws sts get-caller-identity

# View Pool Manager logs
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2

# View Setup Orchestrator logs
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2

# Check pool status
aws dynamodb scan --table-name AccountPoolFactory-AccountState --region us-east-2

# Trigger replenishment manually
./seed-initial-pool.sh

# Check SSM parameters
aws ssm get-parameters-by-path --path /AccountPoolFactory/ --recursive --region us-east-2
```

## Next Steps After Successful Pool Seeding

1. Wait for accounts to reach AVAILABLE state (6-8 minutes)
2. Create a test DataZone project
3. Verify account assignment from pool
4. Monitor pool replenishment
5. Test project deletion and account reclamation
