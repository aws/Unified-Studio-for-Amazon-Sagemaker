# Requirements Document: Account Pool Factory Automation

## Introduction

The Account Pool Factory automation consists of two Lambda functions that work together to maintain a pool of ready-to-use AWS accounts for DataZone projects:

1. **Pool Manager Lambda**: Monitors account pool size, triggers account creation and replenishment, and manages account lifecycle (creation to deletion)
2. **Setup Orchestrator Lambda**: Automates the complete 6-step setup workflow for individual accounts (VPC, IAM, S3, blueprints, policy grants, RAM sharing)

This automation eliminates manual intervention by maintaining a shadow pool of pre-configured accounts, ensuring fast project creation times regardless of the 10-12 minute account setup duration. The system uses event-driven replenishment triggered by CloudFormation stack events in project accounts, and defaults to deleting accounts when projects are removed for cost optimization and clean state management.

## Glossary

- **Pool_Manager**: Lambda function that monitors pool size, triggers replenishment, and manages account lifecycle
- **Setup_Orchestrator**: Lambda function that coordinates account setup workflow for a single account
- **Account_Pool**: Collection of AWS accounts available for DataZone project assignment
- **Account_State**: Current status of account (AVAILABLE, ASSIGNED, SETTING_UP, FAILED, DELETING)
- **Domain_Account**: AWS account where DataZone domain is deployed (994753223772)
- **Project_Account**: AWS account assigned to a DataZone project from the account pool
- **Blueprint**: DataZone environment template (e.g., Tooling, DataLake, RedshiftServerless)
- **Policy_Grant**: DataZone authorization that allows projects to create environments from blueprints
- **RAM_Share**: AWS Resource Access Manager share for cross-account domain access
- **Setup_State**: Current progress of account setup (PENDING, IN_PROGRESS, COMPLETED, FAILED)
- **CloudFormation_Stack**: AWS infrastructure deployment unit
- **StackSet**: CloudFormation template deployed across multiple accounts and includes EventBridge rules
- **VPC**: Virtual Private Cloud with 3 private subnets across 3 availability zones
- **ManageAccessRole**: IAM role for DataZone to manage Lake Formation and Glue resources
- **ProvisioningRole**: IAM role for DataZone to provision environment resources
- **Blueprint_Artifact_Bucket**: S3 bucket for storing blueprint configuration artifacts
- **EventBridge_Event**: Account lifecycle event triggering orchestration
- **EventBridge_Rule**: Rule deployed to project accounts to forward CloudFormation events to central bus
- **Central_Event_Bus**: EventBridge bus in domain account receiving events from all project accounts
- **DynamoDB_Table**: State tracking table for account setup progress and pool inventory
- **SNS_Topic**: Notification channel for setup failures requiring manual intervention
- **Reclaim_Strategy**: Configuration determining account fate after project deletion (DELETE or REUSE)
- **Minimum_Pool_Size**: Threshold triggering account replenishment (e.g., 5 accounts)
- **Target_Pool_Size**: Desired pool size after replenishment (e.g., 10 accounts)
- **Max_Concurrent_Setups**: Maximum number of accounts being set up simultaneously (e.g., 3)

## Requirements

## Pool Manager Lambda Requirements

### Requirement PM-1: EventBridge Rules Deployment to Project Accounts

**User Story:** As a domain administrator, I want EventBridge rules automatically deployed to project accounts, so that CloudFormation stack events are forwarded to the central event bus for pool management.

#### Acceptance Criteria

1. THE Pool_Manager SHALL deploy EventBridge_Rule resources to each Project_Account via StackSet
2. THE EventBridge_Rule SHALL monitor CloudFormation stack events with source aws.cloudformation and detail-type "CloudFormation Stack Status Change"
3. THE EventBridge_Rule SHALL filter for stack names with prefix "DataZone-"
4. THE EventBridge_Rule SHALL forward matching events to Central_Event_Bus in Domain_Account
5. THE EventBridge_Rule SHALL include IAM role with permissions to put events on Central_Event_Bus
6. THE StackSet SHALL be deployed during account setup by Setup_Orchestrator after VPC deployment completes
7. IF EventBridge_Rule deployment fails, THEN THE Setup_Orchestrator SHALL retry up to 3 times with exponential backoff starting at 30 seconds

### Requirement PM-2: Account Assignment Detection

**User Story:** As a domain administrator, I want the pool manager to detect when accounts are assigned to projects, so that pool replenishment is triggered immediately.

#### Acceptance Criteria

1. WHEN a CloudFormation stack event is received with status CREATE_IN_PROGRESS and stack name prefix "DataZone-", THE Pool_Manager SHALL extract the account ID from the event
2. THE Pool_Manager SHALL query DynamoDB_Table to verify the account exists in the pool with state AVAILABLE
3. WHEN the account is verified, THE Pool_Manager SHALL update the account state to ASSIGNED with timestamp
4. THE Pool_Manager SHALL record the project stack name and creation timestamp in DynamoDB_Table
5. THE Pool_Manager SHALL publish CloudWatch metric AccountAssigned with dimension AccountId
6. IF the account is not found in DynamoDB_Table, THEN THE Pool_Manager SHALL log a warning and continue without error
7. WHEN account state is updated to ASSIGNED, THE Pool_Manager SHALL trigger pool size check and replenishment

### Requirement PM-3: Pool Size Monitoring and Replenishment

