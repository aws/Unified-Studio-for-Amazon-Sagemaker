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
  },
  "strategy": "control_tower"
}
```

**Architecture**: Strategy Pattern

The Account Creator Lambda implements a strategy pattern to support multiple account creation methods:

```python
class AccountCreatorStrategy(ABC):
    """Abstract base class for account creation strategies"""
    
    @abstractmethod
    def create_account(self, account_config: dict) -> dict:
        """Create account and return provisioning details"""
        pass
    
    @abstractmethod
    def get_provisioning_status(self, provisioning_id: str) -> dict:
        """Check status of account provisioning"""
        pass
    
    @abstractmethod
    def get_account_id(self, provisioning_id: str) -> str:
        """Get account ID from provisioning request"""
        pass
```

#### Strategy 1: Control Tower Account Factory

**Class**: `ControlTowerStrategy`

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

**Event Handling**: Listens for Control Tower CreateManagedAccount/UpdateManagedAccount events

**Provisioning Time**: 10-15 minutes

#### Strategy 2: AWS Organizations API

**Class**: `OrganizationsApiStrategy`

**Process**:
1. Assume cross-account role in Org Admin account (if different account)
2. Call Organizations `CreateAccount` API directly
3. Create DynamoDB record with state `PROVISIONING`
4. Return account creation request ID

**Organizations API Parameters**:
```python
{
    'Email': account_email,
    'AccountName': account_name,
    'RoleName': 'OrganizationAccountAccessRole',  # Configurable
    'IamUserAccessToBilling': 'ALLOW',  # Configurable
    'Tags': [
        {'Key': k, 'Value': v} for k, v in tags.items()
    ]
}
```

**Post-Creation Steps**:
1. Wait for account creation to complete (poll `DescribeCreateAccountStatus`)
2. Move account to target OU using `MoveAccount` API
3. Emit custom event to trigger Setup Orchestrator

**Event Handling**: Polls Organizations API for status, emits custom EventBridge event when complete

**Provisioning Time**: 5-8 minutes

**Advantages**:
- No Control Tower dependency
- Faster provisioning
- Simpler architecture
- Lower cost

**Disadvantages**:
- No automatic Control Tower guardrails
- Must manually configure baseline security
- No SSO integration
- Must implement own governance

#### Strategy Selection

The Lambda function selects the strategy based on configuration:

```python
def get_strategy(strategy_name: str) -> AccountCreatorStrategy:
    """Factory method to get account creation strategy"""
    strategies = {
        'control_tower': ControlTowerStrategy,
        'organizations_api': OrganizationsApiStrategy,
        # Future strategies
        'manual_pool': ManualPoolStrategy,
        'byoa': BringYourOwnAccountStrategy
    }
    
    strategy_class = strategies.get(strategy_name)
    if not strategy_class:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    
    return strategy_class()
```

**Configuration**:
```python
# Read from DynamoDB config table or environment variable
strategy_name = os.environ.get('ACCOUNT_CREATION_STRATEGY', 'control_tower')
strategy = get_strategy(strategy_name)

# Create account using selected strategy
result = strategy.create_account(account_config)
```

### 3.4 Setup Orchestrator Lambda

**Function Name**: `SetupOrchestrator-{DomainId}`

**Trigger**: EventBridge rule matching Control Tower events or custom events from Organizations API

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

**Orchestration Process**:

The Setup Orchestrator Lambda coordinates the complete account setup workflow after account creation. This is a critical component that ensures accounts are fully configured before being marked as AVAILABLE in the pool.

**Step 1: Initialize Setup**
```python
def handler(event, context):
    # Extract account details from event
    account_id = extract_account_id(event)
    account_name = extract_account_name(event)
    
    # Update DynamoDB state
    update_account_state(account_id, 'CONFIGURING', {
        'SetupStartedAt': datetime.utcnow().isoformat(),
        'SetupSteps': []
    })
    
    # Start orchestration
    orchestrate_setup(account_id, account_name)
