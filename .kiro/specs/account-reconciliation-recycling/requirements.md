# Requirements Document

## Introduction

The Account Pool Factory currently relies on manual shell scripts that directly manipulate the DynamoDB table (`AccountPoolFactory-AccountState`) for account cleanup, reuse, and state management. After cleanup/reuse cycles, the DynamoDB state drifts from what actually exists in AWS Organizations, leaving orphaned records, missing accounts, and inconsistent states. This feature introduces two new Lambda functions: an Account Reconciliation Lambda that synchronizes DynamoDB state with the actual org accounts, and an Account Recycling Lambda that automates the lifecycle of returning accounts to AVAILABLE state, handling error recovery and re-provisioning.

## Glossary

- **Reconciliation_Lambda**: A Lambda function that discovers pool accounts in AWS Organizations and synchronizes the DynamoDB table to reflect the actual state of those accounts
- **Recycling_Lambda**: A Lambda function that manages the lifecycle of returning used, failed, or stale accounts back to AVAILABLE state, including cleanup and re-provisioning
- **Pool_Account**: An AWS account created by the Account Pool Factory, identifiable by the configured name prefix (e.g., `smus-test-project-`) in AWS Organizations
- **DynamoDB_Table**: The `AccountPoolFactory-AccountState` DynamoDB table with composite key (accountId + timestamp), StateIndex GSI (state + createdDate), and ProjectIndex GSI (projectId + assignedDate)
- **Organizations_API**: The AWS Organizations API accessed from the Domain Account by assuming the `OrganizationAccountAccessRole` in the Org Admin Account (495869084367)
- **Domain_Account**: AWS account 994753223772 where the DynamoDB table, Lambda functions, and DataZone domain reside
- **Org_Admin_Account**: AWS account 495869084367 that hosts AWS Organizations and Control Tower
- **Target_OU**: The organizational unit where pool accounts are placed (configured as `target_ou_id` in config.yaml)
- **Account_State**: One of: PROVISIONING, CONFIGURING, SETTING_UP, AVAILABLE, ASSIGNED, CLEANING, FAILED, DELETING, ORPHANED, SUSPENDED
- **Orphaned_Account**: A pool account that exists in AWS Organizations but has no corresponding record in the DynamoDB table
- **Stale_Record**: A DynamoDB record whose corresponding AWS account no longer exists in the organization or has been suspended
- **Domain_Access_Role**: The `SMUS-AccountPoolFactory-DomainAccess` IAM role deployed via StackSet into project accounts for cross-account access from the Domain Account
- **SSM_Config**: Pool Manager configuration stored in SSM Parameter Store under `/AccountPoolFactory/PoolManager/`, including NamePrefix, ReclaimStrategy, and pool size settings
- **Pool_Tag**: The AWS Organizations tag `ManagedBy: AccountPoolFactory` applied to pool-managed accounts, used as the primary method to identify Pool_Accounts (with name prefix as fallback for accounts created before tagging was implemented)

## Requirements

### Requirement 1: Discover Pool Accounts in AWS Organizations

**User Story:** As an operator, I want the Reconciliation Lambda to discover all pool accounts in the organization, so that I have a complete inventory of accounts managed by the pool.

#### Acceptance Criteria

1. WHEN invoked, THE Reconciliation_Lambda SHALL assume the `OrganizationAccountAccessRole` in the Org_Admin_Account to access the Organizations_API
2. WHEN listing accounts, THE Reconciliation_Lambda SHALL use the Organizations_API `list_accounts` paginator to retrieve all accounts in the organization
3. WHEN filtering pool accounts, THE Reconciliation_Lambda SHALL identify Pool_Accounts primarily by checking for the Pool_Tag (`ManagedBy: AccountPoolFactory`) on the account using the Organizations_API `list_tags_for_resource`, and SHALL fall back to matching the account name against the configured name prefix from SSM_Config (`NamePrefix`) for accounts created before tagging was implemented
4. WHEN a pool account is discovered, THE Reconciliation_Lambda SHALL record the account ID, account name, email, account status (ACTIVE/SUSPENDED), and the join date from the Organizations_API response
5. IF the Reconciliation_Lambda fails to assume the cross-account role, THEN THE Reconciliation_Lambda SHALL log the error with the role ARN and Org_Admin_Account ID, and terminate with a descriptive error response
6. WHEN the Reconciliation_Lambda discovers a Pool_Account identified by name prefix that is missing the Pool_Tag, THE Reconciliation_Lambda SHALL apply the Pool_Tag (`ManagedBy: AccountPoolFactory`) and a `PoolName` tag with the value from SSM_Config to backfill tagging for legacy accounts

### Requirement 2: Synchronize DynamoDB State with Organization Accounts

**User Story:** As an operator, I want the DynamoDB table to always reflect the true state of pool accounts in the organization, so that I can trust the pool state without manual intervention.

#### Acceptance Criteria