**User Story:** As a domain administrator, I want the pool manager to maintain minimum pool size, so that accounts are always available for new projects.

#### Acceptance Criteria

1. WHEN an account is marked ASSIGNED, THE Pool_Manager SHALL query DynamoDB_Table to count accounts with state AVAILABLE
2. THE Pool_Manager SHALL read Minimum_Pool_Size from SSM Parameter Store at path /AccountPoolFactory/PoolManager/MinimumPoolSize
3. THE Pool_Manager SHALL read Target_Pool_Size from SSM Parameter Store at path /AccountPoolFactory/PoolManager/TargetPoolSize
4. IF available account count is less than Minimum_Pool_Size, THEN THE Pool_Manager SHALL calculate replenishment quantity as (Target_Pool_Size - available_count)
5. THE Pool_Manager SHALL read Max_Concurrent_Setups from SSM Parameter Store at path /AccountPoolFactory/PoolManager/MaxConcurrentSetups
6. THE Pool_Manager SHALL query DynamoDB_Table to count accounts with state SETTING_UP
7. THE Pool_Manager SHALL limit new account creation to (Max_Concurrent_Setups - current_setting_up_count)
8. THE Pool_Manager SHALL publish CloudWatch metric PoolReplenishmentTriggered with dimensions AvailableCount and RequestedCount

### Requirement PM-4: Parallel Account Creation

**User Story:** As a domain administrator, I want multiple accounts created in parallel, so that pool replenishment completes quickly.

#### Acceptance Criteria

1. WHEN replenishment is triggered, THE Pool_Manager SHALL create N accounts in parallel where N is the calculated replenishment quantity
2. THE Pool_Manager SHALL use AWS Organizations CreateAccount API for each account
3. THE Pool_Manager SHALL generate unique email addresses using format ${EmailPrefix}+${Timestamp}-${Index}@${EmailDomain}
4. THE Pool_Manager SHALL generate unique account names using format ${NamePrefix}-${Timestamp}-${Index}
5. THE Pool_Manager SHALL wait for all CreateAccount operations to return request IDs (not completion)
6. THE Pool_Manager SHALL create DynamoDB_Table records for each account with state SETTING_UP and creation request ID
7. THE Pool_Manager SHALL invoke Setup_Orchestrator asynchronously for each account with account ID and request ID
8. THE Pool_Manager SHALL publish CloudWatch metric AccountCreationStarted with dimension Count

### Requirement PM-5: Account Deletion Detection

**User Story:** As a domain administrator, I want the pool manager to detect when projects are deleted, so that accounts can be reclaimed or deleted.

#### Acceptance Criteria

1. WHEN a CloudFormation stack event is received with status DELETE_COMPLETE and stack name prefix "DataZone-", THE Pool_Manager SHALL extract the account ID from the event
2. THE Pool_Manager SHALL query DynamoDB_Table to retrieve the account record with state ASSIGNED
3. THE Pool_Manager SHALL assume role in Project_Account to list all CloudFormation stacks with name prefix "DataZone-"
4. IF no DataZone stacks remain in the account, THEN THE Pool_Manager SHALL proceed with account reclamation
5. IF DataZone stacks still exist in the account, THEN THE Pool_Manager SHALL log a message and wait for additional DELETE_COMPLETE events
6. THE Pool_Manager SHALL publish CloudWatch metric StackDeleted with dimensions AccountId and StackName
7. THE Pool_Manager SHALL update DynamoDB_Table record with last stack deletion timestamp

### Requirement PM-6: Account Reclamation Strategy - DELETE (Default)

**User Story:** As a domain administrator, I want accounts automatically deleted after project removal, so that costs are minimized and state is clean.

#### Acceptance Criteria

1. WHEN all DataZone stacks are deleted from an account, THE Pool_Manager SHALL read Reclaim_Strategy from SSM Parameter Store at path /AccountPoolFactory/PoolManager/ReclaimStrategy
2. IF Reclaim_Strategy is DELETE or not set, THEN THE Pool_Manager SHALL update account state to DELETING in DynamoDB_Table
3. THE Pool_Manager SHALL use AWS Organizations CloseAccount API to close the account
4. THE Pool_Manager SHALL wait for account closure confirmation with timeout of 5 minutes
5. WHEN account closure completes, THE Pool_Manager SHALL delete the account record from DynamoDB_Table
6. THE Pool_Manager SHALL publish CloudWatch metric AccountDeleted with dimension AccountId
7. IF account closure fails, THEN THE Pool_Manager SHALL mark account state as FAILED and send SNS notification

### Requirement PM-7: Account Reclamation Strategy - REUSE (Optional)

**User Story:** As a domain administrator, I want the option to reuse accounts after project removal, so that account creation limits are not exceeded.

#### Acceptance Criteria

1. IF Reclaim_Strategy is REUSE, THEN THE Pool_Manager SHALL update account state to CLEANING in DynamoDB_Table
2. THE Pool_Manager SHALL invoke Setup_Orchestrator with cleanup mode enabled
3. THE Setup_Orchestrator SHALL delete all CloudFormation stacks in the account
4. THE Setup_Orchestrator SHALL delete all S3 buckets in the account
5. THE Setup_Orchestrator SHALL delete all IAM roles created by DataZone
6. WHEN cleanup completes successfully, THE Pool_Manager SHALL update account state to AVAILABLE
7. IF cleanup fails, THEN THE Pool_Manager SHALL mark account state as FAILED and send SNS notification