```

**Step 2: Create RAM Share for Domain**
```python
def create_ram_share(account_id, domain_arn):
    """
    Create AWS RAM resource share to share DataZone domain with new account.
    
    CRITICAL: Must use permission ARN with portal access:
    arn:aws:ram::aws:permission/AWSRAMPermissionsAmazonDatazoneDomainExtendedServiceWithPortalAccess
    
    Note: Organization-level sharing is NOT supported for DataZone domains.
    Must create one RAM share per account.
    """
    ram_client = boto3.client('ram')
    
    share_name = f"DataZoneDomain-{account_id}"
    
    response = ram_client.create_resource_share(
        name=share_name,
        resourceArns=[domain_arn],
        principals=[account_id],
        permissionArns=[
            'arn:aws:ram::aws:permission/AWSRAMPermissionsAmazonDatazoneDomainExtendedServiceWithPortalAccess'
        ],
        allowExternalPrincipals=False,  # Same org only
        tags=[
            {'key': 'Purpose', 'value': 'DataZoneDomainSharing'},
            {'key': 'AccountId', 'value': account_id}
        ]
    )
    
    share_arn = response['resourceShare']['resourceShareArn']
    
    # Wait for share to become ACTIVE
    wait_for_ram_share_active(share_arn)
    
    return share_arn
```

**Step 3: Verify Domain Visibility**
```python
def verify_domain_visibility(account_id, domain_id, max_retries=10):
    """
    Verify that DataZone domain is visible in the new account.
    
    Within same organization, RAM share is automatically accepted.
    However, it may take a few seconds for domain to become visible.
    """
    # Assume role in new account
    sts_client = boto3.client('sts')
    assumed_role = sts_client.assume_role(
        RoleArn=f'arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole',
        RoleSessionName='DomainVerification'
    )
    
    # Create DataZone client with assumed credentials
    datazone_client = boto3.client(
        'datazone',
        aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
        aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
        aws_session_token=assumed_role['Credentials']['SessionToken']
    )
    
    # Retry with exponential backoff
    for attempt in range(max_retries):
        try:
            response = datazone_client.list_domains()
            
            # Check if our domain is in the list
            for domain in response.get('items', []):
                if domain['id'] == domain_id:
                    if domain['status'] == 'AVAILABLE':
                        logger.info(f"Domain {domain_id} is visible and available in account {account_id}")
                        return True
                    else:
                        logger.warning(f"Domain {domain_id} found but status is {domain['status']}")
            
            # Domain not found yet, wait and retry
            wait_time = 2 ** attempt  # Exponential backoff
            logger.info(f"Domain not visible yet, waiting {wait_time}s before retry {attempt+1}/{max_retries}")
            time.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"Error checking domain visibility: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    
    raise Exception(f"Domain {domain_id} not visible in account {account_id} after {max_retries} retries")
```

**Step 4: Deploy CF3 StackSet**
```python
def deploy_stackset(account_id, account_name):
    """
    Deploy CF3 StackSet to new account for baseline configuration.
    """
    cfn_client = boto3.client('cloudformation')
    
    # Deploy StackSet instance
    response = cfn_client.create_stack_instances(
        StackSetName='AccountPoolFactory-ProjectAccountSetup',
        Accounts=[account_id],
        Regions=[os.environ['AWS_REGION']],
        ParameterOverrides=[
            {'ParameterKey': 'AccountName', 'ParameterValue': account_name},
            {'ParameterKey': 'DomainId', 'ParameterValue': os.environ['DOMAIN_ID']},
            {'ParameterKey': 'DomainAccountId', 'ParameterValue': os.environ['DOMAIN_ACCOUNT_ID']}
        ],
        OperationPreferences={
            'MaxConcurrentCount': 1,
            'FailureToleranceCount': 0
        }
    )
    
    operation_id = response['OperationId']
    
    # Wait for deployment to complete
    wait_for_stackset_operation(operation_id)
    
    return operation_id