1. WHEN a Pool_Account exists in the organization but has no record in the DynamoDB_Table, THE Reconciliation_Lambda SHALL create a new record with state ORPHANED, the account ID, account name, email, and the current timestamp
2. WHEN a DynamoDB record exists for an account that is no longer ACTIVE in the organization, THE Reconciliation_Lambda SHALL update the record state to SUSPENDED
3. WHEN a DynamoDB record has a state that contradicts the actual account condition, THE Reconciliation_Lambda SHALL update the state and add a `reconciliationNote` attribute describing the change (e.g., "State changed from AVAILABLE to ORPHANED: account missing Domain_Access_Role")
4. WHEN reconciliation completes, THE Reconciliation_Lambda SHALL return a summary containing: total org accounts discovered, total pool accounts matched, new orphaned records created, stale records updated, and records unchanged
5. THE Reconciliation_Lambda SHALL use conditional writes when updating DynamoDB records to prevent overwriting concurrent state changes from other Lambda functions

### Requirement 3: Validate Account Readiness During Reconciliation

**User Story:** As an operator, I want reconciliation to verify that accounts marked AVAILABLE actually have the required infrastructure, so that the pool only contains truly ready accounts.

#### Acceptance Criteria

1. WHEN reconciling an account with state AVAILABLE, THE Reconciliation_Lambda SHALL verify the Domain_Access_Role exists in the Pool_Account by attempting to assume it from the Domain_Account
2. WHEN an AVAILABLE account is missing the Domain_Access_Role, THE Reconciliation_Lambda SHALL update the account state to FAILED with an errorMessage indicating the missing role
3. WHEN reconciling an account with state ASSIGNED, THE Reconciliation_Lambda SHALL verify the account has a non-empty `projectStackName` attribute in the DynamoDB record
4. IF an ASSIGNED account has no `projectStackName`, THEN THE Reconciliation_Lambda SHALL add a reconciliationNote flagging the inconsistency without changing the state

### Requirement 4: Support Invocation Modes for Reconciliation

**User Story:** As an operator, I want to run reconciliation on a schedule or on demand, so that I can keep the pool in sync automatically and also trigger it manually when needed.

#### Acceptance Criteria

1. WHEN invoked with event source `scheduled`, THE Reconciliation_Lambda SHALL perform a full reconciliation of all pool accounts
2. WHEN invoked with event source `manual` and a list of account IDs, THE Reconciliation_Lambda SHALL reconcile only the specified accounts
3. WHEN invoked with event source `manual` and parameter `dryRun` set to true, THE Reconciliation_Lambda SHALL return the reconciliation summary without writing any changes to the DynamoDB_Table
4. THE Reconciliation_Lambda SHALL publish a CloudWatch metric `ReconciliationCompleted` with dimensions for `OrphanedCount`, `StaleCount`, and `UnchangedCount` after each run

### Requirement 5: Recycle Accounts Back to AVAILABLE State

**User Story:** As an operator, I want the Recycling Lambda to automatically prepare used accounts for reuse, so that I do not need to manually manipulate DynamoDB or run cleanup scripts.

#### Acceptance Criteria

1. WHEN invoked with an account ID in state CLEANING, THE Recycling_Lambda SHALL invoke the existing DeprovisionAccount Lambda to clean the account and wait for completion
2. WHEN the DeprovisionAccount Lambda completes successfully, THE Recycling_Lambda SHALL invoke the existing SetupOrchestrator Lambda to re-provision the account infrastructure
3. WHEN the SetupOrchestrator Lambda completes successfully, THE Recycling_Lambda SHALL update the account state to AVAILABLE with a `recycledDate` attribute set to the current UTC timestamp
4. WHEN invoked with an account ID in state FAILED, THE Recycling_Lambda SHALL evaluate the `errorMessage` attribute to determine if the failure is recoverable (missing stacks, role issues) or non-recoverable (account suspended, account closed)
5. IF the failure is recoverable, THEN THE Recycling_Lambda SHALL increment the `retryCount` attribute and re-attempt the recycling process
6. IF the failure is non-recoverable, THEN THE Recycling_Lambda SHALL update the account state to DELETING and log the reason

### Requirement 6: Enforce Retry Limits for Recycling

**User Story:** As an operator, I want recycling to have retry limits, so that permanently broken accounts do not consume resources indefinitely.

#### Acceptance Criteria

1. THE Recycling_Lambda SHALL read the maximum retry count from SSM_Config parameter `MaxRecycleRetries`, defaulting to 3 if not configured
2. WHEN the `retryCount` for an account reaches the maximum retry count, THE Recycling_Lambda SHALL update the account state to FAILED with errorMessage "Max recycling retries exceeded" and stop retrying
3. WHEN a recycling attempt fails, THE Recycling_Lambda SHALL record the error in the `errorMessage` attribute and the failed step in a `failedStep` attribute
4. THE Recycling_Lambda SHALL publish a CloudWatch metric `RecyclingFailed` with dimensions for `AccountId` and `FailedStep` when a recycling attempt fails
5. THE Recycling_Lambda SHALL publish a CloudWatch metric `RecyclingSucceeded` with a dimension for `AccountId` when an account is successfully returned to AVAILABLE state