### Requirement PM-8: Pool Manager CloudWatch Metrics

**User Story:** As a domain administrator, I want CloudWatch metrics published for pool operations, so that I can monitor pool health and performance.

#### Acceptance Criteria

1. THE Pool_Manager SHALL publish metric AvailableAccountCount every time pool size is checked
2. THE Pool_Manager SHALL publish metric AssignedAccountCount every time an account is assigned
3. THE Pool_Manager SHALL publish metric SettingUpAccountCount every time replenishment is triggered
4. THE Pool_Manager SHALL publish metric ReplenishmentDuration when replenishment completes
5. THE Pool_Manager SHALL publish metric AccountLifecycleDuration when accounts are deleted or reused
6. THE Pool_Manager SHALL publish all metrics to namespace AccountPoolFactory/PoolManager
7. THE Pool_Manager SHALL include dimensions AccountId, Operation, and Status where applicable

### Requirement PM-9: Pool Manager Error Handling

**User Story:** As a domain administrator, I want SNS notifications sent for pool management failures, so that I can manually intervene when automation fails.

#### Acceptance Criteria

1. WHEN account creation fails, THE Pool_Manager SHALL publish message to SNS_Topic with subject "Account Creation Failed"
2. WHEN account deletion fails, THE Pool_Manager SHALL publish message to SNS_Topic with subject "Account Deletion Failed"
3. WHEN pool size drops to zero, THE Pool_Manager SHALL publish message to SNS_Topic with subject "Account Pool Depleted"
4. THE Pool_Manager SHALL include account ID, error message, and CloudWatch Logs link in SNS message body
5. THE Pool_Manager SHALL include current pool statistics in SNS message body
6. IF SNS publish fails, THEN THE Pool_Manager SHALL log the error but continue execution
7. THE Pool_Manager SHALL publish CloudWatch metric PoolManagerError with dimensions ErrorType and Operation

### Requirement PM-10: Detailed Failure Tracking and Reporting

**User Story:** As a domain administrator, I want detailed failure information captured for failed account setups, so that I can quickly diagnose and resolve issues.

#### Acceptance Criteria

1. WHEN any setup step fails, THE Setup_Orchestrator SHALL update DynamoDB_Table with detailed error information including failed step name, error message, error code, and stack trace
2. THE Setup_Orchestrator SHALL record the CloudFormation stack name, stack ID, and stack status for failed stack deployments
3. THE Setup_Orchestrator SHALL capture CloudFormation stack events for the failed stack and store the last 10 events in DynamoDB_Table
4. THE Setup_Orchestrator SHALL record the specific resource that failed within the CloudFormation stack if available
5. THE Setup_Orchestrator SHALL include retry attempt number and total retry count in the error record
6. THE Setup_Orchestrator SHALL update account state to FAILED in DynamoDB_Table with timestamp of failure
7. THE Setup_Orchestrator SHALL publish CloudWatch metric SetupStepFailed with dimensions AccountId, StepName, ErrorType, and RetryAttempt

### Requirement PM-11: Retry Configuration and Exhaustion Handling

**User Story:** As a domain administrator, I want configurable retry logic for failed setup steps, so that transient failures are automatically recovered.

#### Acceptance Criteria

1. THE Setup_Orchestrator SHALL read retry configuration from SSM Parameter Store at path /AccountPoolFactory/SetupOrchestrator/RetryConfig
2. THE retry configuration SHALL include max_retries (default 3), initial_backoff_seconds (default 30), and backoff_multiplier (default 2)
3. WHEN a setup step fails, THE Setup_Orchestrator SHALL retry the step up to max_retries times with exponential backoff
4. THE Setup_Orchestrator SHALL calculate backoff delay as initial_backoff_seconds * (backoff_multiplier ^ retry_attempt)
5. THE Setup_Orchestrator SHALL record each retry attempt in DynamoDB_Table with timestamp and error message
6. WHEN all retries are exhausted, THE Setup_Orchestrator SHALL mark the account state as FAILED with retry_exhausted flag set to true
7. THE Setup_Orchestrator SHALL publish CloudWatch metric RetryExhausted with dimensions AccountId and FailedStep

### Requirement PM-12: Replenishment Blocking on Failed Accounts

**User Story:** As a domain administrator, I want pool replenishment blocked when failed accounts exist, so that I can resolve errors before creating more accounts.

#### Acceptance Criteria

1. WHEN replenishment is triggered, THE Pool_Manager SHALL query DynamoDB_Table to count accounts with state FAILED
2. IF any accounts have state FAILED, THEN THE Pool_Manager SHALL NOT create new accounts
3. THE Pool_Manager SHALL publish CloudWatch metric ReplenishmentBlocked with dimension FailedAccountCount
4. THE Pool_Manager SHALL publish SNS notification with subject "Pool Replenishment Blocked - Failed Accounts Require Attention"
5. THE SNS notification SHALL include list of failed account IDs, failed step names, and error messages
6. THE SNS notification SHALL include instructions to delete failed accounts to unblock replenishment
7. THE Pool_Manager SHALL log warning message indicating replenishment is blocked and listing failed account IDs

### Requirement PM-13: Failed Account Deletion Requirement

**User Story:** As a domain administrator, I want failed accounts to be manually deleted before replenishment resumes, so that error conditions are explicitly acknowledged and resolved.