```

**Step 5: Enable Blueprints**
```python
def enable_blueprints(account_id, domain_id, blueprints_config):
    """
    Enable DataZone blueprints in the new account.
    
    MUST be performed AFTER domain sharing is complete and domain is visible.
    """
    # Assume role in new account
    sts_client = boto3.client('sts')
    assumed_role = sts_client.assume_role(
        RoleArn=f'arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole',
        RoleSessionName='BlueprintEnablement'
    )
    
    # Create DataZone client with assumed credentials
    datazone_client = boto3.client(
        'datazone',
        aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
        aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
        aws_session_token=assumed_role['Credentials']['SessionToken']
    )
    
    enabled_blueprints = []
    
    for blueprint_config in blueprints_config:
        try:
            response = datazone_client.create_environment_blueprint_configuration(
                domainIdentifier=domain_id,
                environmentBlueprintIdentifier=blueprint_config['blueprint_id'],
                enabledRegions=[os.environ['AWS_REGION']],
                manageAccessRoleArn=blueprint_config['manage_access_role_arn'],
                provisioningRoleArn=blueprint_config['provisioning_role_arn'],
                regionalParameters={
                    os.environ['AWS_REGION']: {
                        'S3Location': blueprint_config.get('s3_location'),
                        'VpcId': blueprint_config.get('vpc_id'),
                        'SubnetIds': blueprint_config.get('subnet_ids', [])
                    }
                }
            )
            
            enabled_blueprints.append(blueprint_config['blueprint_id'])
            logger.info(f"Enabled blueprint {blueprint_config['blueprint_id']} in account {account_id}")
            
        except Exception as e:
            logger.error(f"Failed to enable blueprint {blueprint_config['blueprint_id']}: {e}")
            # Continue with other blueprints
    
    return enabled_blueprints
```

**Step 6: Create Policy Grants**
```python
def create_policy_grants(domain_id, account_id, enabled_blueprints):
    """
    Create policy grants for blueprints and project profiles.
    Performed in Domain account.
    """
    datazone_client = boto3.client('datazone')
    
    grants_created = []
    
    # Grant CREATE_ENVIRONMENT_FROM_BLUEPRINT for each enabled blueprint
    for blueprint_id in enabled_blueprints:
        try:
            response = datazone_client.create_policy_grant(
                domainIdentifier=domain_id,
                principal={
                    'account': account_id
                },
                policyType='CREATE_ENVIRONMENT_FROM_BLUEPRINT',
                detail={
                    'createEnvironmentFromBlueprint': {
                        'blueprintIdentifier': blueprint_id
                    }
                }
            )
            
            grants_created.append(response['policyGrantId'])
            
        except Exception as e:
            logger.error(f"Failed to create policy grant for blueprint {blueprint_id}: {e}")
    
    return grants_created
```

**Step 7: Validate and Mark Available**
```python
def complete_setup(account_id):
    """
    Validate all setup steps and mark account as AVAILABLE.
    """
    # Validate all resources
    validation_results = {
        'ram_share': validate_ram_share(account_id),
        'domain_visibility': validate_domain_visibility(account_id),
        'stackset': validate_stackset_deployment(account_id),
        'blueprints': validate_blueprints_enabled(account_id),
        'policy_grants': validate_policy_grants(account_id)
    }
    
    # Check if all validations passed
    if all(validation_results.values()):
        # Update DynamoDB state to AVAILABLE
        update_account_state(account_id, 'AVAILABLE', {
            'SetupCompletedAt': datetime.utcnow().isoformat(),
            'ValidationResults': validation_results
        })
        
        # Emit CloudWatch metrics
        emit_metric('AccountSetupSuccess', 1, account_id)
        
        # Send SNS notification
        send_notification(f"Account {account_id} is now AVAILABLE in the pool")
        
        logger.info(f"Account {account_id} setup completed successfully")
        
    else:
        # Mark as FAILED
        update_account_state(account_id, 'FAILED', {
            'SetupFailedAt': datetime.utcnow().isoformat(),
            'ValidationResults': validation_results,
            'FailureReason': 'Validation failed'
        })
        
        # Send alert
        send_alert(f"Account {account_id} setup failed validation: {validation_results}")
        
        raise Exception(f"Account setup validation failed: {validation_results}")
