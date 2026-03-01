# Account Pool Factory - Technical Design

## 1. System Architecture

### 1.1 High-Level Architecture

The Account Pool Factory is a distributed system spanning three AWS account types:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Organization Admin Account                        │
│  ┌──────────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│  │ Control Tower    │  │ EventBridge     │  │ Cross-Account    │  │
│  │ Account Factory  │──│ Rules           │──│ IAM Role         │  │
│  │ (Service Catalog)│  │                 │  │                  │  │
│  └──────────────────┘  └─────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ EventBridge Events
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Domain Account                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ DataZone     │  │ Account Pool │  │ Lambda Functions         │ │
│  │ Domain       │──│ (DynamoDB)   │──│ - Account Provider       │ │
│  │              │  │              │  │ - Pool Manager           │ │
│  └──────────────┘  └──────────────┘  │ - Account Creator        │ │
│                                       │ - Setup Orchestrator     │ │
│  ┌──────────────┐  ┌──────────────┐  └──────────────────────────┘ │
│  │ Step         │  │ CloudWatch   │  ┌──────────────────────────┐ │
│  │ Functions    │  │ Dashboard    │  │ SNS Topics               │ │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ StackSet Deployment
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Project Accounts (Pool)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Account 1    │  │ Account 2    │  │ Account N    │             │
│  │ - IAM Roles  │  │ - IAM Roles  │  │ - IAM Roles  │             │
│  │ - CloudTrail │  │ - CloudTrail │  │ - CloudTrail │             │
│  │ - VPC (opt)  │  │ - VPC (opt)  │  │ - VPC (opt)  │             │
│  │ - Blueprints │  │ - Blueprints │  │ - Blueprints │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

#### Organization Admin Account (CF1)
- Hosts AWS Control Tower Account Factory
- Manages AWS Organizations structure
- Emits account lifecycle events via EventBridge
- Provides cross-account access to Domain account

#### Domain Account (CF2)
- Hosts DataZone domain and custom account pool
- Manages account pool state in DynamoDB
- Orchestrates account provisioning workflow
- Monitors pool health and triggers replenishment
- Provides accounts to DataZone projects

#### Project Accounts (CF3)
- Pre-configured accounts ready for project assignment
- DataZone domain association via AWS RAM
- Enabled blueprints for project environments
- IAM roles for project operations
- Baseline security and compliance configuration

## 2. Data Model

### 2.1 Account Pool Table (DynamoDB)

**Table Name**: `AccountPool-{DomainId}`

**Primary Key**: 
- Partition Key: `AccountId` (String)

**Attributes**:
```json
{
  "AccountId": "123456789012",
  "AccountName": "smus-project-001",
  "AccountEmail": "smus-project-001@example.com",
  "State": "AVAILABLE",
  "CreatedAt": "2024-01-15T10:00:00Z",
  "UpdatedAt": "2024-01-15T10:15:00Z",
  "AssignedAt": null,
  "ProjectId": null,
  "ProjectName": null,
  "ProvisioningStartedAt": "2024-01-15T10:00:00Z",
  "ProvisioningCompletedAt": "2024-01-15T10:15:00Z",
  "SetupStartedAt": "2024-01-15T10:15:00Z",
  "SetupCompletedAt": "2024-01-15T10:20:00Z",
  "RetryCount": 0,
  "LastError": null,
  "Tags": {
    "Purpose": "DataZone",
    "ManagedBy": "AccountPoolFactory"
  },
  "OrganizationalUnit": "ou-xxxx-xxxxxxxx",
  "StackSetInstanceId": "arn:aws:cloudformation:...",
  "TTL": 1735689600
}
```

**States**:
- `PROVISIONING`: Control Tower is creating the account
- `CONFIGURING`: CF3 StackSet is being deployed
- `AVAILABLE`: Ready for assignment to a project
- `ASSIGNED`: Assigned to a DataZone project
- `FAILED`: Provisioning or configuration failed