#### Acceptance Criteria

1. THE Pool_Manager SHALL provide API or CLI command to delete failed accounts by account ID
2. WHEN a failed account is deleted, THE Pool_Manager SHALL use AWS Organizations CloseAccount API to close the account
3. THE Pool_Manager SHALL remove the failed account record from DynamoDB_Table after successful closure
4. THE Pool_Manager SHALL publish CloudWatch metric FailedAccountDeleted with dimension AccountId
5. WHEN all failed accounts are deleted, THE Pool_Manager SHALL automatically resume normal replenishment on next trigger
6. THE Pool_Manager SHALL log informational message when replenishment is unblocked after failed account deletion
7. IF failed account deletion fails, THEN THE Pool_Manager SHALL update error message in DynamoDB_Table and send SNS notification

### Requirement PM-14: Failed Account Dashboard and Reporting

**User Story:** As a domain administrator, I want a dashboard showing failed accounts and their errors, so that I can quickly assess pool health.

#### Acceptance Criteria

1. THE Pool_Manager SHALL publish CloudWatch metric FailedAccountCount every 5 minutes
2. THE Pool_Manager SHALL include dimensions for each failed step name in the metric
3. THE Pool_Manager SHALL create CloudWatch dashboard widget showing failed accounts over time
4. THE Pool_Manager SHALL create CloudWatch dashboard widget showing failure breakdown by step name
5. THE Pool_Manager SHALL create CloudWatch dashboard widget showing retry exhaustion rate
6. THE Pool_Manager SHALL support query API to list all failed accounts with full error details
7. THE query API SHALL return account ID, failed step, error message, stack name, retry count, and failure timestamp

### Requirement PM-15: CloudWatch Dashboard - Pool Overview

**User Story:** As a domain administrator, I want a CloudWatch dashboard showing real-time pool status, so that I can monitor account availability and health at a glance.

#### Acceptance Criteria

1. THE Pool_Manager SHALL create a CloudWatch dashboard named "AccountPoolFactory-Overview" in both Org Admin and Domain accounts
2. THE dashboard SHALL include widget showing current pool size by state (AVAILABLE, ASSIGNED, SETTING_UP, FAILED, DELETING)
3. THE dashboard SHALL include widget showing account creation rate (accounts created per hour/day)
4. THE dashboard SHALL include widget showing account assignment rate (accounts assigned per hour/day)
5. THE dashboard SHALL include widget showing average setup duration over last 24 hours
6. THE dashboard SHALL include widget showing failed account count with breakdown by failed step
7. THE dashboard SHALL auto-refresh every 1 minute

### Requirement PM-16: CloudWatch Dashboard - Account Inventory

**User Story:** As a domain administrator, I want to see detailed account inventory with account IDs and project assignments, so that I can track which accounts are in use.

#### Acceptance Criteria

1. THE Pool_Manager SHALL create a CloudWatch dashboard widget showing account inventory table
2. THE widget SHALL display columns: AccountId, State, ProjectId, CreatedDate, AssignedDate, FailureReason
3. THE widget SHALL support filtering by account state
4. THE widget SHALL support sorting by creation date or assignment date
5. THE widget SHALL include clickable links to account details in DynamoDB
6. THE widget SHALL include clickable links to CloudWatch Logs for failed accounts
7. THE widget SHALL update every 5 minutes

### Requirement PM-17: DynamoDB Query API for Account Details

**User Story:** As a domain administrator, I want to query DynamoDB for account details, so that I can programmatically access pool inventory.

#### Acceptance Criteria

1. THE Pool_Manager SHALL expose DynamoDB table with partition key accountId and sort key timestamp
2. THE table SHALL include global secondary index on state attribute for querying by account state
3. THE table SHALL include global secondary index on projectId attribute for querying by project assignment
4. THE table SHALL store account attributes: accountId, state, projectId, projectStackName, createdDate, assignedDate, setupStartDate, setupCompleteDate, failedStep, errorMessage, stackName, stackEvents, retryCount, vpcId, subnetIds, roleArns, bucketName, blueprintIds, grantIds
5. THE Pool_Manager SHALL provide Lambda function or API Gateway endpoint to query accounts by state
6. THE Pool_Manager SHALL provide Lambda function or API Gateway endpoint to query accounts by project ID
7. THE query API SHALL return results in JSON format with pagination support

### Requirement PM-18: Daily and Weekly Statistics

**User Story:** As a domain administrator, I want daily and weekly statistics on account creation and deletion, so that I can track pool usage trends.

#### Acceptance Criteria

1. THE Pool_Manager SHALL publish CloudWatch metric AccountsCreatedDaily with timestamp at midnight UTC
2. THE Pool_Manager SHALL publish CloudWatch metric AccountsDeletedDaily with timestamp at midnight UTC
3. THE Pool_Manager SHALL publish CloudWatch metric AccountsAssignedDaily with timestamp at midnight UTC
4. THE Pool_Manager SHALL calculate weekly statistics by aggregating daily metrics over 7-day period
5. THE Pool_Manager SHALL create CloudWatch dashboard widget showing daily account creation/deletion trend over last 30 days
6. THE Pool_Manager SHALL create CloudWatch dashboard widget showing weekly account creation/deletion trend over last 12 weeks
7. THE Pool_Manager SHALL include comparison to previous period (day-over-day, week-over-week)