```

**Complete Orchestration Flow**:
```python
def orchestrate_setup(account_id, account_name):
    """
    Orchestrate complete account setup workflow.
    """
    try:
        # Step 1: Create RAM share
        logger.info(f"Step 1: Creating RAM share for account {account_id}")
        ram_share_arn = create_ram_share(account_id, os.environ['DOMAIN_ARN'])
        update_setup_progress(account_id, 'ram_share_created', ram_share_arn)
        
        # Step 2: Verify domain visibility
        logger.info(f"Step 2: Verifying domain visibility in account {account_id}")
        verify_domain_visibility(account_id, os.environ['DOMAIN_ID'])
        update_setup_progress(account_id, 'domain_visible', True)
        
        # Step 3: Deploy CF3 StackSet
        logger.info(f"Step 3: Deploying CF3 StackSet to account {account_id}")
        operation_id = deploy_stackset(account_id, account_name)
        update_setup_progress(account_id, 'stackset_deployed', operation_id)
        
        # Step 4: Enable blueprints
        logger.info(f"Step 4: Enabling blueprints in account {account_id}")
        blueprints_config = get_blueprints_config()
        enabled_blueprints = enable_blueprints(account_id, os.environ['DOMAIN_ID'], blueprints_config)
        update_setup_progress(account_id, 'blueprints_enabled', enabled_blueprints)
        
        # Step 5: Create policy grants
        logger.info(f"Step 5: Creating policy grants for account {account_id}")
        grants_created = create_policy_grants(os.environ['DOMAIN_ID'], account_id, enabled_blueprints)
        update_setup_progress(account_id, 'policy_grants_created', grants_created)
        
        # Step 6: Validate and mark available
        logger.info(f"Step 6: Validating setup for account {account_id}")
        complete_setup(account_id)
        
    except Exception as e:
        logger.error(f"Account setup failed for {account_id}: {e}")
        
        # Update DynamoDB with error
        update_account_state(account_id, 'FAILED', {
            'SetupFailedAt': datetime.utcnow().isoformat(),
            'LastError': str(e),
            'RetryCount': get_retry_count(account_id) + 1
        })
        
        # Check if should retry
        if should_retry(account_id):
            logger.info(f"Scheduling retry for account {account_id}")
            schedule_retry(account_id)
        else:
            logger.error(f"Max retries exceeded for account {account_id}")
            send_alert(f"Account {account_id} setup failed after max retries: {e}")
        
        raise
```

**Error Handling**:
- Each step includes retry logic with exponential backoff
- Failed steps are logged with detailed error information
- Account marked as FAILED if max retries exceeded
- SNS alert sent for manual intervention
- Partial setup can be resumed from last successful step
- Setup progress tracked in DynamoDB for debugging

**Monitoring**:
- CloudWatch metrics for each setup step
- Detailed logging with correlation IDs
- Setup duration tracking
- Success/failure rates per step

## 4. CloudFormation Templates

### 4.1 CF1: Organization Admin Setup

**Template Name**: `org-admin-setup.yaml`

**Purpose**: Configure the Organization Admin account to support both Control Tower and Organizations API account creation strategies.

**Resources**:

1. **Cross-Account IAM Role** (`AccountFactoryAccessRole`)
   - Trust policy: Domain account
   - Permissions for Strategy 1 (Control Tower):
     - Service Catalog ProvisionProduct, DescribeProvisionedProduct, DescribeRecord
     - Organizations read operations
     - SSO read operations
   - Permissions for Strategy 2 (Organizations API):
     - Organizations CreateAccount, DescribeCreateAccountStatus
     - Organizations MoveAccount (to move to target OU)
     - Organizations TagResource
     - Organizations read operations

2. **EventBridge Rule** (`AccountCreationEventRule`)
   - Pattern for Strategy 1: Control Tower CreateManagedAccount/UpdateManagedAccount events
   - Pattern for Strategy 2: Custom events from Organizations API poller
   - Target: EventBridge event bus in Domain account

3. **EventBridge Event Bus** (`AccountLifecycleEventBus`)
   - Receives account creation events from both strategies
   - Forwards events to Domain account

4. **EventBridge Event Bus Permission**
   - Allow Domain account to receive events

5. **CloudTrail** (if not exists)
   - Log Control Tower and Organizations API calls

6. **StackSet Administration Role** (`StackSetAdministrationRole`)
   - Allows CloudFormation service to deploy StackSets
   - Assumes AWSControlTowerExecution role in target accounts

7. **StackSet Deployment Role** (`StackSetDeploymentRole`)
   - Allows Domain account to deploy approved StackSet instances
   - Restricted to StackSets with specific name prefix
   - Explicit DENY on creating/modifying StackSets

**Parameters**:
- `DomainAccountId`: AWS Account ID of Domain account
- `EventBusArn`: ARN of event bus in Domain account
- `AccountCreationStrategy`: Strategy to use (control_tower, organizations_api, both)
- `ControlTowerProductId`: Service Catalog Product ID (required for Strategy 1)
- `ControlTowerArtifactId`: Provisioning Artifact ID (optional for Strategy 1)

**Outputs**:
- `CrossAccountRoleArn`: ARN of the cross-account role
- `EventRuleArn`: ARN of the EventBridge rule
- `EventBusArn`: ARN of the event bus
- `StackSetAdminRoleArn`: ARN of StackSet administration role
- `StackSetDeploymentRoleArn`: ARN of StackSet deployment role

**Strategy-Specific Configuration**:

The template uses CloudFormation conditions to enable/disable resources based on the selected strategy:

```yaml
Conditions:
  UseControlTower: !Or
    - !Equals [!Ref AccountCreationStrategy, 'control_tower']
    - !Equals [!Ref AccountCreationStrategy, 'both']
  
  UseOrganizationsApi: !Or
    - !Equals [!Ref AccountCreationStrategy, 'organizations_api']
    - !Equals [!Ref AccountCreationStrategy, 'both']
