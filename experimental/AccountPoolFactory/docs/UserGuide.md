# Account Pool Factory - User Guide

## Overview

The Account Pool Factory automates AWS account provisioning for Amazon DataZone projects. It maintains a shadow pool of pre-configured accounts that are automatically assigned to projects on demand - one dedicated account per project. The system uses event-driven replenishment to ensure accounts are always ready, eliminating the 10-12 minute setup delay during project creation.

## Why Use Account Pool Factory?

### Full Isolation Between Projects
Each DataZone project gets its own dedicated AWS account, providing:
- **Security isolation**: Complete separation of resources, IAM policies, and data
- **Blast radius containment**: Issues in one project cannot affect others
- **Independent governance**: Each account can have its own compliance controls

### Optimal Resource Utilization
With a dedicated account per project:
- **Full account resources**: Each project can use entire account quotas and limits
- **No resource contention**: Projects don't compete for shared account resources
- **Flexible scaling**: Each project scales independently without impacting others

### Easy Cost Attribution
Account-level isolation provides:
- **Clear cost tracking**: AWS billing automatically separates costs by account
- **Project-level budgets**: Set and monitor budgets per project/account
- **Simplified chargeback**: Direct cost attribution to business units or teams
- **Cost optimization**: Identify and optimize costs at the project level

## Architecture

```
┌─────────────────────┐
│ Organization Admin  │ - Creates accounts via Organizations API
│     Account         │ - Manages account lifecycle
└──────────┬──────────┘
           │
           │ Account Creation
           │
┌──────────▼──────────┐
│   Domain Account    │ - Hosts DataZone domain
│                     │ - Pool Manager Lambda (monitors pool size)
│                     │ - Setup Orchestrator Lambda (configures accounts)
│                     │ - Account Provider Lambda (handles DataZone requests)
│                     │ - DynamoDB (tracks account states)
│                     │ - CloudWatch Dashboards (monitoring)
└──────────┬──────────┘
           │
           │ Account Assignment
           │
┌──────────▼──────────┐
│  Project Account    │ - Hosts DataZone project environments
│                     │ - Pre-configured with IAM roles, VPC, blueprints
│                     │ - EventBridge rules forward events to Domain account
└─────────────────────┘
```

### How It Works

1. **Shadow Pool**: Pool Manager maintains 5-10 pre-configured accounts in AVAILABLE state
2. **Event-Driven Replenishment**: When projects are created, CloudFormation events trigger automatic pool replenishment
3. **Parallel Setup**: Multiple accounts are created and configured simultaneously (10-12 minutes per account)
4. **Fast Project Creation**: Projects get accounts instantly from the pool (no waiting for setup)
5. **Automatic Cleanup**: When projects are deleted, accounts are automatically closed to minimize costs

## Three Personas

### 1. Organization Administrator
Manages the AWS Organization and account creation infrastructure.

**Account**: Organization Admin Account (where AWS Organizations is configured)

**Responsibilities**:
- Deploy account creation infrastructure
- Approve CloudFormation StackSets for project accounts
- Monitor organization account limits

**Note**: The system uses Organizations API for fast account creation (< 1 minute). Control Tower is not required.

### 2. Domain Administrator
Manages the DataZone domain and automated account pool.

**Account**: Domain Account (where DataZone domain is hosted)

**Responsibilities**:
- Deploy Pool Manager and Setup Orchestrator Lambdas
- Deploy Account Provider Lambda for DataZone integration
- Configure pool settings (minimum size, target size, reclaim strategy)
- Monitor pool health via CloudWatch dashboards
- Respond to alerts for failed accounts or low pool size
- Review daily/weekly statistics

**Monitoring Tools**:
- **CloudWatch Dashboards**: 4 dashboards showing pool status, account inventory, failures, and org limits
- **SNS Alerts**: Notifications for failures, pool depletion, and account limit warnings
- **DynamoDB Query API**: Programmatic access to account inventory

### 3. Project Creator
Creates DataZone projects and environments.

**Account**: Domain Account (via DataZone portal)

**Responsibilities**:
- Create projects using account pool-enabled profiles
- Create environments based on project profile configuration (ON_CREATE or ON_DEMAND)

**Note**: Account assignment is automatic. When you create a project with an account pool-enabled profile, the system automatically assigns a dedicated account from the pool. You don't need to select or choose accounts - each project gets its own isolated AWS account.

## Prerequisites

Before deploying the Account Pool Factory, ensure you have:

### Organization Administrator Account
- AWS Organization already created and configured
- At least one Organizational Unit (OU) for project accounts
- IAM permissions to create roles, EventBridge rules, and SSM parameters
- Service quota for AWS accounts (default: 10, can be increased)

### Domain Administrator Account  
- DataZone domain already created and accessible
- IAM permissions to create Lambda functions, DynamoDB tables, RAM shares, and CloudWatch dashboards
- Access to domain ID, domain ARN, and root domain unit ID

### General Requirements
- AWS CLI installed and configured
- Python 3.12+ installed
- Git repository cloned locally
- Email domain for account creation (e.g., example.com)

## Configuration

1. Copy the configuration template:
   ```bash
   cd experimental/AccountPoolFactory
   cp config.yaml.template config.yaml
   ```