### Requirement PM-19: Organization Account Limit Monitoring

**User Story:** As a domain administrator, I want to monitor how close I am to AWS Organizations account limits, so that I can request limit increases before hitting the cap.

#### Acceptance Criteria

1. THE Pool_Manager SHALL query AWS Organizations DescribeOrganization API to retrieve account limit
2. THE Pool_Manager SHALL query AWS Organizations ListAccounts API to count total active accounts
3. THE Pool_Manager SHALL calculate remaining account capacity as (limit - active_count)
4. THE Pool_Manager SHALL publish CloudWatch metric OrganizationAccountLimit with value of current limit
5. THE Pool_Manager SHALL publish CloudWatch metric OrganizationAccountsUsed with value of active account count
6. THE Pool_Manager SHALL publish CloudWatch metric OrganizationAccountsRemaining with value of remaining capacity
7. THE Pool_Manager SHALL create CloudWatch alarm when remaining capacity drops below 50 accounts
8. THE Pool_Manager SHALL send SNS notification when remaining capacity drops below 20 accounts with subject "AWS Account Limit Warning"
9. THE Pool_Manager SHALL include instructions to request limit increase in SNS notification
10. THE Pool_Manager SHALL check organization limits every 6 hours

### Requirement PM-20: Cross-Account Dashboard Access

**User Story:** As a domain administrator, I want to view the same dashboard from both Org Admin and Domain accounts, so that I have consistent visibility regardless of which account I'm logged into.

#### Acceptance Criteria

1. THE Pool_Manager SHALL deploy identical CloudWatch dashboards to both Org Admin account and Domain account
2. THE dashboards SHALL use cross-account CloudWatch metrics sharing to display metrics from both accounts
3. THE Org Admin account dashboard SHALL include metrics from Domain account for DataZone-specific operations
4. THE Domain account dashboard SHALL include metrics from Org Admin account for Organizations API operations
5. THE Pool_Manager SHALL configure IAM roles to allow cross-account CloudWatch metrics access
6. THE dashboards SHALL clearly label which account each metric originates from
7. THE dashboards SHALL include links to switch between Org Admin and Domain account consoles

### Requirement PM-21: Account Lifecycle Timeline Widget

**User Story:** As a domain administrator, I want to see a timeline of account lifecycle events, so that I can understand account flow through the pool.

#### Acceptance Criteria

1. THE Pool_Manager SHALL create CloudWatch dashboard widget showing account lifecycle timeline
2. THE timeline SHALL display events: Created, Setup Started, Setup Completed, Assigned, Deleted
3. THE timeline SHALL show duration between each lifecycle stage
4. THE timeline SHALL highlight accounts that took longer than expected to set up (>15 minutes)
5. THE timeline SHALL highlight accounts that failed during setup
6. THE timeline SHALL support filtering by date range (last 24 hours, last 7 days, last 30 days)
7. THE timeline SHALL include average lifecycle duration metric

### Requirement PM-22: Pool Manager Configuration

**User Story:** As a domain administrator, I want pool manager configuration stored in SSM Parameter Store, so that I can adjust pool settings without redeploying code.

#### Acceptance Criteria

1. THE Pool_Manager SHALL read all configuration from SSM Parameter Store at paths under /AccountPoolFactory/PoolManager/
2. THE Pool_Manager SHALL support parameters: PoolName, TargetOUId, MinimumPoolSize, TargetPoolSize, MaxConcurrentSetups, ReclaimStrategy, EmailPrefix, EmailDomain, NamePrefix
3. THE Pool_Manager SHALL read SSM parameters on EVERY invocation (no caching across invocations) to pick up configuration changes dynamically
4. THE Pool_Manager SHALL cache SSM parameters only for the duration of a single Lambda execution
5. IF SSM parameter retrieval fails, THEN THE Pool_Manager SHALL use default values: PoolName=AccountPoolFactory, TargetOUId=root, MinimumPoolSize=5, TargetPoolSize=10, MaxConcurrentSetups=3, ReclaimStrategy=DELETE
6. THE Pool_Manager SHALL log all configuration values at startup for troubleshooting
7. THE Pool_Manager SHALL validate configuration values and log warnings for invalid settings
8. WHEN creating accounts, THE Pool_Manager SHALL move accounts to the OU specified by TargetOUId parameter
9. IF TargetOUId is "root" or empty, THEN THE Pool_Manager SHALL leave accounts in the organization root

## Setup Orchestrator Lambda Requirements

### Requirement 1: Single Account Setup Invocation

**User Story:** As a domain administrator, I want the Setup Orchestrator to handle one account per invocation, so that multiple accounts can be set up in parallel.

#### Acceptance Criteria

1. WHEN the Setup_Orchestrator is invoked, THE Setup_Orchestrator SHALL accept account ID and creation request ID as input parameters
2. THE Setup_Orchestrator SHALL process exactly one account per Lambda invocation
3. THE Setup_Orchestrator SHALL support parallel execution with multiple concurrent invocations for different accounts
4. THE Setup_Orchestrator SHALL validate the account ID exists in AWS Organizations before starting setup
5. THE Setup_Orchestrator SHALL create a setup state record in DynamoDB_Table with status PENDING and account ID as partition key
6. IF the account ID is missing from input, THEN THE Setup_Orchestrator SHALL log an error and terminate without creating a state record
7. IF the account does not exist in AWS Organizations, THEN THE Setup_Orchestrator SHALL log an error and mark the state as FAILED