**Global Secondary Indexes**:
1. `StateIndex`: 
   - Partition Key: `State`
   - Sort Key: `CreatedAt`
   - Purpose: Query accounts by state for pool management

2. `ProjectIndex`:
   - Partition Key: `ProjectId`
   - Sort Key: `AssignedAt`
   - Purpose: Query accounts by project

### 2.2 Configuration Table (DynamoDB)

**Table Name**: `AccountPoolConfig-{DomainId}`

**Primary Key**:
- Partition Key: `ConfigKey` (String)

**Attributes**:
```json
{
  "ConfigKey": "PoolSettings",
  "MinimumPoolSize": 5,
  "MaximumPoolSize": 20,
  "ReplenishmentThreshold": 7,
  "AccountNamePrefix": "smus-project-",
  "AccountEmailDomain": "aws-accounts@example.com",
  "OrganizationalUnitPath": "/Projects/DataZone",
  "UpdatedAt": "2024-01-15T10:00:00Z",
  "UpdatedBy": "admin@example.com"
}
```

## 3. API Specifications

### 3.1 DataZone Custom Account Provider Lambda

**Function Name**: `AccountProvider-{DomainId}`

**Handler**: `account_provider.handler`

**Event Structure** (from DataZone):

DataZone invokes the Lambda with two types of operations:

1. **ListAuthorizedAccountsRequest** - Get list of available accounts
```json
{
  "operationRequest": {
    "listAuthorizedAccountsRequest": {}
  }
}
```

2. **ValidateAccountAuthorizationRequest** - Validate account authorization
```json
{
  "operationRequest": {
    "validateAccountAuthorizationRequest": {
      "awsAccountId": "123456789012"
    }
  }
}
```

**Response Structure** (to DataZone):

1. **ListAuthorizedAccountsResponse**:
```json
{
  "operationResponse": {
    "listAuthorizedAccountsResponse": {
      "items": [
        {
          "awsAccountId": "123456789012",
          "awsAccountName": "smus-project-001",
          "supportedRegions": ["us-east-1", "us-west-2"]
        },
        {
          "awsAccountId": "123456789013",
          "awsAccountName": "smus-project-002",
          "supportedRegions": ["us-east-1", "us-west-2"]
        }
      ]
    }
  }
}
```

2. **ValidateAccountAuthorizationResponse**:
```json
{
  "operationResponse": {
    "validateAccountAuthorizationResponse": {
      "authResult": "GRANT"
    }
  }
}
```

**Error Handling**:
- Return empty items array if no accounts available
- Return "DENY" for authResult if account not authorized
- Raise exception for unsupported operations

### 3.2 Pool Manager Lambda

**Function Name**: `PoolManager-{DomainId}`

**Trigger**: EventBridge scheduled rule (every 5 minutes)

**Logic**:
1. Query DynamoDB for accounts in `AVAILABLE` state
2. If count < `ReplenishmentThreshold`:
   - Calculate accounts needed: `MinimumPoolSize - current_count`
   - Invoke Account Creator Lambda for each needed account
3. Emit CloudWatch metrics
4. Send SNS alert if pool is critically low

### 3.3 Account Creator Lambda

**Function Name**: `AccountCreator-{DomainId}`

**Invocation**: Synchronous from Pool Manager

**Input**:
```json
{
  "accountName": "smus-project-005",
  "accountEmail": "smus-project-005@example.com",
  "organizationalUnit": "ou-xxxx-xxxxxxxx",
  "tags": {
    "Purpose": "DataZone",
    "ManagedBy": "AccountPoolFactory"
  }
}
```

**Process**:
1. Assume cross-account role in Org Admin account
2. Call Service Catalog `ProvisionProduct` API for Control Tower
3. Create DynamoDB record with state `PROVISIONING`
4. Return provisioning request ID