2. Edit `config.yaml` with your values:
   ```yaml
   aws:
     region: us-east-2                    # Your AWS region
     account_id: "495869084367"           # Org Admin account ID
     domain_account_id: "994753223772"    # Domain account ID
   
   datazone:
     domain_id: dzd-4igt64u5j25ko9        # Your existing DataZone domain ID
     domain_arn: arn:aws:datazone:...     # Your domain ARN
     root_domain_unit_id: 6kg8zlq8mvid9l  # Root domain unit ID
   
   account_pool:
     minimum_pool_size: 5                 # Minimum accounts to maintain
     maximum_pool_size: 10                # Target pool size
     replenishment_threshold: 5           # Trigger replenishment below this
     email_prefix: accountpool            # Email prefix for accounts
     email_domain: example.com            # Email domain for accounts
     name_prefix: DataZone-Pool           # Account name prefix
   
   organization:
     target_ou_name: ProjectAccounts      # Existing OU for project accounts
   ```

3. Configure AWS credentials:
   ```bash
   aws configure
   # OR
   export AWS_ACCESS_KEY_ID=...
   export AWS_SECRET_ACCESS_KEY=...
   ```

## Deployment by Persona

### Organization Administrator Deployment

**Prerequisites**: 
- AWS Organization already exists
- Target OU for project accounts already created
- IAM permissions for CloudFormation, IAM, EventBridge, SSM

**Step 1: Deploy Approved StackSets**

StackSets define the approved CloudFormation templates that will be deployed to project accounts during setup.

```bash
./tests/setup/scripts/deploy-approved-stacksets.sh
```

This creates three StackSets in the Org Admin account:
- **VPCSetup**: Networking infrastructure (3 private subnets across 3 AZs)
- **IAMRoles**: DataZone roles (ManageAccessRole, ProvisioningRole)
- **BlueprintEnablement**: Enables all 17 DataZone blueprints

**Note**: StackSets are created once. Instances will be deployed to project accounts automatically by the Setup Orchestrator Lambda.

**What Happens Next**: The Domain Administrator will deploy Lambda functions that use these StackSets to configure new accounts.

### Domain Administrator Deployment

**Prerequisites**:
- DataZone domain already exists
- Domain ID, ARN, and root domain unit ID available
- IAM permissions for Lambda, DynamoDB, RAM, DataZone, CloudWatch
- Organization Administrator has deployed StackSets

**Step 1: Deploy Account Pool Infrastructure**

This deploys all Lambda functions, DynamoDB tables, EventBridge bus, SNS topics, and CloudWatch dashboards in your Domain account.

```bash
./tests/setup/scripts/deploy-account-pool-infrastructure.sh
```

This creates:
- **Pool Manager Lambda**: Monitors pool size, triggers replenishment, manages account lifecycle
- **Setup Orchestrator Lambda**: Configures new accounts (8-step workflow)
- **Account Provider Lambda**: Handles DataZone account pool requests
- **DynamoDB State Table**: Tracks account states and setup progress
- **EventBridge Central Bus**: Receives events from project accounts
- **SNS Alert Topic**: Sends notifications for failures and warnings
- **SSM Parameters**: Stores configuration (pool sizes, retry settings, domain info)
- **4 CloudWatch Dashboards**: Pool overview, account inventory, failed accounts, org limits

**Step 2: Configure Pool Settings**

Review and adjust the SSM parameters created by the deployment:

```bash
# View current configuration
aws ssm get-parameters-by-path \
  --path /AccountPoolFactory/ \
  --recursive \
  --region us-east-2

# Update pool sizes if needed
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/MinimumPoolSize \
  --value "5" \
  --type String \
  --overwrite \
  --region us-east-2

aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/TargetPoolSize \
  --value "10" \
  --type String \
  --overwrite \
  --region us-east-2
```

**Step 3: Create DataZone Account Pool**

This creates the DataZone account pool with Lambda integration.

```bash
./tests/setup/scripts/create-account-pool.sh
```

This registers your Account Provider Lambda as the custom account pool handler in DataZone.

**Step 4: Seed Initial Pool**

Trigger the Pool Manager to create the initial set of accounts:

```bash
# Manually invoke Pool Manager to seed pool
aws lambda invoke \
  --function-name PoolManager \
  --payload '{"action":"force_replenishment"}' \
  --region us-east-2 \
  response.json

# Monitor progress in CloudWatch Logs
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
```

The Pool Manager will:
1. Create accounts via Organizations API (< 1 minute each)
2. Invoke Setup Orchestrator for each account
3. Setup Orchestrator configures accounts in parallel (10-12 minutes each)
4. Accounts transition to AVAILABLE state when ready

**Step 5: Create Project Profile with Account Pool**

This creates a DataZone project profile that uses the account pool.

```bash
./tests/setup/scripts/create-project-profile-with-pool.sh
```

This creates a profile with:
- Account pool integration
- Selected blueprints (configurable in config.yaml)
- Policy grants for blueprint usage

**Step 6: Monitor Pool Health**

Access the CloudWatch dashboards to monitor your account pool:

1. Navigate to CloudWatch console in Domain account
2. Select "Dashboards" from left menu
3. Open these dashboards:
   - **AccountPoolFactory-Overview**: Real-time pool status, creation rates, setup duration
   - **AccountPoolFactory-Inventory**: Account table with IDs, states, projects, dates
   - **AccountPoolFactory-FailedAccounts**: Failed account details and error breakdown
   - **AccountPoolFactory-OrgLimits**: Organization account usage and limits