### Requirement 2: VPC Deployment Step

**User Story:** As a domain administrator, I want VPCs automatically deployed to new accounts, so that DataZone environments have required network infrastructure.

#### Acceptance Criteria

1. WHEN the setup state is PENDING, THE Setup_Orchestrator SHALL deploy the VPC CloudFormation_Stack to the Project_Account
2. THE Setup_Orchestrator SHALL use the template at templates/cloudformation/03-project-account/vpc-setup.yaml
3. THE Setup_Orchestrator SHALL configure VPC with 3 private subnets across 3 availability zones
4. WHEN VPC deployment starts, THE Setup_Orchestrator SHALL update the setup state to IN_PROGRESS with step "vpc_deployment"
5. WHEN VPC deployment completes successfully, THE Setup_Orchestrator SHALL extract VPC ID and subnet IDs from CloudFormation_Stack outputs
6. IF VPC deployment fails, THEN THE Setup_Orchestrator SHALL retry up to 3 times with exponential backoff starting at 30 seconds
7. IF all VPC deployment retries fail, THEN THE Setup_Orchestrator SHALL mark the setup state as FAILED and send SNS notification

### Requirement 3: IAM Roles Deployment Step

**User Story:** As a domain administrator, I want IAM roles automatically deployed to new accounts, so that DataZone can manage resources and provision environments.

#### Acceptance Criteria

1. WHEN VPC deployment completes, THE Setup_Orchestrator SHALL deploy the IAM roles CloudFormation_Stack to the Project_Account
2. THE Setup_Orchestrator SHALL use the template at templates/cloudformation/03-project-account/iam-roles.yaml
3. THE Setup_Orchestrator SHALL create ManageAccessRole with custom inline policies for Lake Formation, Glue, IAM, and S3
4. THE Setup_Orchestrator SHALL create ProvisioningRole with AdministratorAccess policy
5. THE Setup_Orchestrator SHALL NOT attach AmazonDataZoneEnvironmentRolePermissionsBoundary to any role
6. WHEN IAM roles deployment completes successfully, THE Setup_Orchestrator SHALL extract role ARNs from CloudFormation_Stack outputs
7. IF IAM roles deployment fails, THEN THE Setup_Orchestrator SHALL retry up to 3 times with exponential backoff starting at 30 seconds

### Requirement 4: S3 Bucket Creation Step

**User Story:** As a domain administrator, I want S3 buckets automatically created for blueprint artifacts, so that blueprints can be enabled in new accounts.

#### Acceptance Criteria

1. WHEN IAM roles deployment completes, THE Setup_Orchestrator SHALL create a Blueprint_Artifact_Bucket in the Project_Account
2. THE Setup_Orchestrator SHALL name the bucket using format datazone-blueprints-${AccountId}-${Region}
3. THE Setup_Orchestrator SHALL enable versioning on the Blueprint_Artifact_Bucket
4. THE Setup_Orchestrator SHALL enable server-side encryption with AES256 on the Blueprint_Artifact_Bucket
5. IF the bucket already exists, THEN THE Setup_Orchestrator SHALL verify bucket configuration and proceed to next step
6. IF bucket creation fails, THEN THE Setup_Orchestrator SHALL retry up to 3 times with exponential backoff starting at 10 seconds

### Requirement 5: Blueprint Enablement Step

**User Story:** As a domain administrator, I want all 17 DataZone blueprints automatically enabled in new accounts, so that projects can create diverse environment types.

#### Acceptance Criteria

1. WHEN Blueprint_Artifact_Bucket creation completes, THE Setup_Orchestrator SHALL deploy the blueprint enablement CloudFormation_Stack to the Project_Account
2. THE Setup_Orchestrator SHALL use the template at templates/cloudformation/03-project-account/blueprint-enablement.yaml
3. THE Setup_Orchestrator SHALL pass VPC ID, subnet IDs, role ARNs, and S3 bucket location as CloudFormation_Stack parameters
4. THE Setup_Orchestrator SHALL enable all 17 blueprints: LakehouseCatalog, AmazonBedrockGuardrail, MLExperiments, Tooling, RedshiftServerless, EmrServerless, Workflows, AmazonBedrockPrompt, DataLake, AmazonBedrockEvaluation, AmazonBedrockKnowledgeBase, PartnerApps, AmazonBedrockChatAgent, AmazonBedrockFunction, AmazonBedrockFlow, EmrOnEc2, QuickSight
5. WHEN blueprint enablement completes successfully, THE Setup_Orchestrator SHALL extract blueprint IDs from CloudFormation_Stack outputs
6. IF blueprint enablement fails, THEN THE Setup_Orchestrator SHALL retry up to 3 times with exponential backoff starting at 60 seconds

### Requirement 6: Policy Grants Creation Step

**User Story:** As a domain administrator, I want policy grants automatically created for all blueprints, so that projects can create environments without authorization errors.

#### Acceptance Criteria

