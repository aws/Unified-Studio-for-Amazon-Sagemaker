# Design Document

## Overview

This design introduces two new Lambda functions — AccountReconciler and AccountRecycler — that run in the Domain Account (994753223772). They replace the manual shell scripts (`clear-dynamodb-table.sh`, `cleanup-failed-accounts.sh`, `cleanup-retain-accounts.sh`) that directly manipulate the DynamoDB table. Both Lambdas follow the same patterns as existing Lambdas (SSM config loading, DynamoDB access via `AccountPoolFactory-AccountState`, CloudWatch metrics, SNS notifications).

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Domain Account (994753223772)                     │
│                                                                       │
│  ┌──────────────────┐    ┌──────────────────┐                        │
│  │ AccountReconciler │───▶│  AccountRecycler  │                        │
│  │     Lambda        │    │     Lambda        │                        │
│  └────────┬─────────┘    └───┬────┬────┬────┘                        │
│           │                  │    │    │                               │
│           │ assume role      │    │    │ invoke                       │
│           ▼                  │    │    ▼                               │
│  ┌────────────────┐         │    │  ┌──────────────────┐             │
│  │ Org Admin Acct  │         │    │  │ SetupOrchestrator │             │
│  │ (495869084367)  │         │    │  └──────────────────┘             │
│  │                 │         │    │                                    │
│  │ Organizations   │         │    │  ┌──────────────────┐             │
│  │ API + Tags      │         │    └─▶│DeprovisionAccount│             │
│  └────────────────┘         │       └──────────────────┘             │
│                              │                                        │
│           ┌──────────────────┘                                        │
│           ▼                                                           │
│  ┌────────────────────────────┐   ┌─────────┐   ┌──────────┐        │
│  │ DynamoDB: AccountState     │   │   SNS    │   │ CloudWatch│        │
│  │ (accountId + timestamp)    │   │  Alerts  │   │  Metrics  │        │
│  └────────────────────────────┘   └─────────┘   └──────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

### Cross-Account Access Pattern

The AccountReconciler needs to call AWS Organizations APIs (list accounts, list tags, tag resources). These APIs are only available from the Org Admin account. The existing `SMUS-AccountPoolFactory-AccountCreation` role in the Org Admin account already has most of the required Organizations permissions (`ListAccounts`, `DescribeAccount`, etc.).

We reuse this existing role by:
1. Adding `organizations:ListTagsForResource` and `organizations:TagResource` permissions to the `AccountCreationRole` in `02-provision-account.yaml`
2. Adding the AccountReconciler Lambda role as an additional trusted principal on the `AccountCreationRole` (alongside the existing Pool Manager role trust)
3. Using the same external ID pattern: `AccountPoolFactory-{DomainAccountId}`

No new role is created in the Org Admin account.

### Account Identification Strategy

Pool accounts are identified using a two-tier approach:
1. **Primary**: AWS Organizations tag `ManagedBy: AccountPoolFactory` + `PoolName: {this pool's name}` (checked via `list_tags_for_resource`)
2. **Fallback**: Account name prefix matching against SSM `NamePrefix` parameter (for legacy accounts created before tagging)

When the Reconciler finds an account identified by name prefix but missing the tag, it backfills the tag. This ensures all pool accounts converge to tag-based identification over time.

### Scalability: Large Organizations and Multiple Pools

Organizations can have 1000s of accounts, and there may be multiple AccountPoolFactory pools in the same org (each with its own `PoolName` and `NamePrefix`). The design handles this:

**Scoped listing**: Instead of listing all accounts in the org, the Reconciler uses `list_accounts_for_parent` scoped to the Target OU (`target_ou_id` from SSM config). Pool accounts are always moved to a specific OU during provisioning, so this dramatically reduces the search space. If `target_ou_id` is not configured, it falls back to `list_accounts` across the entire org.

**Efficient filtering**: The Reconciler first filters by name prefix (cheap string comparison on the paginated response), then calls `list_tags_for_resource` only on matching accounts to verify/backfill tags. This avoids calling the tags API on every account in the org.