You can also access these dashboards from the Org Admin account (cross-account metrics sharing is configured automatically).

**Step 7: Subscribe to Alerts**

Subscribe to the SNS topic to receive alerts:

```bash
# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-2:DOMAIN_ACCOUNT_ID:AccountPoolFactory-Alerts \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-2

# Confirm subscription via email
```

You'll receive alerts for:
- Account setup failures
- Pool depletion (no available accounts)
- Replenishment blocked (failed accounts exist)
- Organization account limit warnings (< 50 remaining)
- Organization account limit critical (< 20 remaining)

### Project Creator Usage

**Prerequisites**:
- Access to DataZone portal
- Project profile with account pool already created

**Create a Project**

**Via DataZone Portal**:
1. Navigate to DataZone portal
2. Click "Create Project"
3. Select the project profile that uses account pools
4. System automatically assigns a dedicated account from the pool
5. Project is created with its own isolated AWS account

**Via AWS CLI**:

```bash
# Step 1: Get an available account from the pool
POOL_RESPONSE=$(aws datazone list-accounts-in-account-pool \
  --domain-identifier YOUR_DOMAIN_ID \
  --account-pool-identifier YOUR_POOL_ID \
  --region YOUR_REGION)

# Extract first available account ID and region
ACCOUNT_ID=$(echo $POOL_RESPONSE | jq -r '.accounts[0].awsAccountId')
REGION=$(echo $POOL_RESPONSE | jq -r '.accounts[0].regionName')

echo "Using account: $ACCOUNT_ID in region: $REGION"

# Step 2: Create project with the selected account
aws datazone create-project \
  --domain-identifier YOUR_DOMAIN_ID \
  --name "My Project" \
  --user-parameters '[{
    "environmentConfigurationName": "Tooling",
    "environmentResolvedAccount": {
      "awsAccountId": "'$ACCOUNT_ID'",
      "regionName": "'$REGION'",
      "sourceAccountPoolId": "YOUR_POOL_ID"
    }
  }]' \
  --region YOUR_REGION
```

**Note**: 
- This automatically selects the first available account from the pool
- Each project gets one dedicated account
- The selected account will be assigned to your project
- If your profile has multiple environment configurations with account pools, you must provide resolved accounts for all of them

**Create Environments**

Environments can be created through the DataZone portal or API based on your project profile configuration.

## Key Concepts

### Account States
- **AVAILABLE**: Ready to be assigned to projects
- **ASSIGNED**: Currently assigned to a project
- **SETTING_UP**: Being created and configured (10-12 minutes)
- **FAILED**: Setup failed after retry exhaustion
- **DELETING**: Being closed via Organizations API
- **CLEANING**: Being cleaned for reuse (REUSE strategy only)

### Account Lifecycle
1. **Creation**: Pool Manager creates account via Organizations API (< 1 minute)
2. **Setup**: Setup Orchestrator runs 8-step workflow (10-12 minutes):
   - VPC deployment (~2.5 min)
   - IAM roles deployment (~2 min)
   - S3 bucket creation
   - Blueprint enablement (~3 min) - 17 blueprints
   - Policy grants creation (~2 min)
   - Domain sharing via RAM (~1 min)
   - EventBridge rules deployment
   - Domain visibility verification
3. **Available**: Account ready for project assignment
4. **Assignment**: Project created, account assigned automatically
5. **Deletion**: Project deleted, account closed automatically (DELETE strategy)

### Event-Driven Replenishment
- **Trigger**: CloudFormation stack CREATE_IN_PROGRESS events from project accounts
- **Detection**: EventBridge rules forward events to central bus in Domain account
- **Action**: Pool Manager checks available count, triggers replenishment if below minimum
- **Parallel**: Multiple accounts created and configured simultaneously
- **Blocking**: Replenishment blocked if ANY failed accounts exist (manual cleanup required)

### Reclaim Strategies
- **DELETE** (default): Accounts automatically closed when projects deleted (cost optimization)
- **REUSE** (optional): Accounts cleaned and returned to pool (preserves account quota)

## Monitoring and Observability

### CloudWatch Dashboards

The system provides 4 comprehensive dashboards accessible from both Org Admin and Domain accounts:

#### 1. Pool Overview Dashboard (`AccountPoolFactory-Overview`)
Shows real-time pool health and performance:
- **Pool Size by State**: Count of accounts in each state (AVAILABLE, ASSIGNED, SETTING_UP, FAILED, DELETING)
- **Account Creation Rate**: Accounts created per hour/day
- **Account Assignment Rate**: Accounts assigned per hour/day
- **Average Setup Duration**: Setup time over last 24 hours (target: 12 minutes)
- **Failed Account Breakdown**: Pie chart showing failures by setup step
- **Replenishment Events**: Recent replenishment triggers with quantities

#### 2. Account Inventory Dashboard (`AccountPoolFactory-Inventory`)
Detailed account tracking:
- **Account Table**: Account IDs, states, project assignments, creation dates, assigned dates, setup duration
- **Account Lifecycle Timeline**: Visual timeline showing account progression through states
- **Filters**: Filter by state, sort by date
- **Links**: Clickable links to CloudWatch Logs and DynamoDB records