**Service Catalog Parameters**:
```python
{
    'ProductId': 'prod-xxxxxxxxxxxx',  # Control Tower Account Factory product
    'ProvisioningArtifactId': 'pa-xxxxxxxxxxxx',
    'ProvisionedProductName': account_name,
    'ProvisioningParameters': [
        {'Key': 'AccountEmail', 'Value': account_email},
        {'Key': 'AccountName', 'Value': account_name},
        {'Key': 'ManagedOrganizationalUnit', 'Value': ou_name},
        {'Key': 'SSOUserEmail', 'Value': sso_email},
        {'Key': 'SSOUserFirstName', 'Value': 'DataZone'},
        {'Key': 'SSOUserLastName', 'Value': 'Project'}
    ],
    'Tags': tags
}
```

### 3.4 Setup Orchestrator Lambda

**Function Name**: `SetupOrchestrator-{DomainId}`

**Trigger**: EventBridge rule matching Control Tower events

**Event Pattern**:
```json
{
  "source": ["aws.controltower"],
  "detail-type": ["AWS Service Event via CloudTrail"],
  "detail": {
    "eventName": ["CreateManagedAccount", "UpdateManagedAccount"],
    "serviceEventDetails": {
      "createManagedAccountStatus": {
        "state": ["SUCCEEDED"]
      }
    }
  }
}
```

**Process**:
1. Extract account ID from event
2. Update DynamoDB record state to `CONFIGURING`
3. Deploy CF3 StackSet to new account
4. Wait for StackSet deployment completion
5. Validate account setup
6. Update DynamoDB record state to `AVAILABLE`
7. Emit CloudWatch metrics

## 4. CloudFormation Templates

### 4.1 CF1: Organization Admin Setup

**Template Name**: `org-admin-setup.yaml`

**Resources**:
1. **Cross-Account IAM Role** (`AccountFactoryAccessRole`)
   - Trust policy: Domain account
   - Permissions: Service Catalog ProvisionProduct, Organizations read

2. **EventBridge Rule** (`AccountCreationEventRule`)
   - Pattern: Control Tower CreateManagedAccount events
   - Target: EventBridge event bus in Domain account

3. **EventBridge Event Bus Permission**
   - Allow Domain account to receive events

4. **CloudTrail** (if not exists)
   - Log Control Tower API calls

**Parameters**:
- `DomainAccountId`: AWS Account ID of Domain account
- `EventBusArn`: ARN of event bus in Domain account

**Outputs**:
- `CrossAccountRoleArn`: ARN of the cross-account role
- `EventRuleArn`: ARN of the EventBridge rule

### 4.2 CF2: Domain Account Setup

**Template Name**: `domain-account-setup.yaml`

**Resources**:

1. **DynamoDB Tables**
   - `AccountPool` table with GSIs
   - `AccountPoolConfig` table

2. **Lambda Functions**
   - Account Provider (with DataZone integration)
   - Pool Manager
   - Account Creator
   - Setup Orchestrator

3. **Lambda Execution Roles**
   - Least-privilege IAM roles for each function
   - Cross-account assume role permissions

4. **EventBridge Rules**
   - Pool monitoring (scheduled, every 5 minutes)
   - Control Tower event forwarding

5. **Step Functions State Machine**
   - Orchestrate account provisioning workflow
   - Handle retries and error states

6. **CloudWatch Dashboard**
   - Pool size metrics
   - Assignment rate
   - Provisioning duration
   - Error rates

7. **SNS Topics**
   - Pool alerts (low pool size, failures)
   - Operational notifications

8. **DataZone Custom Account Pool**
   - Register Account Provider Lambda with DataZone