1. WHEN blueprint enablement completes, THE Setup_Orchestrator SHALL create policy grants in the Project_Account
2. THE Setup_Orchestrator SHALL create one Policy_Grant per Blueprint with entity identifier format ${AccountId}:${BlueprintId}
3. THE Setup_Orchestrator SHALL set policy type to CREATE_ENVIRONMENT_FROM_BLUEPRINT for each Policy_Grant
4. THE Setup_Orchestrator SHALL configure principal as Project with CONTRIBUTOR designation
5. THE Setup_Orchestrator SHALL configure domain unit filter with root domain unit ID and includeChildDomainUnits set to true
6. WHEN all policy grants are created successfully, THE Setup_Orchestrator SHALL record grant IDs in DynamoDB_Table
7. IF policy grant creation fails for any blueprint, THEN THE Setup_Orchestrator SHALL retry that grant up to 3 times with exponential backoff starting at 10 seconds

### Requirement 7: Domain Sharing via RAM Step

**User Story:** As a domain administrator, I want domain sharing automatically configured via RAM, so that project accounts can access the DataZone domain.

#### Acceptance Criteria

1. WHEN policy grants creation completes, THE Setup_Orchestrator SHALL create a RAM_Share in the Domain_Account
2. THE Setup_Orchestrator SHALL use the template at templates/cloudformation/02-domain-account/domain-sharing-setup.yaml
3. THE Setup_Orchestrator SHALL associate the domain ARN as the resource in the RAM_Share
4. THE Setup_Orchestrator SHALL associate the Project_Account ID as the principal in the RAM_Share
5. THE Setup_Orchestrator SHALL use permission ARN AWSRAMPermissionsAmazonDatazoneDomainExtendedServiceWithPortalAccess
6. WHEN RAM_Share creation completes, THE Setup_Orchestrator SHALL verify the share status is ACTIVE
7. IF RAM_Share creation fails, THEN THE Setup_Orchestrator SHALL retry up to 3 times with exponential backoff starting at 30 seconds

### Requirement 8: EventBridge Rules Deployment Step

**User Story:** As a domain administrator, I want EventBridge rules automatically deployed to project accounts, so that CloudFormation events are forwarded to the central event bus for pool management.

#### Acceptance Criteria

1. WHEN domain sharing via RAM completes, THE Setup_Orchestrator SHALL deploy EventBridge rules StackSet to the Project_Account
2. THE Setup_Orchestrator SHALL use the template at templates/cloudformation/03-project-account/eventbridge-rules.yaml
3. THE Setup_Orchestrator SHALL configure rules to monitor CloudFormation stack events with prefix "DataZone-"
4. THE Setup_Orchestrator SHALL configure rules to forward events to Central_Event_Bus in Domain_Account
5. THE Setup_Orchestrator SHALL pass Central_Event_Bus ARN as CloudFormation_Stack parameter
6. WHEN EventBridge rules deployment completes successfully, THE Setup_Orchestrator SHALL verify rules are enabled
7. IF EventBridge rules deployment fails, THEN THE Setup_Orchestrator SHALL retry up to 3 times with exponential backoff starting at 30 seconds

### Requirement 9: Domain Visibility Verification

**User Story:** As a domain administrator, I want domain visibility automatically verified in project accounts, so that setup failures are detected before marking accounts as available.

#### Acceptance Criteria

1. WHEN EventBridge rules deployment completes, THE Setup_Orchestrator SHALL assume a role in the Project_Account
2. THE Setup_Orchestrator SHALL call DataZone ListDomains API in the Project_Account
3. THE Setup_Orchestrator SHALL verify the domain ID appears in the API response
4. THE Setup_Orchestrator SHALL verify the domain status is AVAILABLE
5. IF the domain is not visible, THEN THE Setup_Orchestrator SHALL retry up to 10 times with exponential backoff starting at 15 seconds
6. IF the domain is not visible after all retries, THEN THE Setup_Orchestrator SHALL mark the setup state as FAILED and send SNS notification
7. WHEN domain visibility is verified, THE Setup_Orchestrator SHALL update account state to AVAILABLE in DynamoDB_Table

### Requirement 10: Setup State Management

**User Story:** As a domain administrator, I want setup progress tracked in DynamoDB, so that I can monitor account setup status and resume from failures.

#### Acceptance Criteria

1. WHEN each setup step starts, THE Setup_Orchestrator SHALL update the DynamoDB_Table record with current step name and timestamp
2. WHEN each setup step completes, THE Setup_Orchestrator SHALL update the DynamoDB_Table record with completion timestamp and outputs
3. WHEN all setup steps complete successfully, THE Setup_Orchestrator SHALL update the setup state to COMPLETED
4. THE Setup_Orchestrator SHALL store VPC ID, subnet IDs, role ARNs, bucket name, blueprint IDs, and grant IDs in the DynamoDB_Table record
5. IF any setup step fails after all retries, THEN THE Setup_Orchestrator SHALL update the setup state to FAILED with error details
6. THE Setup_Orchestrator SHALL record total setup duration in the DynamoDB_Table record

### Requirement 10: Idempotency and Resume Capability

**User Story:** As a domain administrator, I want setup orchestration to be idempotent, so that duplicate events or manual retries do not cause errors.

#### Acceptance Criteria

1. WHEN the Setup_Orchestrator receives an event for an account with setup state COMPLETED, THE Setup_Orchestrator SHALL log a message and terminate without making changes
2. WHEN the Setup_Orchestrator receives an event for an account with setup state IN_PROGRESS, THE Setup_Orchestrator SHALL check the last updated timestamp
3. IF the last updated timestamp is older than 30 minutes, THEN THE Setup_Orchestrator SHALL resume from the last completed step
4. IF the last updated timestamp is newer than 30 minutes, THEN THE Setup_Orchestrator SHALL log a message and terminate to avoid concurrent execution
5. WHEN resuming from a failed step, THE Setup_Orchestrator SHALL verify the previous step outputs exist before proceeding
6. IF previous step outputs are missing, THEN THE Setup_Orchestrator SHALL restart from the first step