**Multi-pool isolation**: Each Reconciler instance only processes accounts belonging to its own pool:
- Tag match: `ManagedBy=AccountPoolFactory` AND `PoolName={this pool's PoolName from SSM}`
- Name prefix match: account name starts with this pool's `NamePrefix` from SSM
- Accounts tagged with a different `PoolName` are skipped even if they have the `ManagedBy` tag

**API rate limiting**: Organizations APIs have rate limits. The Reconciler uses pagination (already handled by boto3 paginators) and adds a configurable delay between `list_tags_for_resource` calls to stay within limits. For very large OUs, it processes accounts in batches.

## Detailed Design

### 1. AccountReconciler Lambda

**Location**: `src/account-reconciler/lambda_function.py`
**Runtime**: Python 3.12, 512 MB, 300s timeout
**Runs in**: Domain Account
**IAM Role**: `SMUS-AccountPoolFactory-AccountReconciler-Role`

#### Event Schema

```json
{
  "source": "scheduled | manual",
  "dryRun": false,
  "accountIds": ["123456789012"],
  "autoRecycle": false,
  "autoReplenish": false
}
```

- `source=scheduled` + no `accountIds` → full reconciliation of all org accounts
- `source=manual` + `accountIds` → reconcile only specified accounts
- `dryRun=true` → compute changes but don't write to DynamoDB
- `autoRecycle=true` → invoke AccountRecycler for ORPHANED/FAILED accounts after reconciliation
- `autoReplenish=true` → after reconciliation + recycling, if AVAILABLE count < MinimumPoolSize, invoke Pool Manager `force_replenishment` to create new accounts (replaces the need for a separate seeding script)

#### Response Schema

```json
{
  "status": "SUCCESS",
  "summary": {
    "totalOrgAccounts": 15,
    "totalPoolAccounts": 8,
    "orphanedCreated": 2,
    "staleUpdated": 1,
    "unchanged": 5,
    "tagsBackfilled": 3,
    "failedValidation": 1
  },
  "details": [
    {
      "accountId": "123456789012",
      "action": "CREATED_ORPHANED | UPDATED_STATE | BACKFILLED_TAG | UNCHANGED | FAILED_VALIDATION",
      "previousState": "AVAILABLE",
      "newState": "FAILED",
      "note": "Missing Domain_Access_Role"
    }
  ],
  "recyclingTriggered": false,
  "replenishmentTriggered": false
}
```

#### Core Algorithm

```
1. Load SSM config (NamePrefix, PoolName, TargetOUId)
2. Assume SMUS-AccountPoolFactory-AccountCreation role in Org Admin account (same role used by Pool Manager)
3. If TargetOUId is configured:
     List accounts scoped to the Target OU via list_accounts_for_parent paginator
   Else:
     List all org accounts via list_accounts paginator
4. For each account, filter by name prefix first (cheap string match):
   a. If name matches NamePrefix → candidate pool account
   b. If name doesn't match → skip (not this pool's account)
5. For each candidate pool account, call list_tags_for_resource:
   a. If tag ManagedBy=AccountPoolFactory AND PoolName={this pool's PoolName} → confirmed pool account
   b. If tag ManagedBy=AccountPoolFactory AND PoolName={different pool} → skip (belongs to another pool)
   c. If no ManagedBy tag but name prefix matched → pool account (backfill tags)
   d. Add small delay between tag API calls to respect rate limits
5. For each pool account found:
   a. Query DynamoDB for existing record
   b. If no record → create ORPHANED record
   c. If record exists:
      - If org status is SUSPENDED → update DynamoDB state to SUSPENDED
      - If DynamoDB state is AVAILABLE → validate Domain_Access_Role exists
        - If role missing → update state to FAILED with reconciliationNote
      - If DynamoDB state is ASSIGNED → verify projectStackName exists
        - If missing → add reconciliationNote (don't change state)
6. Check for stale DynamoDB records (records with no matching org account)
   → update state to SUSPENDED
7. Publish CloudWatch metrics
8. If autoRecycle=true → invoke AccountRecycler with orphaned/failed account IDs
9. If autoReplenish=true → count AVAILABLE accounts in DynamoDB
   a. If AVAILABLE < MinimumPoolSize → invoke Pool Manager with action=force_replenishment
   b. This replaces the separate seed script (03-seed-test-accounts.sh)
10. Return summary
```