#### 3. Failed Accounts Dashboard (`AccountPoolFactory-FailedAccounts`)
Failure analysis and troubleshooting:
- **Failed Account Count**: Current count of accounts in FAILED state
- **Failure Breakdown by Step**: Bar chart showing which setup steps fail most often
- **Retry Exhaustion Rate**: Percentage of failed accounts with retries exhausted
- **Failed Account Details**: Account IDs, failed steps, error messages, stack events, retry counts
- **Recent Failures**: Last 10 failed accounts with full error details

#### 4. Organization Limits Dashboard (`AccountPoolFactory-OrgLimits`)
Account quota monitoring:
- **Account Limit Status**: Total limit, accounts used, accounts remaining
- **Account Usage Trend**: Total accounts over last 30 days with limit line
- **Capacity Alarms**: Alarm status for remaining capacity
- **Daily/Weekly Statistics**: Accounts created/deleted/assigned per day and week

### Accessing Dashboards

**From AWS Console**:
1. Navigate to CloudWatch console in Domain account (or Org Admin account)
2. Select "Dashboards" from left menu
3. Open desired dashboard (AccountPoolFactory-Overview, etc.)
4. Dashboards auto-refresh every 1 minute

**From AWS CLI**:
```bash
# List all dashboards
aws cloudwatch list-dashboards --region us-east-2

# Get dashboard definition
aws cloudwatch get-dashboard \
  --dashboard-name AccountPoolFactory-Overview \
  --region us-east-2
```

### SNS Alerts

Subscribe to receive email/SMS alerts for critical events:

**Alert Types**:
- **Account Setup Failed**: Setup failed after retry exhaustion (includes account ID, failed step, error message, logs link)
- **Pool Depleted**: No available accounts in pool (immediate action required)
- **Replenishment Blocked**: Failed accounts exist, blocking new account creation (manual cleanup required)
- **Organization Account Limit Warning**: < 50 accounts remaining (request limit increase)
- **Organization Account Limit Critical**: < 20 accounts remaining (urgent action required)

**Subscribe to Alerts**:
```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-2:DOMAIN_ACCOUNT_ID:AccountPoolFactory-Alerts \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-2
```

### DynamoDB Query API

Programmatic access to account inventory for custom reporting or automation:

```bash
# Query accounts by state
aws dynamodb query \
  --table-name AccountPoolFactory-AccountState \
  --index-name StateIndex \
  --key-condition-expression "#state = :state" \
  --expression-attribute-names '{"#state":"state"}' \
  --expression-attribute-values '{":state":{"S":"AVAILABLE"}}' \
  --region us-east-2

# Query accounts by project
aws dynamodb query \
  --table-name AccountPoolFactory-AccountState \
  --index-name ProjectIndex \
  --key-condition-expression "projectId = :projectId" \
  --expression-attribute-values '{":projectId":{"S":"proj-abc123"}}' \
  --region us-east-2

# Get specific account details
aws dynamodb get-item \
  --table-name AccountPoolFactory-AccountState \
  --key '{"accountId":{"S":"123456789012"},"timestamp":{"N":"1709395200"}}' \
  --region us-east-2
```

### CloudWatch Logs

View Lambda execution logs for troubleshooting:

```bash
# Pool Manager logs
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2

# Setup Orchestrator logs
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2

# Account Provider logs
aws logs tail /aws/lambda/AccountProvider --follow --region us-east-2
```

### CloudWatch Insights Queries

Pre-built queries for common troubleshooting scenarios:

**Failed Accounts Summary**:
```sql
fields accountId, failedStep, errorMessage, retryCount
| filter state = "FAILED"
| sort timestamp desc
| limit 20
```

**Setup Duration Analysis**:
```sql
fields accountId, setupDuration
| filter state = "COMPLETED"
| stats avg(setupDuration), max(setupDuration), min(setupDuration) by bin(5m)
```

**Replenishment Events**:
```sql
fields @timestamp, availableCount, requestedCount, createdCount
| filter @message like /ReplenishmentTriggered/
| sort @timestamp desc
```

## Common Tasks

### Monitor Pool Status

**Via CloudWatch Dashboard**:
1. Open `AccountPoolFactory-Overview` dashboard
2. Check "Pool Size by State" widget for current counts
3. Review "Account Creation Rate" for replenishment activity

**Via CLI**:
```bash
# Check available accounts
aws dynamodb query \
  --table-name AccountPoolFactory-AccountState \
  --index-name StateIndex \
  --key-condition-expression "#state = :state" \
  --expression-attribute-names '{"#state":"state"}' \
  --expression-attribute-values '{":state":{"S":"AVAILABLE"}}' \
  --region us-east-2

# Check pool configuration
aws ssm get-parameters-by-path \
  --path /AccountPoolFactory/PoolManager/ \
  --region us-east-2
```

### Adjust Pool Size

Update SSM parameters to change pool behavior:

```bash
# Increase minimum pool size
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/MinimumPoolSize \
  --value "10" \
  --type String \
  --overwrite \
  --region us-east-2

# Increase target pool size
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/TargetPoolSize \
  --value "20" \
  --type String \
  --overwrite \
  --region us-east-2

# Pool Manager will use new values on next invocation
```

### Trigger Manual Replenishment

Force pool replenishment without waiting for events:

