# Manual Testing Steps - Complete the Deployment

## Overview
The Lambda code has been deployed with cross-account role support. You need to:
1. Deploy the cross-account role in Org Admin account
2. Configure SSM parameters in Domain account
3. Test pool seeding

## Prerequisites
- Access to both Org Admin account (495869084367) and Domain account (994753223772)
- AWS CLI configured
- Ability to switch between accounts (Isengard, AWS profiles, etc.)

---

## Part 1: Deploy Cross-Account Role (5 minutes)

### Switch to Org Admin Account (495869084367)

```bash
# Use your preferred method to switch accounts
# Example with AWS CLI profiles:
export AWS_PROFILE=org-admin

# Or use Isengard/credential manager for account 495869084367

# Verify you're in the correct account
aws sts get-caller-identity
```

**Expected output:**
```json
{
    "Account": "495869084367",
    ...
}
```

### Deploy the Cross-Account Role

```bash
cd experimental/AccountPoolFactory
./deploy-org-admin-role.sh
```

**What this does:**
- Creates IAM role: `AccountPoolFactory-AccountCreation`
- Configures trust policy with External ID
- Grants least-privilege Organizations API permissions
- Saves role details to `org-admin-role-details.json`

**Expected output:**
```
🚀 Deploying Account Creation Role in Org Admin Account
========================================================
Org Admin Account: 495869084367
Domain Account: 994753223772
Region: us-east-2

✅ Running in correct account

📦 Deploying cross-account role...
Waiting for changeset to be created..
Waiting for stack create/update to complete
Successfully created/updated stack - AccountPoolFactory-AccountCreationRole

✅ Role deployed successfully

📊 Role Details:
  Role ARN: arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation
  External ID: AccountPoolFactory-994753223772

📄 Role details saved to: org-admin-role-details.json

✅ Deployment complete!
```