#### DynamoDB Write Pattern

Uses conditional writes to prevent overwriting concurrent changes:

```python
dynamodb.update_item(
    TableName=TABLE_NAME,
    Key={'accountId': {'S': account_id}, 'timestamp': item['timestamp']},
    UpdateExpression='SET #state = :new_state, reconciliationNote = :note, lastReconciled = :now',
    ConditionExpression='#state = :expected_state',
    ExpressionAttributeNames={'#state': 'state'},
    ExpressionAttributeValues={
        ':new_state': {'S': new_state},
        ':expected_state': {'S': current_state},
        ':note': {'S': note},
        ':now': {'S': datetime.now(timezone.utc).isoformat()}
    }
)
```

#### Domain_Access_Role Validation

For AVAILABLE accounts, the Reconciler validates the role exists by attempting to assume it:

```python
sts.assume_role(
    RoleArn=f'arn:aws:iam::{account_id}:role/SMUS-AccountPoolFactory-DomainAccess',
    RoleSessionName='reconciliation-check',
    DurationSeconds=900
)
```

This reuses the same pattern as `setup-orchestrator/get_cross_account_client()`.

### 2. AccountRecycler Lambda

**Location**: `src/account-recycler/lambda_function.py`
**Runtime**: Python 3.12, 512 MB, 900s timeout (longer due to orchestrating deprovision + setup)
**Runs in**: Domain Account
**IAM Role**: `SMUS-AccountPoolFactory-AccountRecycler-Role`

#### Event Schema

```json
{
  "accountId": "123456789012",
  "recycleAll": false
}
```

- `accountId` → recycle a single account
- `recycleAll=true` → query DynamoDB for all CLEANING, FAILED, ORPHANED accounts and process them

#### Response Schema

```json
{
  "status": "SUCCESS",
  "summary": {
    "totalProcessed": 5,
    "succeeded": 3,
    "failed": 1,
    "skipped": 1
  },
  "results": [
    {
      "accountId": "123456789012",
      "previousState": "CLEANING",
      "result": "RECYCLED | FAILED | SKIPPED",
      "newState": "AVAILABLE",
      "error": null
    }
  ]
}
```

#### Recycling State Machine

```
                    ┌─────────┐
                    │ CLEANING │──── DeprovisionAccount ────┐
                    └─────────┘                             │
                         │                                  │
                         │ success                     fail │
                         ▼                                  ▼
                  ┌─────────────┐                    ┌──────────┐
                  │ SETTING_UP  │                    │  FAILED   │
                  └──────┬──────┘                    └─────┬────┘
                         │                                 │
                    SetupOrchestrator              retryCount < max?
                         │                           │          │
                    success│                     yes │      no  │
                         ▼                          ▼          ▼
                   ┌───────────┐            retry cycle    ┌──────────┐
                   │ AVAILABLE  │                          │ DELETING  │
                   └───────────┘                          └──────────┘

                    ┌──────────┐
                    │ ORPHANED  │
                    └─────┬────┘
                          │
                   Domain_Access_Role exists?
                     │              │
                  yes │          no │
                     ▼              ▼
              SetupOrchestrator   ProvisionAccount (StackSet roles)
                     │              │
                     ▼              ▼
               ┌───────────┐  ┌─────────────┐
               │ AVAILABLE  │  │ SETTING_UP  │──▶ AVAILABLE
               └───────────┘  └─────────────┘
```

#### Core Algorithm — Single Account