```bash
# Invoke Pool Manager Lambda manually
aws lambda invoke \
  --function-name PoolManager \
  --payload '{"action":"force_replenishment"}' \
  --region us-east-2 \
  response.json

# Monitor progress
aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
```

### Handle Failed Accounts

When replenishment is blocked due to failed accounts:

1. **Identify Failed Accounts**:
   - Open `AccountPoolFactory-FailedAccounts` dashboard
   - Review failed account details (account ID, failed step, error message)

2. **Investigate Failure**:
   ```bash
   # Get detailed error information
   aws dynamodb get-item \
     --table-name AccountPoolFactory-AccountState \
     --key '{"accountId":{"S":"FAILED_ACCOUNT_ID"},"timestamp":{"N":"TIMESTAMP"}}' \
     --region us-east-2
   
   # View CloudFormation stack events
   aws cloudformation describe-stack-events \
     --stack-name STACK_NAME \
     --region us-east-2
   ```

3. **Delete Failed Account**:
   ```bash
   # Close the failed account
   aws organizations close-account \
     --account-id FAILED_ACCOUNT_ID
   
   # Remove from DynamoDB (Pool Manager will do this automatically)
   # Replenishment will resume on next trigger
   ```

### Change Reclaim Strategy

Switch between DELETE (default) and REUSE strategies:

```bash
# Set to REUSE (clean and return accounts to pool)
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/ReclaimStrategy \
  --value "REUSE" \
  --type String \
  --overwrite \
  --region us-east-2

# Set to DELETE (close accounts when projects deleted)
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/ReclaimStrategy \
  --value "DELETE" \
  --type String \
  --overwrite \
  --region us-east-2
```

### View Account Details

Get detailed information about a specific account:

```bash
# Query by account ID
aws dynamodb query \
  --table-name AccountPoolFactory-AccountState \
  --key-condition-expression "accountId = :accountId" \
  --expression-attribute-values '{":accountId":{"S":"123456789012"}}' \
  --region us-east-2 \
  --limit 1 \
  --scan-index-forward false

# View in CloudWatch dashboard
# Open AccountPoolFactory-Inventory and search for account ID
```

### Check Organization Account Limits

Monitor how close you are to AWS account limits:

**Via Dashboard**:
1. Open `AccountPoolFactory-OrgLimits` dashboard
2. Check "Account Limit Status" widget
3. Review "Capacity Alarms" for warnings

**Via CLI**:
```bash
# Get current account limit
aws service-quotas get-service-quota \
  --service-code organizations \
  --quota-code L-29A0C5DF \
  --region us-east-1

# Count active accounts
aws organizations list-accounts \
  --query 'Accounts[?Status==`ACTIVE`] | length(@)'
```

### Request Account Limit Increase

If approaching account limits:

```bash
# Request limit increase via Service Quotas
aws service-quotas request-service-quota-increase \
  --service-code organizations \
  --quota-code L-29A0C5DF \
  --desired-value 100 \
  --region us-east-1
```

Or submit a support case through AWS Support Center.

## Troubleshooting

### Pool Replenishment Not Triggering

**Symptoms**: Available account count stays low, no new accounts being created

**Possible Causes**:
1. Failed accounts exist (replenishment blocked)
2. EventBridge rules not deployed to project accounts
3. Pool Manager Lambda not receiving events

**Solutions**:
```bash
# Check for failed accounts
aws dynamodb query \
  --table-name AccountPoolFactory-AccountState \
  --index-name StateIndex \
  --key-condition-expression "#state = :state" \
  --expression-attribute-names '{"#state":"state"}' \
  --expression-attribute-values '{":state":{"S":"FAILED"}}' \
  --region us-east-2

# If failed accounts exist, delete them
aws organizations close-account --account-id FAILED_ACCOUNT_ID

# Manually trigger replenishment
aws lambda invoke \
  --function-name PoolManager \
  --payload '{"action":"force_replenishment"}' \
  --region us-east-2 \
  response.json
```

### Account Setup Fails at Specific Step

**Symptoms**: Accounts stuck in SETTING_UP state, dashboard shows failures at specific step

**Common Failures**:

**VPC Deployment Failure**:
- Cause: Insufficient IP addresses in region
- Solution: Choose different region or request VPC quota increase

**Blueprint Enablement Failure**:
- Cause: Service quota exceeded (17 blueprints × N accounts)
- Solution: Request DataZone blueprint quota increase
- Check: `aws service-quotas get-service-quota --service-code datazone --quota-code L-XXXXXXXX`

**Policy Grants Failure**:
- Cause: Domain unit not found or access denied
- Solution: Verify root domain unit ID in SSM parameters
- Check: `aws ssm get-parameter --name /AccountPoolFactory/SetupOrchestrator/RootDomainUnitId`

**Domain Visibility Failure**:
- Cause: RAM share not active or domain not shared
- Solution: Verify RAM share exists and is ACTIVE
- Check: `aws ram get-resource-shares --resource-owner SELF --name DataZone-Domain-Share-*`

**Solutions**:
```bash
# View detailed error for failed account
aws dynamodb get-item \
  --table-name AccountPoolFactory-AccountState \
  --key '{"accountId":{"S":"ACCOUNT_ID"},"timestamp":{"N":"TIMESTAMP"}}' \
  --region us-east-2

# View CloudFormation stack events
aws cloudformation describe-stack-events \
  --stack-name STACK_NAME \
  --region us-east-2 \
  | jq '.StackEvents[] | select(.ResourceStatus | contains("FAILED"))'

# View Setup Orchestrator logs
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
```