**Copy these values** (you'll need them in Part 2):
- Role ARN: `arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation`
- External ID: `AccountPoolFactory-994753223772`

---

## Part 2: Configure Domain Account (5 minutes)

### Switch to Domain Account (994753223772)

```bash
# Switch back to Domain account
export AWS_PROFILE=domain-account
# Or use your credential manager for account 994753223772

# Verify you're in the correct account
aws sts get-caller-identity
```

**Expected output:**
```json
{
    "Account": "994753223772",
    ...
}
```

### Add SSM Parameters

```bash
cd experimental/AccountPoolFactory

# Add the cross-account role ARN
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/OrgAdminRoleArn \
  --value 'arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation' \
  --type String \
  --region us-east-2

# Add the external ID
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/ExternalId \
  --value 'AccountPoolFactory-994753223772' \
  --type String \
  --region us-east-2
```

**Expected output for each command:**
```json
{
    "Version": 1,
    "Tier": "Standard"
}
```

### Verify Configuration

```bash
aws ssm get-parameters \
  --names /AccountPoolFactory/PoolManager/OrgAdminRoleArn /AccountPoolFactory/PoolManager/ExternalId \
  --region us-east-2 \
  --query 'Parameters[*].[Name,Value]' \
  --output table
```

**Expected output:**
```
---------------------------------------------------------------------------
|                              GetParameters                              |
+-----------------------------------------------------+-------------------+
|  /AccountPoolFactory/PoolManager/ExternalId        |  AccountPoolFactory-994753223772  |
|  /AccountPoolFactory/PoolManager/OrgAdminRoleArn   |  arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation  |
+-----------------------------------------------------+-------------------+
```

---

## Part 3: Test Pool Seeding (10-15 minutes)

### Trigger Pool Replenishment

```bash
./seed-initial-pool.sh
```

**Expected output:**
```
🌱 Seeding initial account pool
================================
Region: us-east-2

🚀 Triggering pool replenishment...
{
    "StatusCode": 200,
    "ExecutedVersion": "$LATEST"
}

📄 Response:
{"statusCode": 200, "body": "Replenishment triggered"}

✅ Pool replenishment triggered
```

### Monitor Pool Manager Logs (Real-time)

Open a new terminal and run:
```bash
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
```

**Expected log output:**
```
📥 Received event: {"action": "force_replenishment"}
✅ Configuration loaded: {
  "EmailDomain": "example.com",
  "EmailPrefix": "accountpool",
  "MinimumPoolSize": "3",
  "TargetPoolSize": "10",
  "TargetOUId": "ou-n5om-otvkrtx2",
  "OrgAdminRoleArn": "arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation",
  "ExternalId": "AccountPoolFactory-994753223772"
}
🔐 Assuming cross-account role: arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation
✅ Successfully assumed role in Org Admin account
🔄 Force replenishment triggered
📊 Checking pool size...
📈 Pool status: 0 available, 0 setting up, 0 failed
🚀 Triggering replenishment: creating 3 accounts
📧 Creating account 1/3: DataZone-Pool-1772586390-0 (accountpool+1772586390-0@example.com)
✅ Account creation initiated: request_id=car-xxxxxxxxxxxxx
⏳ Account creation in progress... (IN_PROGRESS)
⏳ Account creation in progress... (IN_PROGRESS)
✅ Account created successfully: 123456789012
✅ Moved account 123456789012 to OU ou-n5om-otvkrtx2
✅ Created DynamoDB record for account 123456789012
✅ Invoked Setup Orchestrator for account 123456789012
📧 Creating account 2/3: DataZone-Pool-1772586390-1 (accountpool+1772586390-1@example.com)
...
```

**Key indicators of success:**
- ✅ "Successfully assumed role in Org Admin account"
- ✅ "Account created successfully"
- ✅ "Invoked Setup Orchestrator"

### Monitor Setup Orchestrator Logs

Open another terminal:
```bash
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
```

**Expected log output:**
```
📥 Received event: {"accountId": "123456789012", "requestId": "car-xxxxx", "mode": "setup"}
✅ Configuration loaded
🚀 Starting account setup for 123456789012
📊 Current state: SETTING_UP

Wave 1: VPC Deployment
  ✅ Step 1: Deploy VPC and Subnets - COMPLETE (45s)

Wave 2: IAM and EventBridge
  ✅ Step 2: Deploy IAM Roles - COMPLETE (30s)
  ✅ Step 3: Deploy EventBridge Rules - COMPLETE (25s)

Wave 3: S3 and RAM
  ✅ Step 4: Deploy S3 Bucket - COMPLETE (20s)
  ✅ Step 5: Create RAM Share - COMPLETE (35s)

Wave 4: Blueprint Enablement
  ✅ Step 6: Enable Blueprints - COMPLETE (180s)

Wave 5: Policy Grants
  ✅ Step 7: Add Policy Grants - COMPLETE (40s)

Wave 6: Domain Visibility
  ✅ Step 8: Add Domain Visibility - COMPLETE (30s)

✅ Account setup complete for 123456789012
📊 Final state: AVAILABLE
⏱️  Total time: 6m 25s
```

### Check Account States in DynamoDB

```bash
aws dynamodb scan \
  --table-name AccountPoolFactory-AccountState \
  --region us-east-2 \
  --query 'Items[*].[accountId.S, state.S, accountName.S, createdDate.S]' \
  --output table
```

**Expected output (after 6-8 minutes):**
```
----------------------------------------------------------------------------------
|                                  Scan                                          |
+----------------+-------------+---------------------------+---------------------+
|  123456789012  |  AVAILABLE  |  DataZone-Pool-1772586390-0  |  2026-03-03T...  |
|  123456789013  |  AVAILABLE  |  DataZone-Pool-1772586390-1  |  2026-03-03T...  |
|  123456789014  |  AVAILABLE  |  DataZone-Pool-1772586390-2  |  2026-03-03T...  |
+----------------+-------------+---------------------------+---------------------+
```

### Check CloudWatch Metrics

```bash
# View pool size metrics
aws cloudwatch get-metric-statistics \
  --namespace AccountPoolFactory/PoolManager \
  --metric-name AvailableAccountCount \
  --start-time $(date -u -v-10M +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Maximum \
  --region us-east-2
```

---

## Part 4: Test Project Creation (5 minutes)

### Create Test Project via DataZone Portal

1. Navigate to DataZone portal: https://dzd-5o0lje5xgpeuw9.sagemaker.us-east-2.on.aws
2. Click "Create Project"
3. Fill in project details:
   - Name: "Test-Pool-Project-1"
   - Description: "Testing account pool assignment"
   - Project Profile: "Open Project - Account Pool"
4. Click "Create"

### Monitor Account Assignment

Watch Pool Manager logs for assignment event:
```bash
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
```

**Expected log output:**
```
📥 Received event from CloudFormation
🎯 Processing assignment event for account 123456789012, stack DataZone-Test-Pool-Project-1
✅ Account 123456789012 marked as ASSIGNED
📊 Checking pool size...
📈 Pool status: 2 available, 0 setting up, 0 failed
🚀 Triggering replenishment: creating 1 accounts
```

### Verify Account State Changed

```bash
aws dynamodb query \
  --table-name AccountPoolFactory-AccountState \
  --index-name StateIndex \
  --key-condition-expression "#state = :state" \
  --expression-attribute-names '{"#state":"state"}' \
  --expression-attribute-values '{":state":{"S":"ASSIGNED"}}' \
  --region us-east-2
```

---

## Part 5: Test Project Deletion (5 minutes)

### Delete Test Project

1. In DataZone portal, navigate to the test project
2. Click "Delete Project"
3. Confirm deletion

### Monitor Account Reclamation

Watch Pool Manager logs:
```bash
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
```

**Expected log output:**
```
📥 Received DELETE_COMPLETE event
🗑️ Processing deletion event for account 123456789012
🗑️ Reclaiming account 123456789012 using DELETE strategy
✅ Account 123456789012 closure initiated
✅ Account deleted
```

### Verify Account Removed from DynamoDB

```bash
aws dynamodb scan \
  --table-name AccountPoolFactory-AccountState \
  --region us-east-2 \
  --filter-expression "accountId = :id" \
  --expression-attribute-values '{":id":{"S":"123456789012"}}' \
  --region us-east-2
```

**Expected:** No items returned (account record deleted)

---

## Success Criteria

✅ Cross-account role deployed in Org Admin account
✅ SSM parameters configured in Domain account
✅ Pool Manager successfully assumes cross-account role
✅ Accounts created via Organizations API
✅ Accounts reach AVAILABLE state (6-8 minutes)
✅ Project creation assigns account from pool
✅ Pool automatically replenishes after assignment
✅ Project deletion reclaims and closes account

---

## Troubleshooting

### Issue: "Could not assume role"
**Check:**
```bash
# Verify role exists
aws iam get-role --role-name AccountPoolFactory-AccountCreation --profile org-admin

# Verify SSM parameters
aws ssm get-parameters \
  --names /AccountPoolFactory/PoolManager/OrgAdminRoleArn /AccountPoolFactory/PoolManager/ExternalId \
  --region us-east-2
```

### Issue: Accounts stuck in SETTING_UP
**Check Setup Orchestrator logs:**
```bash
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
```

### Issue: No accounts created
**Check Pool Manager logs for errors:**
```bash
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
```

---

## Next Steps After Successful Testing

1. Update TESTING_PROGRESS.md with actual results
2. Subscribe to SNS alerts
3. Configure CloudWatch alarms
4. Test failure scenarios
5. Document any issues encountered
6. Update UserGuide with production recommendations