### Requirement 11: CloudWatch Metrics and Monitoring

**User Story:** As a domain administrator, I want CloudWatch metrics published for setup operations, so that I can monitor success rates and performance.

#### Acceptance Criteria

1. WHEN setup orchestration starts, THE Setup_Orchestrator SHALL publish a metric SetupStarted with dimension AccountId
2. WHEN setup orchestration completes successfully, THE Setup_Orchestrator SHALL publish a metric SetupSucceeded with dimension AccountId and setup duration
3. WHEN setup orchestration fails, THE Setup_Orchestrator SHALL publish a metric SetupFailed with dimensions AccountId, FailedStep, and ErrorType
4. WHEN each setup step completes, THE Setup_Orchestrator SHALL publish a metric StepDuration with dimensions AccountId and StepName
5. THE Setup_Orchestrator SHALL publish metrics to namespace AccountPoolFactory/SetupOrchestrator
6. THE Setup_Orchestrator SHALL include timestamp and unit for all metrics

### Requirement 12: Error Notification and Alerting

**User Story:** As a domain administrator, I want SNS notifications sent for setup failures, so that I can manually intervene when automation fails.

#### Acceptance Criteria

1. WHEN setup orchestration fails after all retries, THE Setup_Orchestrator SHALL publish a message to SNS_Topic
2. THE Setup_Orchestrator SHALL include account ID, failed step name, error message, and retry count in the SNS message
3. THE Setup_Orchestrator SHALL include CloudWatch Logs link for detailed troubleshooting in the SNS message
4. THE Setup_Orchestrator SHALL format the SNS message subject as "Account Setup Failed: ${AccountId}"
5. THE Setup_Orchestrator SHALL include setup state record from DynamoDB_Table in the SNS message body
6. IF SNS publish fails, THEN THE Setup_Orchestrator SHALL log the error but continue execution

### Requirement 13: Lambda Timeout and Execution Management

**User Story:** As a domain administrator, I want setup orchestration to complete within Lambda timeout limits, so that long-running operations do not fail.

#### Acceptance Criteria

1. THE Setup_Orchestrator SHALL have a timeout configuration of 15 minutes
2. WHEN total execution time exceeds 13 minutes, THE Setup_Orchestrator SHALL save current progress to DynamoDB_Table and terminate gracefully
3. WHEN the Setup_Orchestrator terminates due to timeout, THE Setup_Orchestrator SHALL publish a CloudWatch metric TimeoutOccurred
4. WHEN the Setup_Orchestrator terminates due to timeout, THE Setup_Orchestrator SHALL invoke itself asynchronously to resume from the last completed step
5. THE Setup_Orchestrator SHALL track total execution time across multiple invocations in the DynamoDB_Table record
6. IF total execution time across all invocations exceeds 30 minutes, THEN THE Setup_Orchestrator SHALL mark the setup state as FAILED and send SNS notification

### Requirement 14: Parallel Step Execution Optimization

**User Story:** As a domain administrator, I want independent setup steps to execute in parallel, so that total setup time is minimized.

#### Acceptance Criteria

1. WHEN VPC deployment and IAM roles deployment have no dependencies, THE Setup_Orchestrator SHALL execute them in parallel
2. WHEN S3 bucket creation completes, THE Setup_Orchestrator SHALL start blueprint enablement immediately without waiting for policy grants
3. WHEN blueprint enablement and domain sharing have no dependencies, THE Setup_Orchestrator SHALL execute them in parallel
4. THE Setup_Orchestrator SHALL wait for all parallel operations to complete before proceeding to dependent steps
5. IF any parallel operation fails, THEN THE Setup_Orchestrator SHALL cancel remaining parallel operations and mark the setup state as FAILED
6. THE Setup_Orchestrator SHALL record parallel execution metrics in CloudWatch with dimension ExecutionMode set to PARALLEL

### Requirement 15: Configuration Management

**User Story:** As a domain administrator, I want setup orchestrator configuration stored in SSM Parameter Store, so that I can update settings without redeploying Lambda code.

#### Acceptance Criteria

1. THE Setup_Orchestrator SHALL read domain ID from SSM Parameter Store at path /AccountPoolFactory/SetupOrchestrator/DomainId
2. THE Setup_Orchestrator SHALL read root domain unit ID from SSM Parameter Store at path /AccountPoolFactory/SetupOrchestrator/RootDomainUnitId
3. THE Setup_Orchestrator SHALL read retry configuration from SSM Parameter Store at path /AccountPoolFactory/SetupOrchestrator/RetryConfig
4. THE Setup_Orchestrator SHALL read SNS topic ARN from SSM Parameter Store at path /AccountPoolFactory/SetupOrchestrator/AlertTopicArn
5. THE Setup_Orchestrator SHALL read SSM parameters on EVERY invocation (no caching across invocations) to pick up configuration changes dynamically
6. THE Setup_Orchestrator SHALL cache SSM parameters only for the duration of a single Lambda execution
7. IF SSM parameter retrieval fails, THEN THE Setup_Orchestrator SHALL use default values and log a warning