### Project Creation Fails with "Account Not Authorized"

**Symptoms**: Project creation fails, error mentions account authorization

**Possible Causes**:
1. Account Provider Lambda not invoked
2. Account not in AVAILABLE state
3. Domain not visible in project account

**Solutions**:
```bash
# Check account state
aws dynamodb query \
  --table-name AccountPoolFactory-AccountState \
  --key-condition-expression "accountId = :accountId" \
  --expression-attribute-values '{":accountId":{"S":"ACCOUNT_ID"}}' \
  --region us-east-2

# Verify domain visibility from project account
# (requires assuming role in project account)
aws datazone list-domains --region us-east-2

# Check Account Provider Lambda logs
aws logs tail /aws/lambda/AccountProvider --follow --region us-east-2
```

### Environment Creation Fails

**Symptoms**: Environment stuck in CREATING state or fails with permission errors

**Possible Causes**:
1. IAM roles not deployed correctly
2. VPC or subnets missing
3. Blueprints not enabled

**Solutions**:
```bash
# Verify IAM roles exist in project account
aws iam get-role --role-name DataZoneManageAccessRole
aws iam get-role --role-name DataZoneProvisioningRole

# Verify VPC and subnets exist
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=SageMakerUnifiedStudioVPC"
aws ec2 describe-subnets --filters "Name=tag:Name,Values=SageMakerUnifiedStudioPrivateSubnet*"

# Verify blueprints enabled
aws datazone list-environment-blueprint-configurations \
  --domain-identifier DOMAIN_ID \
  --region us-east-2
```

### CloudWatch Dashboard Not Showing Data

**Symptoms**: Dashboard widgets empty or showing "No data"

**Possible Causes**:
1. Metrics not being published
2. Cross-account metrics sharing not configured
3. Time range too narrow

**Solutions**:
```bash
# Check if metrics exist
aws cloudwatch list-metrics \
  --namespace AccountPoolFactory/PoolManager \
  --region us-east-2

# Verify Lambda functions are running
aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `PoolManager`) || starts_with(FunctionName, `SetupOrchestrator`)]' \
  --region us-east-2

# Check Lambda execution logs for errors
aws logs tail /aws/lambda/PoolManager --region us-east-2
```

### SNS Alerts Not Received

**Symptoms**: No email alerts for failures or warnings

**Possible Causes**:
1. Subscription not confirmed
2. Email in spam folder
3. SNS topic permissions incorrect

**Solutions**:
```bash
# List subscriptions
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-2:ACCOUNT_ID:AccountPoolFactory-Alerts \
  --region us-east-2

# Check subscription status (should be "Confirmed")
# If "PendingConfirmation", check email for confirmation link

# Test SNS topic
aws sns publish \
  --topic-arn arn:aws:sns:us-east-2:ACCOUNT_ID:AccountPoolFactory-Alerts \
  --subject "Test Alert" \
  --message "This is a test alert from Account Pool Factory" \
  --region us-east-2
```

### High Setup Duration (> 15 minutes)

**Symptoms**: Dashboard shows average setup duration exceeding 15 minutes

**Possible Causes**:
1. CloudFormation stack deployments slow
2. API throttling
3. Resource contention

**Solutions**:
```bash
# Check for throttling errors in logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/SetupOrchestrator \
  --filter-pattern "ThrottlingException" \
  --region us-east-2

# Review setup duration by step
aws logs insights query \
  --log-group-name /aws/lambda/SetupOrchestrator \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields accountId, stepName, duration | filter stepName != "" | stats avg(duration) by stepName' \
  --region us-east-2
```

## Configuration Reference

### SSM Parameters

All configuration is stored in SSM Parameter Store for easy updates without redeployment:

**Pool Manager Configuration** (`/AccountPoolFactory/PoolManager/`):
- `PoolName`: Name for the account pool (default: AccountPoolFactory)
- `TargetOUId`: OU ID where accounts should be moved after creation (default: root). Use "root" to leave accounts in organization root, or provide an OU ID like "ou-xxxx-xxxxxxxx" to move accounts to a specific OU
- `MinimumPoolSize`: Minimum accounts to maintain (default: 5)
- `TargetPoolSize`: Target pool size after replenishment (default: 10)
- `MaxConcurrentSetups`: Maximum accounts being set up simultaneously (default: 3)
- `ReclaimStrategy`: DELETE or REUSE (default: DELETE)
- `EmailPrefix`: Email prefix for account creation (default: accountpool)
- `EmailDomain`: Email domain for account creation (default: example.com)
- `NamePrefix`: Account name prefix (default: DataZone-Pool)

**Dynamic Configuration Updates**:
All SSM parameters are read on every Lambda invocation, allowing configuration changes without Lambda restart:

```bash
# Update pool name
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/PoolName \
  --value "MyCustomPool" \
  --type String \
  --overwrite \
  --region us-east-2

# Update target OU (move accounts to specific OU)
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/TargetOUId \
  --value "ou-xxxx-xxxxxxxx" \
  --type String \
  --overwrite \
  --region us-east-2

# Changes take effect on next Lambda invocation (no restart needed)
```

