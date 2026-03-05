# Account Pool Factory - User Guide

## Overview

The Account Pool Factory automates AWS account provisioning for Amazon DataZone projects. It maintains a shadow pool of pre-configured accounts that are automatically assigned to projects on demand - one dedicated account per project. The system uses event-driven replenishment to ensure accounts are always ready, eliminating the 6-8 minute setup delay during project creation.

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
3. **Wave-Based Parallel Setup**: Multiple accounts are created and configured simultaneously using wave-based parallel execution (6-8 minutes per account)
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

**Note**: For the initial release, Organization Administrator setup is optional. The system uses Organizations API directly for account creation, which doesn't require StackSets. StackSets will be used in future releases for automated account configuration.

**What Happens Next**: The Domain Administrator will deploy Lambda functions that create and configure accounts.

### Domain Administrator Deployment

**Prerequisites**:
- DataZone domain already exists
- Domain ID, ARN, and root domain unit ID available
- IAM permissions for Lambda, DynamoDB, RAM, DataZone, CloudWatch
- Organization Administrator has deployed StackSets (optional for initial release)

**Step 1: Deploy Account Pool Infrastructure**

This deploys all Lambda functions, DynamoDB tables, EventBridge bus, SNS topics, and CloudWatch dashboards in your Domain account.

**Audience**: 1b (Existing Accounts - Production)

**Script**: `scripts/02-domain-account/deploy/01-deploy-infrastructure.sh`

**What it does**:
- Creates CloudFormation stack with all infrastructure components
- Deploys Pool Manager Lambda (monitors pool, triggers replenishment)
- Deploys Setup Orchestrator Lambda (configures accounts)
- Creates DynamoDB table for account state tracking
- Creates EventBridge central bus for events
- Creates SNS topic for alerts
- Creates 13 SSM parameters with configuration
- Creates 4 CloudWatch dashboards

**Command**:
```bash
cd experimental/AccountPoolFactory
./scripts/02-domain-account/deploy/01-deploy-infrastructure.sh
```

**Sample Output**:
```
🚀 Deploying Account Pool Factory Infrastructure
================================================
Region: us-east-2
Domain Account: 994753223772
Domain ID: dzd-5o0lje5xgpeuw9

📦 Packaging Lambda functions...
✓ Pool Manager packaged
✓ Setup Orchestrator packaged

📤 Uploading to S3...
✓ Uploaded to s3://accountpoolfactory-artifacts-994753223772/pool-manager.zip
✓ Uploaded to s3://accountpoolfactory-artifacts-994753223772/setup-orchestrator.zip

🏗️  Deploying CloudFormation stack...
Stack Name: AccountPoolFactory-Infrastructure

Waiting for stack creation...
✓ Stack created successfully!

📊 Stack Outputs:
  DynamoDBTableName: AccountPoolFactory-AccountState
  EventBusArn: arn:aws:events:us-east-2:994753223772:event-bus/AccountPoolFactory-CentralBus
  SNSTopicArn: arn:aws:sns:us-east-2:994753223772:AccountPoolFactory-Alerts
  PoolManagerArn: arn:aws:lambda:us-east-2:994753223772:function:PoolManager
  SetupOrchestratorArn: arn:aws:lambda:us-east-2:994753223772:function:SetupOrchestrator

✅ Infrastructure deployment complete!

Next steps:
1. Deploy cross-account role: Switch to Org Admin account and run ./deploy-org-admin-role.sh
2. Deploy Account Provider Lambda: ./deploy-account-provider.sh
3. Create account pool: ./create-account-pool.sh
4. Create project profile: ./create-project-profile.sh
```