**Parameters**:
- `DomainId`: DataZone domain ID
- `OrgAdminAccountId`: Org Admin account ID
- `OrgAdminRoleArn`: Cross-account role ARN from CF1
- `MinimumPoolSize`: Minimum accounts in pool (default: 5)
- `MaximumPoolSize`: Maximum accounts in pool (default: 20)
- `AccountNamePrefix`: Prefix for account names
- `AccountEmailDomain`: Email domain for accounts
- `OrganizationalUnitPath`: OU path for accounts
- `AlertEmail`: Email for SNS alerts

**Outputs**:
- `AccountPoolTableName`: DynamoDB table name
- `AccountProviderFunctionArn`: Lambda function ARN
- `PoolManagerFunctionArn`: Lambda function ARN
- `DashboardUrl`: CloudWatch dashboard URL

### 4.3 CF3: Project Account Setup (StackSet)

**Template Name**: `project-account-setup.yaml`

**Deployment**: StackSet with self-managed permissions

**Resources**:

1. **AWS RAM Resource Share Acceptance**
   - Accept DataZone domain resource share
   - Enable cross-account access

2. **DataZone Blueprint Configurations**
   - Enable configurable list of blueprints
   - Configure regional parameters (S3, VPC, Subnets)
   - Based on `enable_all_blueprints.yaml`

3. **IAM Roles**
   - `DataZoneProjectRole`: Assumed by DataZone for project operations
   - `ManageAccessRole`: For blueprint management
   - `ProvisioningRole`: For environment provisioning
   - Cross-account role for Domain account

4. **CloudTrail**
   - Account-level audit logging
   - S3 bucket for logs

5. **VPC and Networking** (optional)
   - VPC with public/private subnets
   - NAT Gateway
   - Security groups

6. **S3 Bucket**
   - For blueprint artifacts
   - Encryption enabled

7. **Account Tags**
   - Apply configurable tags

8. **Custom Resource**
   - Signal completion to Domain account
   - Update DynamoDB record

**Parameters**:
- `DomainId`: DataZone domain ID
- `DomainAccountId`: Domain account ID
- `DomainArn`: DataZone domain ARN
- `AccountPoolTableName`: DynamoDB table name
- `EnabledBlueprints`: Comma-separated list of blueprints
- `CreateVPC`: Boolean to create VPC
- `VPCCidr`: CIDR block for VPC
- `ProjectRoleName`: Name of project IAM role
- `ManageAccessRoleArn`: ARN for manage access role
- `ProvisioningRoleArn`: ARN for provisioning role

**Outputs**:
- `ProjectRoleArn`: ARN of the project role
- `VPCId`: VPC ID (if created)
- `SubnetIds`: Subnet IDs (if created)

## 5. Workflow Sequences

### 5.1 Account Provisioning Workflow

```
1. Pool Manager detects low pool size
   ↓
2. Pool Manager invokes Account Creator Lambda
   ↓
3. Account Creator:
   - Assumes role in Org Admin account
   - Calls Service Catalog ProvisionProduct
   - Creates DynamoDB record (state: PROVISIONING)
   ↓
4. Control Tower creates account (10-15 minutes)
   ↓
5. Control Tower emits CreateManagedAccount event
   ↓
6. EventBridge forwards event to Domain account
   ↓
7. Setup Orchestrator Lambda triggered:
   - Updates DynamoDB (state: CONFIGURING)
   - Deploys CF3 StackSet to new account
   ↓
8. CF3 StackSet deployment (2-5 minutes):
   - Accepts RAM resource share
   - Enables blueprints
   - Creates IAM roles
   - Sets up CloudTrail
   - Creates VPC (if configured)
   ↓
9. Custom Resource signals completion
   ↓
10. Setup Orchestrator:
    - Validates account setup
    - Updates DynamoDB (state: AVAILABLE)
    - Emits CloudWatch metrics
```

### 5.2 Account Assignment Workflow