### Requirement 7: Handle ORPHANED Accounts

**User Story:** As an operator, I want orphaned accounts to be automatically brought into the pool, so that discovered accounts do not sit idle.

#### Acceptance Criteria

1. WHEN invoked with an account ID in state ORPHANED, THE Recycling_Lambda SHALL verify the Domain_Access_Role exists in the Pool_Account
2. WHEN the Domain_Access_Role exists, THE Recycling_Lambda SHALL invoke the SetupOrchestrator Lambda to provision the account infrastructure and transition the state to SETTING_UP
3. WHEN the Domain_Access_Role does not exist, THE Recycling_Lambda SHALL invoke the ProvisionAccount Lambda to deploy the required StackSet roles before proceeding with setup
4. WHEN provisioning of an ORPHANED account completes successfully, THE Recycling_Lambda SHALL update the account state to AVAILABLE with a `recycledDate` attribute

### Requirement 8: Integrate with Existing Pool Manager

**User Story:** As an operator, I want the recycling and reconciliation functions to work alongside the existing Pool Manager, so that the overall pool lifecycle remains consistent.

#### Acceptance Criteria

1. THE Recycling_Lambda SHALL use the same DynamoDB_Table, key schema (accountId + timestamp), and GSI patterns as the existing Pool Manager Lambda
2. THE Recycling_Lambda SHALL use the same SNS topic for failure notifications as the existing Pool Manager Lambda
3. WHEN the Recycling_Lambda transitions an account to AVAILABLE, THE Recycling_Lambda SHALL clear the `projectStackName`, `assignedDate`, `errorMessage`, `failedStep`, and `cleanupStartDate` attributes from the DynamoDB record
4. THE Reconciliation_Lambda SHALL read the `NamePrefix` from SSM_Config to identify pool accounts, using the same parameter path (`/AccountPoolFactory/PoolManager/NamePrefix`) as the Pool Manager Lambda

### Requirement 9: Support Batch Recycling

**User Story:** As an operator, I want to recycle multiple accounts in a single invocation, so that I can efficiently recover the pool after a test cycle.

#### Acceptance Criteria

1. WHEN invoked with event parameter `recycleAll` set to true, THE Recycling_Lambda SHALL query the DynamoDB_Table StateIndex GSI for all accounts in states CLEANING, FAILED, and ORPHANED
2. WHEN processing multiple accounts, THE Recycling_Lambda SHALL process accounts concurrently up to a configurable limit read from SSM_Config parameter `MaxConcurrentRecycles`, defaulting to 3
3. WHEN batch recycling completes, THE Recycling_Lambda SHALL return a summary containing: total accounts processed, accounts successfully recycled, accounts that failed recycling, and accounts skipped due to non-recoverable errors
4. IF an individual account fails during batch recycling, THEN THE Recycling_Lambda SHALL continue processing the remaining accounts and include the failure in the summary

### Requirement 10: Reconciliation and Recycling Coordination

**User Story:** As an operator, I want reconciliation to automatically trigger recycling for discovered issues and replenish the pool if needed, so that the pool self-heals and stays at the desired size without manual steps or separate seeding scripts.

#### Acceptance Criteria

1. WHEN reconciliation discovers ORPHANED accounts and the event parameter `autoRecycle` is set to true, THE Reconciliation_Lambda SHALL invoke the Recycling_Lambda with the list of orphaned account IDs
2. WHEN reconciliation updates accounts to FAILED state and `autoRecycle` is true, THE Reconciliation_Lambda SHALL invoke the Recycling_Lambda with the list of newly failed account IDs
3. WHEN `autoRecycle` is false or not specified, THE Reconciliation_Lambda SHALL only update the DynamoDB_Table without triggering the Recycling_Lambda
4. WHEN reconciliation and recycling complete and the count of AVAILABLE accounts is below the `MinimumPoolSize` from SSM_Config, THE Reconciliation_Lambda SHALL invoke the Pool Manager Lambda with `action: force_replenishment` to create additional accounts
5. WHEN the event parameter `autoReplenish` is false, THE Reconciliation_Lambda SHALL skip the replenishment check even if the pool is under minimum size

### Requirement 11: Tag Pool Accounts During Provisioning

**User Story:** As an operator, I want newly created pool accounts to be tagged in AWS Organizations, so that they can be reliably identified as pool-managed accounts without relying solely on name prefix matching.

#### Acceptance Criteria

1. WHEN the ProvisionAccount Lambda successfully creates a new account, IT SHALL tag the account in AWS Organizations using `tag_resource` with the tags `ManagedBy: AccountPoolFactory` and `PoolName: {pool_name}` (where pool_name is read from SSM_Config or passed in the event)
2. IF tagging fails after account creation, THE ProvisionAccount Lambda SHALL log a warning but SHALL NOT fail the overall provisioning process, since the Reconciliation_Lambda can backfill tags later
3. THE ProvisionAccount Lambda IAM role SHALL be updated (via CloudFormation template `02-provision-account.yaml`) to include `organizations:TagResource` and `organizations:ListTagsForResource` permissions