```
1. Load SSM config (MaxRecycleRetries default 3, MaxConcurrentRecycles default 3)
2. Query DynamoDB for account record
3. Based on current state:

   CLEANING:
     a. Invoke DeprovisionAccount Lambda (synchronous)
     b. If success → invoke SetupOrchestrator Lambda (synchronous)
     c. If SetupOrchestrator success → update state to AVAILABLE, set recycledDate, clear project attributes
     d. If any step fails → update state to FAILED, set errorMessage + failedStep, increment retryCount

   FAILED:
     a. Read errorMessage to classify:
        - Recoverable: missing stacks, role issues, timeout errors
        - Non-recoverable: account suspended, account closed
     b. If non-recoverable → update state to DELETING, log reason
     c. If recoverable and retryCount < MaxRecycleRetries → increment retryCount, re-attempt from CLEANING flow
     d. If retryCount >= MaxRecycleRetries → update state to FAILED with "Max recycling retries exceeded"

   ORPHANED:
     a. Check Domain_Access_Role exists (STS assume role)
     b. If exists → invoke SetupOrchestrator, transition to SETTING_UP → AVAILABLE
     c. If not exists → invoke ProvisionAccount to deploy StackSet roles, then SetupOrchestrator
     d. On success → update state to AVAILABLE, set recycledDate
```

#### Batch Processing

When `recycleAll=true`:
1. Query StateIndex GSI for accounts in states: CLEANING, FAILED, ORPHANED
2. Process up to `MaxConcurrentRecycles` accounts using `concurrent.futures.ThreadPoolExecutor`
3. Each account is processed independently — failures don't stop other accounts
4. Return aggregate summary

#### Attribute Cleanup on AVAILABLE Transition

When transitioning to AVAILABLE, clear project-specific attributes (same pattern as `reclaim_account_reuse` in pool-manager):

```python
dynamodb.update_item(
    TableName=TABLE_NAME,
    Key={'accountId': {'S': account_id}, 'timestamp': item['timestamp']},
    UpdateExpression='''
        SET #state = :available, recycledDate = :now, retryCount = :zero
        REMOVE projectStackName, assignedDate, errorMessage, failedStep, cleanupStartDate, projectId, reconciliationNote
    ''',
    ExpressionAttributeNames={'#state': 'state'},
    ExpressionAttributeValues={
        ':available': {'S': 'AVAILABLE'},
        ':now': {'S': datetime.now(timezone.utc).isoformat()},
        ':zero': {'N': '0'}
    }
)
```

### 3. IAM Roles and CloudFormation Changes

#### New Resources in `02-domain-account/deploy/01-infrastructure.yaml`

**AccountReconcilerRole** (`SMUS-AccountPoolFactory-AccountReconciler-Role`):
- Lambda basic execution
- DynamoDB: Query, PutItem, UpdateItem, GetItem on AccountState table + indexes
- STS: AssumeRole on `SMUS-AccountPoolFactory-AccountCreation` (Org Admin — reused, not new) and `SMUS-AccountPoolFactory-DomainAccess` (project accounts)
- SSM: GetParameter on `/AccountPoolFactory/PoolManager/*`
- CloudWatch: PutMetricData
- SNS: Publish to AlertTopic
- Lambda: InvokeFunction on AccountRecycler (for autoRecycle) and PoolManager (for autoReplenish)

**AccountRecyclerRole** (`SMUS-AccountPoolFactory-AccountRecycler-Role`):
- Lambda basic execution
- DynamoDB: Query, PutItem, UpdateItem, GetItem on AccountState table + indexes
- Lambda: InvokeFunction on DeprovisionAccount, SetupOrchestrator, ProvisionAccount (cross-account in Org Admin)
- SSM: GetParameter on `/AccountPoolFactory/PoolManager/*`
- CloudWatch: PutMetricData
- SNS: Publish to AlertTopic

**AccountReconcilerFunction** and **AccountRecyclerFunction**: Lambda function resources following existing patterns.

#### New Resources in `01-org-mgmt-account/deploy/02-provision-account.yaml`

**Update to AccountCreationRole** (`SMUS-AccountPoolFactory-AccountCreation`):
- Add `organizations:ListTagsForResource`, `organizations:TagResource`, and `organizations:ListAccountsForParent` to the existing policy
- Add `SMUS-AccountPoolFactory-AccountReconciler-Role` from the Domain account as an additional trusted principal in the AssumeRolePolicyDocument (alongside the existing Pool Manager role)

**Update to ProvisionAccountRole**: Add `organizations:TagResource` and `organizations:ListTagsForResource` permissions so the ProvisionAccount Lambda can tag newly created accounts.

#### New SSM Parameters