```

**IAM Policy for Strategy 1 (Control Tower)**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ServiceCatalogAccountFactory",
      "Effect": "Allow",
      "Action": [
        "servicecatalog:ProvisionProduct",
        "servicecatalog:DescribeProvisionedProduct",
        "servicecatalog:DescribeRecord",
        "servicecatalog:TerminateProvisionedProduct"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "servicecatalog:productType": "CONTROL_TOWER_ACCOUNT"
        }
      }
    }
  ]
}
```

**IAM Policy for Strategy 2 (Organizations API)**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "OrganizationsAccountCreation",
      "Effect": "Allow",
      "Action": [
        "organizations:CreateAccount",
        "organizations:DescribeCreateAccountStatus",
        "organizations:MoveAccount",
        "organizations:TagResource",
        "organizations:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "OrganizationsRead",
      "Effect": "Allow",
      "Action": [
        "organizations:DescribeOrganization",
        "organizations:DescribeOrganizationalUnit",
        "organizations:DescribeAccount",
        "organizations:ListAccounts",
        "organizations:ListAccountsForParent",
        "organizations:ListOrganizationalUnitsForParent",
        "organizations:ListRoots"
      ],
      "Resource": "*"
    }
  ]
}
```

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
   - Calls Service Catalog ProvisionProduct (Control Tower) OR Organizations CreateAccount API
   - Creates DynamoDB record (state: PROVISIONING)
   ↓
4. Control Tower/Organizations creates account (5-15 minutes)
   ↓
5. Account creation event emitted
   ↓
6. EventBridge forwards event to Domain account
   ↓
7. Setup Orchestrator Lambda triggered:
   - Updates DynamoDB (state: CONFIGURING)
   
   Step 1: Create RAM Share (Domain Account)
   - Create AWS RAM resource share
   - Associate domain ARN as resource
   - Associate new account ID as principal
   - Use permission: AWSRAMPermissionsAmazonDatazoneDomainExtendedServiceWithPortalAccess
   - Wait for share to become ACTIVE
   ↓
   Step 2: Verify Domain Visibility (New Account)
   - Assume role in new account
   - Call DataZone ListDomains API
   - Verify domain is visible and status is AVAILABLE
   - Retry with exponential backoff if not yet visible (within same org, auto-accepted)
   ↓
   Step 3: Deploy CF3 StackSet (New Account)
   - Deploy baseline IAM roles and security configuration
   - Wait for StackSet deployment to complete (2-5 minutes)
   - Verify all resources created successfully
   ↓
   Step 4: Enable Blueprints (New Account)
   - For each configured blueprint:
     - Call DataZone EnableBlueprint API
     - Provide required parameters (roles, VPC, subnets)
     - Verify blueprint enabled successfully
   ↓
   Step 5: Create Policy Grants (Domain Account)
   - Grant CREATE_ENVIRONMENT_FROM_BLUEPRINT permissions
   - Grant CREATE_PROJECT_FROM_PROJECT_PROFILE permissions
   ↓
   Step 6: Validate and Mark Available
   - Validate all setup steps completed
   - Update DynamoDB (state: AVAILABLE)
   - Emit CloudWatch metrics
   - Send SNS notification
```

**Total Time**: 7-20 minutes (depending on account creation strategy)
- Control Tower: 10-15 minutes account creation + 2-5 minutes setup
- Organizations API: 5-8 minutes account creation + 2-5 minutes setup

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