```
1. User creates DataZone project
   ↓
2. DataZone invokes Account Provider Lambda
   ↓
3. Account Provider:
   - Queries DynamoDB for AVAILABLE account
   - Updates account state to ASSIGNED atomically
   - Records project mapping
   - Returns account details to DataZone
   ↓
4. DataZone configures project with account
   ↓
5. Account Provider triggers Pool Manager
   ↓
6. Pool Manager checks pool size and replenishes if needed
```

### 5.3 Error Handling Workflow

```
1. Account provisioning fails
   ↓
2. Setup Orchestrator detects failure
   ↓
3. Update DynamoDB (state: FAILED, increment RetryCount)
   ↓
4. If RetryCount < MaxRetries:
   - Wait with exponential backoff
   - Retry provisioning
   ↓
5. If RetryCount >= MaxRetries:
   - Send SNS alert
   - Mark account for manual intervention
   - Continue with other accounts
```

## 6. Security Design

### 6.1 IAM Roles and Permissions

**Account Creator Lambda Role**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::{OrgAdminAccountId}:role/AccountFactoryAccessRole"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/AccountPool-*"
    }
  ]
}
```

**Cross-Account Role (Org Admin)**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "servicecatalog:ProvisionProduct",
        "servicecatalog:DescribeProvisionedProduct",
        "servicecatalog:DescribeRecord"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "servicecatalog:ProductId": "{ControlTowerProductId}"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "organizations:DescribeAccount",
        "organizations:ListAccounts"
      ],
      "Resource": "*"
    }
  ]
}
```

### 6.2 Data Encryption

- **DynamoDB**: Encryption at rest using AWS managed keys
- **S3**: Server-side encryption (SSE-S3 or SSE-KMS)
- **Secrets Manager**: For sensitive configuration
- **CloudWatch Logs**: Encryption enabled

### 6.3 Network Security

- Lambda functions in VPC (optional)
- Security groups with least-privilege rules
- VPC endpoints for AWS services
- Private subnets for sensitive resources

## 7. Monitoring and Observability

### 7.1 CloudWatch Metrics

**Custom Metrics** (Namespace: `AccountPoolFactory`):
- `PoolSize`: Current number of AVAILABLE accounts
- `ProvisioningDuration`: Time to provision account
- `AssignmentRate`: Accounts assigned per hour
- `FailureRate`: Failed provisioning attempts
- `PoolUtilization`: Percentage of pool in use

**Dimensions**:
- `DomainId`: DataZone domain ID
- `State`: Account state
- `ErrorType`: Type of error (if applicable)

### 7.2 CloudWatch Alarms

1. **Pool Low Alarm**
   - Metric: `PoolSize`
   - Threshold: < `MinimumPoolSize`
   - Action: SNS notification

2. **Pool Empty Alarm**
   - Metric: `PoolSize`
   - Threshold: = 0
   - Action: SNS notification (critical)

3. **High Failure Rate Alarm**
   - Metric: `FailureRate`
   - Threshold: > 10% over 1 hour
   - Action: SNS notification

4. **Provisioning Duration Alarm**
   - Metric: `ProvisioningDuration`
   - Threshold: > 20 minutes
   - Action: SNS notification

### 7.3 CloudWatch Dashboard

**Widgets**:
1. Pool size over time (line graph)
2. Account states distribution (pie chart)
3. Assignment rate (line graph)
4. Provisioning duration (histogram)
5. Error rate (line graph)
6. Recent errors (log insights)

### 7.4 Logging Strategy

**Log Groups**:
- `/aws/lambda/AccountProvider-{DomainId}`
- `/aws/lambda/PoolManager-{DomainId}`
- `/aws/lambda/AccountCreator-{DomainId}`
- `/aws/lambda/SetupOrchestrator-{DomainId}`

**Log Format** (JSON):
```json
{
  "timestamp": "2024-01-15T10:00:00Z",
  "level": "INFO",
  "correlationId": "req_xxxxxxxxxxxxx",
  "component": "AccountProvider",
  "action": "GET_ACCOUNT",
  "accountId": "123456789012",
  "projectId": "prj_xxxxxxxxxxxxx",
  "duration": 245,
  "message": "Account assigned successfully"
}
```