| Parameter | Path | Default |
|-----------|------|---------|
| MaxRecycleRetries | `/AccountPoolFactory/PoolManager/MaxRecycleRetries` | 3 |
| MaxConcurrentRecycles | `/AccountPoolFactory/PoolManager/MaxConcurrentRecycles` | 3 |

### 4. ProvisionAccount Lambda Changes

Modify `src/provision-account/lambda_function.py` `create_account()` to tag accounts after creation:

```python
# After successful account creation, tag the account
try:
    organizations.tag_resource(
        ResourceId=account_id,
        Tags=[
            {'Key': 'ManagedBy', 'Value': 'AccountPoolFactory'},
            {'Key': 'PoolName', 'Value': event.get('poolName', 'AccountPoolFactory')}
        ]
    )
    print(f"   🏷️ Tagged account {account_id} with ManagedBy=AccountPoolFactory, PoolName={event.get('poolName', 'AccountPoolFactory')}")
except Exception as tag_error:
    print(f"   ⚠️ Failed to tag account {account_id}: {tag_error}")
    # Non-fatal — Reconciler can backfill tags later
```

This is added after the `return account_id` line in the success path, restructured so tagging happens before the return. The `poolName` is passed in the event payload from Pool Manager's `create_accounts_parallel()`, which reads it from SSM config.

### 5. CloudWatch Metrics

| Metric | Lambda | Dimensions |
|--------|--------|------------|
| ReconciliationCompleted | Reconciler | OrphanedCount, StaleCount, UnchangedCount |
| ReconciliationFailed | Reconciler | ErrorType |
| RecyclingSucceeded | Recycler | AccountId |
| RecyclingFailed | Recycler | AccountId, FailedStep |
| BatchRecyclingCompleted | Recycler | TotalProcessed, Succeeded, Failed |

All metrics published to namespace `AccountPoolFactory` using the same `publish_metric()` pattern as existing Lambdas.

### 6. File Structure

```
src/
  account-reconciler/
    lambda_function.py          # AccountReconciler Lambda
  account-recycler/
    lambda_function.py          # AccountRecycler Lambda
  provision-account/
    lambda_function.py          # Updated: add tagging after account creation
templates/cloudformation/
  01-org-mgmt-account/deploy/
    02-provision-account.yaml   # Updated: add Reconciliation role, update ProvisionAccount permissions
  02-domain-account/deploy/
    01-infrastructure.yaml      # Updated: add Reconciler + Recycler roles, functions, SSM params
```

## Correctness Properties

### Property 1: Reconciliation Completeness
After a full reconciliation run, every ACTIVE pool account in AWS Organizations (identified by tag or name prefix) SHALL have a corresponding record in the DynamoDB table. No pool account shall be unaccounted for.

### Property 2: State Consistency
After reconciliation, no DynamoDB record shall have state AVAILABLE if the corresponding account is missing the `SMUS-AccountPoolFactory-DomainAccess` role. Such accounts must be in FAILED state.

### Property 3: Recycling Idempotency
Invoking the Recycler on an account already in AVAILABLE state shall be a no-op — it shall not re-run deprovision or setup, and the account state shall remain AVAILABLE.

### Property 4: Retry Bound
No account shall be retried more than `MaxRecycleRetries` times. Once the limit is reached, the account must be in FAILED state with the message "Max recycling retries exceeded" and no further recycling attempts shall occur.

### Property 5: Orphan Resolution
Every ORPHANED account that completes the recycling process successfully shall transition to AVAILABLE state with a `recycledDate` attribute and have all project-specific attributes cleared.

### Property 6: Concurrent Safety
Conditional DynamoDB writes shall prevent the Reconciler from overwriting state changes made by other Lambdas (Pool Manager, SetupOrchestrator, DeprovisionAccount) between the read and write operations.

### Property 7: Tag Convergence
After reconciliation, every pool account identified by name prefix shall have the `ManagedBy: AccountPoolFactory` tag in AWS Organizations. Legacy untagged accounts are backfilled during reconciliation.

### Property 8: Non-Destructive Dry Run
When `dryRun=true`, the Reconciler shall return the same summary as a real run but shall not modify any DynamoDB records or invoke any other Lambdas.