**Setup Orchestrator Configuration** (`/AccountPoolFactory/SetupOrchestrator/`):
- `DomainId`: DataZone domain ID
- `DomainAccountId`: Domain account ID
- `RootDomainUnitId`: Root domain unit ID
- `Region`: AWS region
- `AlertTopicArn`: SNS topic ARN for alerts
- `RetryConfig`: JSON string with retry configuration:
  ```json
  {
    "max_retries": 3,
    "initial_backoff_seconds": 30,
    "backoff_multiplier": 2,
    "step_specific": {
      "blueprint_enablement": {
        "max_retries": 3,
        "initial_backoff_seconds": 60
      },
      "domain_visibility": {
        "max_retries": 10,
        "initial_backoff_seconds": 15
      }
    }
  }
  ```

### DynamoDB Table Schema

**Table Name**: `AccountPoolFactory-AccountState`

**Primary Key**:
- Partition Key: `accountId` (String)
- Sort Key: `timestamp` (Number)

**Global Secondary Indexes**:
- `StateIndex`: Query accounts by state
- `ProjectIndex`: Query accounts by project assignment

**Key Attributes**:
- `state`: AVAILABLE | ASSIGNED | SETTING_UP | FAILED | DELETING | CLEANING
- `createdDate`: ISO 8601 timestamp
- `assignedDate`: ISO 8601 timestamp (when assigned to project)
- `setupDuration`: Setup time in seconds
- `projectId`: DataZone project ID
- `projectStackName`: CloudFormation stack name
- `currentStep`: Current setup step
- `completedSteps`: Array of completed steps
- `failedStep`: Step that failed
- `errorMessage`: Error message for failures
- `stackEvents`: CloudFormation stack events for failures
- `retryCount`: Number of retry attempts
- `resources`: Object with VPC ID, subnet IDs, role ARNs, bucket name, blueprint IDs, grant IDs

### Lambda Functions

**Pool Manager Lambda**:
- Function Name: `PoolManager`
- Runtime: Python 3.12
- Timeout: 5 minutes
- Memory: 512 MB
- Trigger: EventBridge rule on central bus
- Responsibilities: Pool size monitoring, replenishment, account lifecycle

**Setup Orchestrator Lambda**:
- Function Name: `SetupOrchestrator`
- Runtime: Python 3.12
- Timeout: 15 minutes
- Memory: 1024 MB
- Trigger: Invoked by Pool Manager
- Responsibilities: 8-step account setup workflow

**Account Provider Lambda**:
- Function Name: `AccountProvider`
- Runtime: Python 3.12
- Timeout: 5 minutes
- Memory: 512 MB
- Trigger: DataZone account pool requests
- Responsibilities: List accounts, validate authorization

### CloudWatch Metrics

**Namespace**: `AccountPoolFactory/PoolManager` and `AccountPoolFactory/SetupOrchestrator`

**Key Metrics**:
- `AvailableAccountCount`: Current available accounts
- `AssignedAccountCount`: Current assigned accounts
- `SettingUpAccountCount`: Current accounts being set up
- `FailedAccountCount`: Current failed accounts
- `AccountCreationStarted`: Accounts creation initiated
- `AccountAssigned`: Account assignment events
- `AccountDeleted`: Account deletion events
- `ReplenishmentTriggered`: Replenishment events
- `ReplenishmentBlocked`: Replenishment blocked events
- `SetupSucceeded`: Successful setups
- `SetupFailed`: Failed setups
- `SetupStepFailed`: Failed setup steps (with step dimension)
- `OrganizationAccountsRemaining`: Remaining account capacity

### EventBridge Architecture

**Central Event Bus**: `AccountPoolFactory-CentralBus` (in Domain account)

**Event Pattern** (forwarded from project accounts):
```json
{
  "source": ["aws.cloudformation"],
  "detail-type": ["CloudFormation Stack Status Change"],
  "detail": {
    "stack-name": [{"prefix": "DataZone-"}]
  }
}
```

**EventBridge Rules** (deployed to each project account):
- Rule Name: `DataZone-Stack-Events-Forwarder`
- Target: Central Event Bus in Domain account
- IAM Role: `EventBridgeForwarderRole`

## Cost Estimation

### Monthly Costs (Typical Usage)

**Lambda Functions**:
- Pool Manager: ~$0.20/month (100 invocations/day)
- Setup Orchestrator: ~$2.00/month (10 account setups/day)
- Account Provider: ~$0.10/month (50 invocations/day)

**DynamoDB**:
- On-demand pricing: ~$1.25/month (1000 reads/writes per day)
- Storage: ~$0.25/GB/month

**EventBridge**:
- Custom event bus: $1.00/million events
- Estimated: ~$0.10/month (3000 events/day)

**CloudWatch**:
- Metrics: $0.30/metric/month (~20 metrics = $6.00)
- Dashboards: $3.00/dashboard/month (4 dashboards = $12.00)
- Logs: $0.50/GB ingested (~2 GB/month = $1.00)
- Alarms: $0.10/alarm/month (5 alarms = $0.50)

**SNS**:
- Email notifications: First 1000 free, then $2.00/100,000

**Total Estimated Monthly Cost**: ~$25-30/month