**Correlation IDs**: Track requests across Lambda functions

## 8. Performance Considerations

### 8.1 Scalability

- **DynamoDB**: On-demand capacity mode for automatic scaling
- **Lambda**: Concurrent execution limit (default: 1000)
- **Control Tower**: Rate limit ~5 accounts per minute
- **StackSets**: Parallel deployment to multiple accounts

### 8.2 Optimization

- **Connection Pooling**: Reuse AWS SDK clients
- **Caching**: Cache configuration in Lambda memory
- **Batch Operations**: Process multiple accounts in parallel
- **Async Processing**: Use Step Functions for long-running workflows

### 8.3 Rate Limiting

- **Exponential Backoff**: For AWS API throttling
- **Jitter**: Randomize retry delays
- **Circuit Breaker**: Prevent cascading failures

## 9. Disaster Recovery

### 9.1 Backup Strategy

- **DynamoDB**: Point-in-time recovery enabled
- **Configuration**: Stored in Parameter Store with versioning
- **CloudFormation**: Templates in version control

### 9.2 Recovery Procedures

1. **Pool Corruption**: Restore DynamoDB from backup
2. **Lambda Failure**: Automatic retry with dead-letter queue
3. **StackSet Failure**: Manual rollback and retry
4. **Complete Failure**: Redeploy CF2 from template

## 10. Testing Strategy

### 10.1 Unit Tests

- Test each Lambda function independently
- Mock AWS SDK calls
- Test error handling paths
- Coverage target: >80%

### 10.2 Integration Tests

- Test end-to-end account provisioning
- Test DataZone integration
- Test pool replenishment
- Test error scenarios

### 10.3 Load Tests

- Simulate high project creation rate
- Test pool depletion and recovery
- Measure provisioning duration under load

## 11. Deployment Strategy

### 11.1 Deployment Order

1. Deploy CF1 to Org Admin account
2. Deploy CF2 to Domain account
3. CF3 is deployed automatically by Setup Orchestrator

### 11.2 Update Strategy

- **Blue/Green**: For Lambda functions
- **Rolling**: For StackSet updates
- **Canary**: For critical changes

### 11.3 Rollback Plan

- CloudFormation stack rollback
- DynamoDB point-in-time recovery
- Lambda version aliases

## 12. Cost Optimization

### 12.1 Cost Drivers

- AWS accounts (no direct cost, but resources within)
- Lambda invocations
- DynamoDB storage and requests
- CloudWatch logs and metrics
- StackSet operations

### 12.2 Cost Controls

- Set `MaximumPoolSize` appropriately
- Use DynamoDB on-demand pricing
- Set CloudWatch Logs retention
- Monitor unused accounts

## 13. Compliance and Governance

### 13.1 Audit Trail

- CloudTrail logs all API calls
- DynamoDB streams for change tracking
- EventBridge events for lifecycle tracking

### 13.2 Compliance Controls

- Service Control Policies (SCPs) on accounts
- AWS Config rules for compliance
- Automated compliance checks in CF3

## 14. Future Enhancements

### 14.1 Phase 2 Features

- Account recycling/reuse
- Multi-region support
- Custom account configurations per project type
- Cost allocation and chargeback
- Self-service portal for administrators

### 14.2 Integration Opportunities

- AWS Service Catalog for custom blueprints
- AWS Systems Manager for account configuration
- AWS Security Hub for security posture
- AWS Cost Explorer for cost tracking

## 15. Open Design Questions

1. Should we use Step Functions for the entire provisioning workflow?
2. How to handle account cleanup when projects are deleted?
3. Should we support multiple pool configurations for different project types?
4. How to handle Control Tower updates and account migrations?
5. Should we implement account warming (pre-configure resources)?