**Resources Created**:
- **DynamoDB Table**: AccountPoolFactory-AccountState
- **EventBridge Bus**: AccountPoolFactory-CentralBus
- **SNS Topic**: AccountPoolFactory-Alerts
- **Pool Manager Lambda**: arn:aws:lambda:us-east-2:994753223772:function:PoolManager
- **Setup Orchestrator Lambda**: arn:aws:lambda:us-east-2:994753223772:function:SetupOrchestrator
- **13 SSM Parameters**: /AccountPoolFactory/* (pool config, domain info, retry settings)
- **4 CloudWatch Dashboards**: Overview, Inventory, FailedAccounts, OrgLimits

**Step 2: Deploy Cross-Account Role (Organization Admin Account)**

**Audience**: 1b (Existing Accounts - Production)

This deploys the cross-account IAM role that allows Pool Manager Lambda in the Domain account to create and manage accounts via Organizations API.

**Script**: `scripts/01-org-mgmt-account/deploy/02-deploy-account-creation-role.sh`

**What it does**:
- Deploys IAM role in Organization Admin account
- Configures trust policy with External ID for security
- Grants least-privilege Organizations API permissions
- Saves role ARN and External ID for Domain account configuration

**Security Features**:
- External ID prevents confused deputy attacks
- Least-privilege permissions (only account creation/management)
- Trust policy restricted to specific Lambda role in Domain account

**Command** (run in Organization Admin account):
```bash
# Switch to Organization Admin account credentials
export AWS_PROFILE=org-admin  # or use aws configure

./scripts/01-org-mgmt-account/deploy/02-deploy-account-creation-role.sh
```

**Sample Output**:
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

Next steps:
1. Switch back to Domain account credentials
2. Update SSM parameter with role ARN:
   aws ssm put-parameter --name /AccountPoolFactory/PoolManager/OrgAdminRoleArn \
     --value 'arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation' \
     --type String --region us-east-2
3. Update SSM parameter with external ID:
   aws ssm put-parameter --name /AccountPoolFactory/PoolManager/ExternalId \
     --value 'AccountPoolFactory-994753223772' \
     --type String --region us-east-2
4. Trigger pool replenishment: ./seed-initial-pool.sh
```

**Resources Created**:
- **IAM Role**: AccountPoolFactory-AccountCreation
- **Role ARN**: arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation
- **External ID**: AccountPoolFactory-{DomainAccountId}

**After Deployment** (run in Domain account):
```bash
# Switch back to Domain account
export AWS_PROFILE=domain-account

# Configure Pool Manager with cross-account role
aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/OrgAdminRoleArn \
  --value 'arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation' \
  --type String \
  --region us-east-2

aws ssm put-parameter \
  --name /AccountPoolFactory/PoolManager/ExternalId \
  --value 'AccountPoolFactory-994753223772' \
  --type String \
  --region us-east-2
```

**Step 3: Deploy Trust Policy StackSet (Organization Admin Account)**

**Audience**: 1b (Existing Accounts - Production)

This deploys a StackSet that updates the OrganizationAccountAccessRole trust policy in all pool accounts, allowing the Setup Orchestrator Lambda in the Domain account to configure them.

**Script**: `scripts/01-org-mgmt-account/deploy/03-deploy-trust-policy-stackset.sh`

**What it does**:
- Creates a CloudFormation StackSet in Organization Admin account
- Deploys stack instances to all accounts in the target OU
- Updates OrganizationAccountAccessRole trust policy to include Domain account
- Enables Setup Orchestrator to assume role and deploy CloudFormation stacks

**Why This is Needed**:
When AWS Organizations creates new accounts, the OrganizationAccountAccessRole only trusts the Organization Admin account by default. The Setup Orchestrator Lambda runs in the Domain account and needs to assume this role to deploy VPC, IAM roles, EventBridge rules, and blueprints in each pool account.

**Command** (run in Organization Admin account):
```bash
# Switch to Organization Admin account credentials
eval $(isengardcli credentials amirbo+1@amazon.com)
# OR: export AWS_PROFILE=org-admin

./scripts/01-org-mgmt-account/deploy/03-deploy-trust-policy-stackset.sh
```

**Sample Output**:
```
🚀 Deploying Trust Policy StackSet
====================================
Region: us-east-2
Org Admin Account: 495869084367
Domain Account: 994753223772
Target OU: ou-n5om-otvkrtx2

📦 Creating new StackSet...
✅ StackSet created

📋 Deploying StackSet instances to target OU...
✅ StackSet instances deployment initiated

📊 Checking deployment status...
   Operation status: RUNNING
   Operation status: RUNNING
   Operation status: SUCCEEDED

✅ StackSet deployment completed successfully!

📊 StackSet Summary:
-----------------------------------------------------------
| AccountPoolFactory-TrustPolicy | ACTIVE | Trust policy |
-----------------------------------------------------------

📋 Stack Instances:
-----------------------------------------------------------
| 669468173247 | us-east-2 | CURRENT |
| 476383094227 | us-east-2 | CURRENT |
| 071378140110 | us-east-2 | CURRENT |
-----------------------------------------------------------

✅ Trust policy deployment complete!

Next steps:
1. Verify all stack instances are in CREATE_COMPLETE status
2. Switch back to Domain account:
   eval $(isengardcli credentials amirbo+3@amazon.com)
3. Retry Setup Orchestrator for failed accounts
```

**Resources Created**:
- **StackSet**: AccountPoolFactory-TrustPolicy
- **Stack Instances**: One per account in target OU
- **Updated Role**: OrganizationAccountAccessRole (trust policy includes Domain account)

**Auto-Deployment**:
The StackSet is configured with auto-deployment enabled. When new accounts are created in the target OU, the trust policy update will be automatically deployed to them within a few minutes.

**After Deployment** (run in Domain account):
```bash
# Switch back to Domain account
eval $(isengardcli credentials amirbo+3@amazon.com)

# Retry setup for any failed accounts
aws lambda invoke \
  --function-name SetupOrchestrator \
  --cli-binary-format raw-in-base64-out \
  --payload '{"accountId":"ACCOUNT_ID","mode":"setup"}' \
  --region us-east-2 \
  /tmp/response.json
```

**Step 4: Deploy Account Provider Lambda**

**Audience**: 1b (Existing Accounts - Production)

This deploys the Account Provider Lambda that handles DataZone account pool requests.

**Script**: `scripts/02-domain-account/deploy/02-deploy-lambdas.sh`

**What it does**:
- Packages Account Provider Lambda code
- Uploads to S3
- Deploys Lambda function with IAM role
- Configures permissions for DataZone to invoke

**Command**:
```bash
./scripts/02-domain-account/deploy/02-deploy-lambdas.sh
```

**Sample Output**:
```
🚀 Deploying Account Provider Lambda
====================================
Region: us-east-2
Domain Account: 994753223772

📦 Packaging Lambda function...
✓ Account Provider packaged

📤 Uploading to S3...
✓ Uploaded to s3://accountpoolfactory-artifacts-994753223772/account-provider.zip

🏗️  Creating Lambda function...
✓ Lambda function created: AccountProvider
✓ Function ARN: arn:aws:lambda:us-east-2:994753223772:function:AccountProvider

🔐 Configuring permissions...
✓ DataZone can invoke this Lambda

✅ Account Provider deployment complete!

Lambda Details:
  Function Name: AccountProvider
  Runtime: python3.12
  Handler: lambda_function.lambda_handler
  Role: AccountProviderLambdaRole

Next steps:
1. Create account pool: ./create-account-pool.sh
```

**Resources Created**:
- **Lambda Function**: AccountProvider
- **IAM Role**: AccountProviderLambdaRole
- **Lambda Permission**: Allows DataZone service to invoke

**Step 4: Create DataZone Account Pool**

**Audience**: 1a (New Accounts - Testing) and 1b (Existing Accounts - Production)

This creates the DataZone account pool and registers your Account Provider Lambda as the custom handler.

**Script**: `tests/setup/04-create-account-pool.sh` (for testing) or use AWS CLI directly (for production)

**What it does**:
- Retrieves Lambda ARN and Role ARN
- Creates DataZone account pool with MANUAL resolution strategy
- Registers Lambda as customAccountPoolHandler
- Saves pool details to account-pool-details.json

**Command**:
```bash
# For testing (Audience 1a)
./tests/setup/04-create-account-pool.sh

# For production (Audience 1b) - use AWS CLI directly
# See script for reference implementation
```

**Sample Output**:
```
🚀 Creating DataZone Account Pool
==================================
Domain ID: dzd-5o0lje5xgpeuw9
Domain Account: 994753223772
Region: us-east-2

Lambda Function ARN: arn:aws:lambda:us-east-2:994753223772:function:AccountProvider
Lambda Role ARN: arn:aws:iam::994753223772:role/AccountProviderLambdaRole

📦 Creating account pool...

✅ Account pool created successfully!

Pool ID: 5id04597iehicp
Pool ARN: arn:aws:datazone:us-east-2:994753223772:account-pool/dzd-5o0lje5xgpeuw9/5id04597iehicp
Pool Name: AccountPoolFactory
Resolution Strategy: MANUAL

📄 Pool details saved to: account-pool-details.json

📊 Account pool details:
{
  "domainId": "dzd-5o0lje5xgpeuw9",
  "name": "AccountPoolFactory",
  "id": "5id04597iehicp",
  "description": "Automated account pool managed by Account Pool Factory",
  "resolutionStrategy": "MANUAL",
  "accountSource": {
    "customAccountPoolHandler": {
      "lambdaFunctionArn": "arn:aws:lambda:us-east-2:994753223772:function:AccountProvider",
      "lambdaExecutionRoleArn": "arn:aws:iam::994753223772:role/AccountProviderLambdaRole"
    }
  },
  "createdAt": "2026-03-03T20:17:56.675745+00:00",
  "domainUnitId": "563ikhcj7fgkrt"
}

✅ Account pool setup complete!

Next steps:
1. Create a project profile that uses this account pool: ./create-project-profile.sh
2. Seed the initial pool with accounts: ./seed-initial-pool.sh
3. Create a test project
```

**Resources Created**:
- **DataZone Account Pool**: AccountPoolFactory (ID: 5id04597iehicp)
- **Pool Configuration File**: account-pool-details.json

**Step 5: Create Project Profile with Account Pool**

**Audience**: 1a (New Accounts - Testing) and 1b (Existing Accounts - Production)

This creates a DataZone project profile that uses the account pool for dynamic account assignment. There are two types of profiles based on your domain type:

- **Open Project Profile** (for IAM-based domains): Uses ToolingLite and simpler blueprints
- **Closed Project Profile** (for IDC-based domains): Uses full enterprise blueprints (Tooling, DataLake, etc.)

**Script for IAM Domains**: `tests/setup/05-create-open-profile.sh` (testing) or AWS CLI (production)
**Script for IDC Domains**: `tests/setup/06-create-closed-profile.sh` (testing) or AWS CLI (production)

**What it does**:
- Fetches all available blueprint IDs from domain
- Creates project profile with account pool integration
- Configures environment blueprints appropriate for domain type
- Adds policy grants for blueprints and project profile
- Saves profile details to JSON file

**Command (for IAM domain)**:
```bash
# For testing (Audience 1a)
./tests/setup/05-create-open-profile.sh

# For production (Audience 1b) - use AWS CLI directly
# See script for reference implementation
```

**Sample Output**:
```
🚀 Creating Open Project Profile with Account Pool (IAM Domain)
==============================================================
Domain ID: dzd-5o0lje5xgpeuw9
Domain Unit ID: 563ikhcj7fgkrt
Domain Account: 994753223772
Region: us-east-2

Account Pool ID: 5id04597iehicp

📋 Fetching blueprint IDs from domain...
Blueprint IDs (IAM Domain):
  ToolingLite: 4iny26qew2b8mh
  S3Bucket: 3ydt1bhkq3sesp
  S3TableCatalog: 4sfeixs7cu9v1l

🔧 Building environment configurations for open projects...
📦 Creating open project profile...

✅ Open project profile created successfully!

Profile ID: danattlt8uwzah
Profile Name: Open Project - Account Pool

📄 Profile details saved to: open-project-profile-details.json

🔐 Adding policy grants...

Adding policy grant for ToolingLite...
✅ Policy grant added for ToolingLite
Adding policy grant for S3Bucket...
✅ Policy grant added for S3Bucket
Adding policy grant for S3TableCatalog...
✅ Policy grant added for S3TableCatalog

Adding policy grant for Project Profile...
✅ Policy grant added for Project Profile

✅ Open project profile setup complete!

Profile Type: Open (IAM Domain)
Blueprints: ToolingLite (ON_CREATE), S3Bucket, S3TableCatalog (ON_DEMAND)

Next steps:
1. Seed the initial pool with accounts: ./seed-initial-pool.sh
2. Create a test project using this profile
3. Verify account assignment from pool
```

**Resources Created (IAM Domain)**:
- **Project Profile**: Open Project - Account Pool (ID: danattlt8uwzah)
- **Environment Configurations**: 3 blueprints configured with account pool
  - ToolingLite (ON_CREATE) - Lightweight tooling environment
  - S3Bucket (ON_DEMAND) - S3 bucket for data storage
  - S3TableCatalog (ON_DEMAND) - S3 table catalog for data discovery
- **Policy Grants**: 4 grants (3 blueprints + 1 profile)
- **Profile Configuration File**: open-project-profile-details.json

**Resources Created (IDC Domain)**:
- **Project Profile**: Closed Project - Account Pool
- **Environment Configurations**: 8+ blueprints configured with account pool
  - Tooling (ON_CREATE) - Full tooling environment with Spaces and Bedrock
  - DataLake (ON_CREATE) - Lakehouse database with Glue and Athena
  - RedshiftServerless (ON_CREATE) - Redshift Serverless workgroup
  - Workflows (ON_DEMAND) - Airflow workflows
  - MLExperiments (ON_DEMAND) - SageMaker MLflow
  - EmrOnEc2 (ON_DEMAND) - EMR on EC2 clusters
  - EmrServerless (ON_DEMAND) - EMR Serverless applications
- **Policy Grants**: 9+ grants (8+ blueprints + 1 profile)
- **Profile Configuration File**: closed-project-profile-details.json

**Step 6: Configure Pool Settings**

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

**Step 7: Seed Initial Pool**

**Audience**: 1a (New Accounts - Testing)

Trigger the Pool Manager to create the initial set of accounts.

**Script**: `tests/setup/03-seed-test-accounts.sh`

**What it does**:
- Invokes Pool Manager Lambda with force_replenishment action
- Pool Manager creates accounts via Organizations API
- Setup Orchestrator configures each account
- Accounts transition to AVAILABLE state when ready

**Command**:
```bash
./tests/setup/03-seed-test-accounts.sh
```

**Sample Output**:
```
🚀 Seeding Initial Account Pool
================================
Region: us-east-2

📞 Invoking Pool Manager Lambda...
✓ Pool Manager invoked successfully

Response:
{
  "statusCode": 200,
  "body": {
    "action": "force_replenishment",
    "availableCount": 0,
    "targetPoolSize": 5,
    "accountsToCreate": 5,
    "message": "Replenishment triggered: creating 5 accounts"
  }
}

📊 Monitor progress:
  Pool Manager logs: aws logs tail /aws/lambda/PoolManager --follow --region us-east-2
  Setup Orchestrator logs: aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
  DynamoDB table: aws dynamodb scan --table-name AccountPoolFactory-AccountState --region us-east-2

⏱️  Expected completion time: 6-8 minutes per account

✅ Initial pool seeding started!

Next steps:
1. Monitor CloudWatch Logs for progress
2. Check CloudWatch Dashboard: AccountPoolFactory-Overview
3. Wait for accounts to reach AVAILABLE state
4. Create a test project using the project profile
```

**What Happens Next**:
1. Pool Manager creates 5 accounts via Organizations API (< 1 minute each)
2. Setup Orchestrator configures each account in parallel (6-8 minutes each)
3. Accounts transition through states: SETTING_UP → AVAILABLE
4. CloudWatch metrics and dashboards update in real-time

**Step 8: Monitor Pool Health**

Access the CloudFormation dashboards to monitor your account pool:

1. Navigate to CloudWatch console in Domain account
2. Select "Dashboards" from left menu
3. Open these dashboards:
   - **AccountPoolFactory-Overview**: Real-time pool status, creation rates, setup duration
   - **AccountPoolFactory-Inventory**: Account table with IDs, states, projects, dates
   - **AccountPoolFactory-FailedAccounts**: Failed account details and error breakdown
   - **AccountPoolFactory-OrgLimits**: Organization account usage and limits

You can also access these dashboards from the Org Admin account (cross-account metrics sharing is configured automatically).

**Step 9: Subscribe to Alerts**

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
- **SETTING_UP**: Being created and configured (6-8 minutes with wave-based parallel execution)
- **FAILED**: Setup failed after retry exhaustion
- **DELETING**: Being closed via Organizations API
- **CLEANING**: Being cleaned for reuse (REUSE strategy only)

### Account Lifecycle
1. **Creation**: Pool Manager creates account via Organizations API (< 1 minute)
2. **Setup**: Setup Orchestrator runs 8-step workflow in 6 waves with parallel execution (6-8 minutes):
   - Wave 1: VPC deployment (~2.5 min)
   - Wave 2: IAM roles + EventBridge rules in parallel (~2 min)
   - Wave 3: S3 bucket + RAM share in parallel (~1 min)
   - Wave 4: Blueprint enablement (~3 min) - 17 blueprints
   - Wave 5: Policy grants creation (~2 min)
   - Wave 6: Domain visibility verification (~1 min)
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