**Cost Optimization Tips**:
- Use DELETE strategy to minimize account count (accounts cost $0 when closed)
- Set appropriate pool sizes (avoid over-provisioning)
- Configure log retention to 7-14 days for non-production
- Use CloudWatch Logs Insights instead of exporting to S3

### AWS Account Costs

**Account Creation**: Free (no charge for creating AWS accounts)

**Account Maintenance**: 
- Active accounts: No monthly fee
- Closed accounts: No charge (accounts closed after 90-day suspension period)

**Resource Costs in Project Accounts**:
- VPC: Free (no charge for VPC itself)
- S3 buckets: $0.023/GB/month (minimal for blueprint artifacts)
- IAM roles: Free
- DataZone environments: Charged based on resources deployed (EC2, RDS, etc.)

**Note**: The Account Pool Factory infrastructure costs are minimal. The majority of costs come from DataZone environments deployed by users in project accounts.

## Security Considerations

### Least Privilege Access

All Lambda functions use IAM roles with minimum required permissions:
- Pool Manager: Organizations, DynamoDB, Lambda, SNS, CloudWatch, SSM, STS
- Setup Orchestrator: CloudFormation, DataZone, RAM, S3, IAM (PassRole only), DynamoDB, SNS, CloudWatch, SSM, STS
- Account Provider: DataZone, DynamoDB, CloudWatch

### Data Protection

- **DynamoDB**: Encryption at rest enabled by default
- **SNS**: Messages encrypted in transit (TLS)
- **CloudWatch Logs**: Encrypted with AWS managed keys
- **S3 Buckets**: Created with AES256 encryption enabled
- **EventBridge**: Events encrypted in transit

### Audit Trail

- **CloudTrail**: All API calls logged automatically
- **DynamoDB Streams**: Capture state changes for audit
- **CloudWatch Logs**: All Lambda operations logged
- **SNS Notifications**: Critical events sent to administrators

### Cross-Account Access

- **OrganizationAccountAccessRole**: Used for cross-account operations (created automatically by Organizations)
- **EventBridge**: Cross-account event forwarding restricted to organization accounts only
- **RAM Shares**: Domain sharing restricted to specific project accounts

### Secrets Management

- No hardcoded credentials in code
- IAM roles for authentication
- SSM Parameter Store for configuration (not secrets)
- Temporary credentials via STS AssumeRole for cross-account access

## Best Practices

### Pool Sizing

**Minimum Pool Size**: Set based on expected project creation rate
- Low activity (< 5 projects/day): MinimumPoolSize = 3
- Medium activity (5-20 projects/day): MinimumPoolSize = 5
- High activity (> 20 projects/day): MinimumPoolSize = 10

**Target Pool Size**: Set 2x minimum to handle bursts
- MinimumPoolSize = 5 → TargetPoolSize = 10
- MinimumPoolSize = 10 → TargetPoolSize = 20

**Max Concurrent Setups**: Limit parallel account configuration
- Small deployments: MaxConcurrentSetups = 3
- Large deployments: MaxConcurrentSetups = 5
- Note: Higher values may hit API rate limits

### Reclaim Strategy

**DELETE (Recommended)**:
- Minimizes costs (accounts closed when not in use)
- Clean state for each project
- No account quota concerns
- Use when: Cost optimization is priority

**REUSE (Optional)**:
- Preserves account quota
- Faster project creation (no account creation delay)
- Requires cleanup automation
- Use when: Account quota is limited or account creation is restricted

### Monitoring

**Daily Tasks**:
- Check `AccountPoolFactory-Overview` dashboard for pool health
- Review available account count (should be > minimum)
- Verify no failed accounts blocking replenishment

**Weekly Tasks**:
- Review `AccountPoolFactory-FailedAccounts` dashboard for patterns
- Check `AccountPoolFactory-OrgLimits` dashboard for capacity
- Review daily/weekly statistics for trends

**Monthly Tasks**:
- Review CloudWatch costs and optimize if needed
- Adjust pool sizes based on usage patterns
- Request account limit increases if approaching capacity

### Alert Response

**Account Setup Failed**:
1. Review error message in SNS notification
2. Check CloudWatch Logs for detailed stack trace
3. Investigate root cause (quota, permissions, configuration)
4. Delete failed account to unblock replenishment
5. Fix root cause before next replenishment

**Pool Depleted**:
1. Check for failed accounts blocking replenishment
2. Verify Pool Manager Lambda is running
3. Manually trigger replenishment if needed
4. Increase target pool size if depletion is frequent

**Organization Account Limit Warning**:
1. Review current account usage in dashboard
2. Identify accounts that can be closed
3. Request limit increase via Service Quotas
4. Consider REUSE strategy to preserve quota

## Next Steps

- Review [Design Document](../.kiro/specs/setup-orchestrator/design.md) for technical details
- See [Requirements Document](../.kiro/specs/setup-orchestrator/requirements.md) for complete specifications
- Check [Development Progress](DevelopmentProgress.md) for implementation status
- Consult [Testing Guide](TestingGuide.md) for validation procedures

## Support

For issues or questions:
- Review CloudWatch Logs for Lambda errors
- Check DynamoDB tables for account state
- Verify configuration in SSM Parameter Store
- Open CloudWatch dashboards for visual monitoring
- Review SNS alerts for critical events
- Consult design and requirements documentation in `.kiro/specs/setup-orchestrator/`
