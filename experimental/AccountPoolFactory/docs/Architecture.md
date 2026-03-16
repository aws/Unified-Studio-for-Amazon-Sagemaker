# Account Pool Factory - Architecture

[← Back to README](../README.md) | [Org Admin Guide](OrgAdminGuide.md) | [Domain Admin Guide](DomainAdminGuide.md) | [Security Guide](SecurityGuide.md) | [Testing Guide](TestingGuide.md) | [Project Structure](ProjectStructure.md)

---

## The Problem We're Solving

When a user creates a new project in **Amazon SageMaker Unified Studio**, that project requires a dedicated AWS account for security isolation. Each project gets its own account to ensure complete separation of resources, data, and permissions between different teams and workloads.

However, creating and configuring a new AWS account takes 5-6 minutes:
- Creating the account via AWS Organizations: ~1 minute
- Deploying VPC, IAM roles, S3 buckets, RAM share: ~2.5 minutes (parallel)
- Enabling 17 DataZone blueprints: ~3 minutes
- Verifying domain visibility: included in Wave 1

This delay frustrates users who expect instant project creation. The Account Pool Factory solves this by maintaining a pool of pre-configured accounts that are ready before users need them.

## The Solution

The Account Pool Factory is an event-driven automation system that:
- Maintains a pool of 5-10 pre-configured AWS accounts (configurable)
- Monitors the pool size and automatically replenishes when accounts are assigned
- Provides instant account assignment (< 5 seconds instead of 5-6 minutes)
- Handles account lifecycle from creation through assignment to cleanup

**Key Benefit**: Users get immediate project creation with zero wait time for account setup.

## Who's Involved

### 1. Project Creator (Works in: Domain Account)

The end user who creates SageMaker Unified Studio projects through the web portal. They:
- Create projects using the SMUS interface
- Create environments within projects
- Delete projects when done

**Experience**: Click "Create Project" → Project ready in seconds (account already configured)

### 2. Domain Administrator (Works in: Domain Account)

Manages the SageMaker Unified Studio domain and the automated account pool. They:
- Deploy and configure the pool management infrastructure
- Monitor pool health via CloudWatch dashboards
- Respond to alerts when accounts fail setup
- Adjust pool sizes based on demand

**Tools**: CloudWatch dashboards, SNS alerts, SSM parameters for configuration

### 3. Organization Administrator (Works in: Organization Admin Account)

Manages the AWS Organization and account creation infrastructure. They:
- Deploy StackSets for account provisioning
- Monitor organization account limits
- Request limit increases when needed
- Review cross-account metrics

**Tools**: AWS Organizations console, CloudWatch dashboards, Service Quotas

## System Architecture

### Multi-Account Architecture

![Multi-Account Architecture](diagrams/mutli-account-architecture-factory.png)

**Editable Diagram**: [mutli-account-architecture-factory.drawio](diagrams/mutli-account-architecture-factory.drawio)

The system spans three account types:
- **Organization Admin Account**: Manages AWS Organizations and account creation
- **Domain Account**: Hosts SageMaker Unified Studio, DataZone, and automation Lambdas
- **Project Accounts (Pool)**: Pre-configured accounts ready for project assignment

## How It Works: Step-by-Step

### Step 1: User Creates a Project

A user opens SageMaker Unified Studio and clicks "Create Project". Behind the scenes:

**API Call Sequence**:

1. **User Action**: Click "Create Project" in SMUS UI

2. **Client → AccountProvider Lambda**: `listAuthorizedAccountsRequest` — get list of AVAILABLE pool accounts

3. **Client picks one account** from the returned list

4. **Client → DataZone**: `get_project_profile` — get the list of environment configuration names declared in the profile

5. **Client → DataZone**: `CreateProject` with **`userParameters`** — each environment config name explicitly mapped to the chosen account ID + `sourceAccountPoolId`
   > ⚠️ **This step is mandatory.** Without `userParameters`, DataZone returns `FAILED_VALIDATION: EnvironmentConfigurations require a resolved account on input`. DataZone does NOT auto-resolve the account — the caller must pass it.

6. **DataZone → AccountProvider Lambda**: `validateAccountAuthorizationRequest` — confirms the account is valid and marks it ASSIGNED

7. **DataZone deploys project** CloudFormation stacks to the specified account

8. **`overallDeploymentStatus`** transitions: `IN_PROGRESS` → `SUCCESSFUL`

**Example `userParameters` structure** (required for each env config in the profile):
```python
user_params = [
    {
        'environmentConfigurationName': 'Tooling',   # one entry per env config
        'environmentResolvedAccount': {
            'awsAccountId': '123456789012',           # from AccountProvider
            'regionName': 'us-east-2',
            'sourceAccountPoolId': 'c5r1rtjwi2qhbd'  # from list_account_pools
        }
    },
    # ... repeat for every env config name in the profile
]
```

**Lambda Activated**: Account Provider Lambda (Domain Account)
- `listAuthorizedAccountsRequest`: queries DynamoDB PoolIndex GSI for AVAILABLE accounts in the matching pool, returns list
- `validateAccountAuthorizationRequest`: confirms account is AVAILABLE/ASSIGNED, marks ASSIGNED, triggers PoolManager replenishment

**Result**: User gets instant project creation (< 5 seconds) because account is already configured

### Step 2: Pool Detects Assignment and Replenishes

When DataZone deploys the project to the assigned account, CloudFormation events trigger the Pool Manager Lambda. The Pool Manager marks the account as ASSIGNED in DynamoDB, then checks if the pool size dropped below the minimum threshold (default: 5 accounts).

If replenishment is needed, the Pool Manager invokes the ProvisionAccount Lambda (in Org Admin account) to create new accounts, then invokes the Setup Orchestrator Lambda (in Domain account) to configure them. The entire process takes 6-8 minutes per account, but happens in the background while the pool continues serving other users.

**Result**: Pool automatically maintains the target size (default: 10 accounts) without manual intervention

## Event Flow Summary

```
User Creates Project (SMUS)
  ↓
Account Provider Lambda → Returns available account
  ↓
CloudFormation Events → Pool Manager detects assignment
  ↓
Pool Manager → Triggers replenishment if needed
  ↓
ProvisionAccount Lambda → Creates new account (Org Admin)
  ↓
Setup Orchestrator Lambda → Configures account in 2 waves (Domain)
  ↓
Account Available → Ready for next user
```

## Account Lifecycle with Recycling

```
┌─────────────────────────────────────────────────────────────┐
│                    Account Lifecycle                         │
└─────────────────────────────────────────────────────────────┘

CREATE PATH (New Account):
  ProvisionAccount → SETTING_UP → Setup Orchestrator → AVAILABLE

ASSIGNMENT PATH:
  AVAILABLE → User Creates Project → ASSIGNED

RECLAIM PATH (DELETE Strategy):
  ASSIGNED → Project Deleted → Removed from Pool
  
RECLAIM PATH (REUSE Strategy):
  ASSIGNED → Project Deleted → CLEANING → DeprovisionAccount
    ├─ Success → AVAILABLE (back to pool)
    └─ Failure → FAILED (blocks replenishment)

FAILURE HANDLING:
  FAILED → Manual Investigation → Delete from Pool → Replenishment Unblocked
```

**State Transitions**:
- `SETTING_UP`: Account being configured by Setup Orchestrator (6-8 minutes)
- `AVAILABLE`: Ready for assignment, in pool inventory
- `ASSIGNED`: In use by a project
- `CLEANING`: Being cleaned by DeprovisionAccount (10-15 minutes)
- `FAILED`: Setup or cleanup failed, requires manual intervention

**Force recycling**: The AccountRecycler supports `force=true` to recycle accounts that are stuck:
- `AVAILABLE + force`: Re-runs full deprovision → setup cycle (useful for incomplete setup)
- `ASSIGNED + force`: Transitions to CLEANING and runs deprovision → setup (use when account is ASSIGNED but has no real backing project — e.g. from manual testing or edge cases)

## Key Design Decisions

### Why Pre-Configure Accounts?

**Problem**: 6-8 minute wait frustrates users
**Solution**: Accounts ready before users need them
**Trade-off**: Small pool maintenance cost vs. instant user experience

### Why Event-Driven Replenishment?

**Problem**: Time-based polling wastes Lambda invocations
**Solution**: CloudFormation events trigger replenishment only when needed
**Benefit**: Lower costs, immediate response to demand

### Why Cross-Account Lambda for Provisioning?

**Problem**: Setup Orchestrator needs Organizations API access (security risk)
**Solution**: Separate ProvisionAccount Lambda in Org Admin account
**Benefit**: Least-privilege security, ExternalId protection from the start

### Why Wave-Based Parallel Execution?

**Problem**: Sequential deployment takes 10-12 minutes
**Solution**: Deploy independent resources in parallel waves
**Benefit**: 45% faster (5.5 minutes), maximizes parallelization by eliminating false dependencies

### Why Two Reclaim Strategies (DELETE vs REUSE)?

**Problem**: Different organizations have different priorities (compliance vs cost vs speed)
**Solution**: Configurable ReclaimStrategy via SSM parameter

**DELETE Strategy** (default):
- Accounts removed from pool after project deletion
- Accounts remain in AWS Organizations (manual cleanup required)
- Pool replenishes by creating new accounts
- **Use when**: Compliance requires fresh accounts, account limits not a concern
- **Pros**: Simple, no cleanup complexity, guaranteed clean state
- **Cons**: Slower replenishment, higher costs, account limit pressure

**REUSE Strategy** (cost-optimized):
- Accounts cleaned and returned to pool after project deletion
- DeprovisionAccount removes all project resources automatically
- Pool reuses existing accounts instead of creating new ones
- **Use when**: Cost optimization important, account limits constrained
- **Pros**: Faster replenishment (no account creation), lower costs, stays within limits
- **Cons**: Cleanup complexity, potential for cleanup failures, requires monitoring

**Configuration**: Set `/AccountPoolFactory/PoolManager/ReclaimStrategy` SSM parameter to `DELETE` or `REUSE`

## Detailed Component Architecture

This section describes each account type, the resources deployed in it, and how the Lambdas function.

### Organization Admin Account

**Purpose**: Manages AWS Organization and handles secure account provisioning

**Deployed Resources**:
- CloudFormation StackSet Administration Role
- CloudFormation StackSets:
  - `SMUS-AccountPoolFactory-StackSetExecution` - Deploys execution role to new accounts
  - `SMUS-AccountPoolFactory-DomainAccess` - Deploys cross-account access role with ExternalId
- ProvisionAccount Lambda function
- CloudWatch Logs for Lambda execution

**Lambda: ProvisionAccount**

**Trigger**: Cross-account invocation from Pool Manager Lambda (Domain Account)

**What it does**:
1. Creates account via Organizations API (~1 minute)
2. Moves account to target OU
3. Deploys StackSet execution role to new account
4. Deploys SMUS-AccountPoolFactory-DomainAccess role with ExternalId protection
5. Waits for IAM role propagation
6. Returns ready-to-use account ID

**Why it exists**: This is the only Lambda that touches OrganizationAccountAccessRole (no ExternalId). By isolating account creation in the Org Admin account, we prevent the Setup Orchestrator from having Organizations API access, which would be a security risk.

**IAM Permissions**:
- Organizations: CreateAccount, DescribeAccount, MoveAccount, ListParents
- STS: AssumeRole (OrganizationAccountAccessRole in any account)
- CloudFormation: CreateStack, DescribeStacks, CreateStackInstances, DescribeStackSetOperation

**Resource Policy**: Allows Domain account Pool Manager to invoke cross-account

### Domain Account

**Purpose**: Hosts SageMaker Unified Studio, DataZone, and all automation infrastructure

**Deployed Resources**:
- SageMaker Unified Studio domain
- DataZone domain
- DynamoDB table: `AccountPoolFactory-AccountState`
- EventBridge central bus: `AccountPoolFactory-CentralBus`
- SNS topic: `AccountPoolFactory-Alerts`
- SQS queue: `AccountPoolFactory-SetupQueue` (controls SetupOrchestrator parallelism)
- SQS DLQ: `AccountPoolFactory-SetupQueue-DLQ` (captures failed setup jobs after 3 attempts)
- SSM parameters: `/AccountPoolFactory/*` (configuration)
- Four Lambda functions:
  - Account Provider Lambda
  - Pool Manager Lambda
  - Setup Orchestrator Lambda
  - DeprovisionAccount Lambda
- CloudWatch dashboards (4 dashboards)
- CloudWatch Logs for all Lambdas

**Lambda: Account Provider**

**Trigger**: DataZone API calls (`list-accounts-in-account-pool`, `validate-account-authorization`)

**What it does**:
1. Queries DynamoDB StateIndex GSI for AVAILABLE accounts
2. Returns account ID and region to DataZone
3. Publishes CloudWatch metrics
4. Sends SNS alert if pool is empty

**Why it exists**: DataZone needs a Lambda to query the account pool. This Lambda is the integration point between DataZone and the pool management system.

**IAM Permissions**:
- DynamoDB: Query (StateIndex GSI)
- CloudWatch: PutMetricData
- SNS: Publish

**Lambda: Pool Manager**

**Trigger**: CloudFormation events from EventBridge central bus

**What it does**:
1. Detects account assignment from CREATE_IN_PROGRESS events
2. Updates DynamoDB to mark account as ASSIGNED
3. Checks pool size against minimum threshold
4. Blocks replenishment if failed accounts exist
5. Invokes ProvisionAccount Lambda (cross-account) to create new accounts
6. Creates DynamoDB records for new accounts (state: SETTING_UP)
7. Enqueues setup jobs to `AccountPoolFactory-SetupQueue` — SetupOrchestrator picks them up at controlled concurrency
8. Handles account deletion and reclamation:
   - DELETE strategy: Removes account from pool (account still exists in Organizations)
   - REUSE strategy: Invokes DeprovisionAccount Lambda to clean and recycle account

**Why it exists**: This is the orchestrator for pool-level operations. It monitors pool health, triggers replenishment, and manages the account lifecycle including account recycling.

**IAM Permissions**:
- Lambda: InvokeFunction (ProvisionAccount in Org Admin, DeprovisionAccount in Domain)
- SQS: SendMessage (AccountPoolFactory-SetupQueue)
- DynamoDB: Query, PutItem, UpdateItem, DeleteItem
- SNS: Publish
- CloudWatch: PutMetricData
- SSM: GetParameter, GetParameters
- STS: AssumeRole (SMUS-AccountPoolFactory-DomainAccess for checking remaining stacks in project accounts)

**Configuration** (SSM Parameters):
- PoolName, TargetOUId, MinimumPoolSize (default: 5), TargetPoolSize (default: 10)
- MaxConcurrentSetups (default: 3), ReclaimStrategy (DELETE or REUSE)
- ProvisionAccountLambdaArn (ARN in Org Admin account)

**Lambda: Setup Orchestrator**

**Trigger**: SQS queue `AccountPoolFactory-SetupQueue` (event source mapping, `BatchSize=1`, `MaxConcurrency=10`)

**Parallelism control**: The SQS event source mapping `MaxConcurrency` setting is the single knob controlling how many SetupOrchestrator instances run simultaneously. Default is 10 (processes 200 accounts in ~2.5 hours). Adjustable via SSM parameter `/AccountPoolFactory/PoolManager/SetupQueueMaxConcurrency` without redeployment.

**Why SQS instead of direct invoke**: Previously the Recycler invoked SetupOrchestrator synchronously, holding a thread open for 6-8 minutes per account. With 10 concurrent threads this caused Lambda throttling (`TooManyRequestsException`) which incorrectly incremented retry counters and permanently stuck accounts. SQS decouples the enqueue from execution — Recycler/PoolManager enqueue instantly, SQS delivers at the configured rate.

**What it does**:
1. Unwraps SQS record (or accepts direct invocation for backward compatibility)
2. Validates account exists in DynamoDB
3. Checks for idempotency (skips if already AVAILABLE)
4. Executes 2-wave configuration workflow:
   - Wave 1: Foundation + Domain Access (parallel, ~2.5 min)
     - VPC deployment with 3 private subnets
     - IAM roles (ManageAccessRole, ProvisioningRole)
     - Project execution role (AmazonSageMakerProjectRole)
     - EventBridge rules for event forwarding
     - S3 bucket for blueprint artifacts
     - Domain visibility verification (via org-wide RAM share — no per-account share created)
   - Wave 2: Blueprint Enablement (~3 min)
     - Enable 17 DataZone blueprints with VPC/S3 regional parameters
     - Deploy 17 `AWS::DataZone::PolicyGrant` resources (CREATE_ENVIRONMENT_FROM_BLUEPRINT)
5. Supports `mode: updateBlueprints` — updates only the Blueprints stack without deprovisioning
6. Updates DynamoDB with progress after each wave
7. Marks account as AVAILABLE when complete

**Why it exists**: This Lambda handles the complex multi-step configuration workflow. By using wave-based parallel execution and eliminating false dependencies, it reduces setup time from 10-12 minutes to 5.5 minutes.

**IAM Permissions**:
- CloudFormation: CreateStack, DescribeStacks, DeleteStack
- DataZone: ListDomains, GetDomain, CreatePolicyGrant
- RAM: CreateResourceShare, GetResourceShares, AssociateResourceShare
- S3: CreateBucket, PutBucketVersioning, PutBucketEncryption
- DynamoDB: PutItem, UpdateItem, GetItem
- SNS: Publish
- CloudWatch: PutMetricData
- SSM: GetParameter
- STS: AssumeRole (SMUS-AccountPoolFactory-DomainAccess role with ExternalId)

**Configuration** (SSM Parameters):
- DomainId, DomainAccountId, RootDomainUnitId, Region
- RetryConfig (exponential backoff for failures)

**Lambda: DeprovisionAccount**

**Trigger**: Async invocation from Pool Manager Lambda (when ReclaimStrategy=REUSE)

**What it does**:
1. Assumes SMUS-AccountPoolFactory-DomainAccess role in project account (with ExternalId)
2. Lists all CloudFormation stacks in the account
3. Categorizes stacks:
   - Approved infrastructure (AccountPoolFactory-*, StackSet-*) - protected, never deleted
   - Project stacks (DataZone-*, user-created) - must be deleted
4. Builds dependency graph from stack exports/imports
5. Performs reverse topological sort to determine safe deletion order
6. Deletes project stacks sequentially with retry logic
7. Waits for each stack deletion to complete (timeout: 10 minutes per stack)
8. Updates DynamoDB state:
   - Success: CLEANING → AVAILABLE (account returned to pool)
   - Failure: CLEANING → FAILED (manual intervention required)
9. Publishes CloudWatch metrics and SNS notifications

**Why it exists**: Account recycling (REUSE strategy) reduces costs and speeds up replenishment by cleaning existing accounts instead of creating new ones. This Lambda safely removes all project resources while preserving the approved infrastructure, allowing accounts to be reused multiple times.

**IAM Permissions** (shares SetupOrchestratorRole):
- CloudFormation: ListStacks, DescribeStacks, DeleteStack, DescribeStackEvents
- DynamoDB: Query, UpdateItem
- SNS: Publish
- CloudWatch: PutMetricData
- STS: AssumeRole (SMUS-AccountPoolFactory-DomainAccess role with ExternalId)

**Configuration** (Environment Variables):
- DELETION_TIMEOUT (default: 600 seconds per stack)
- MAX_RETRIES (default: 3 attempts per stack)
- DOMAIN_ID (for ExternalId in cross-account role assumption)

**Error Handling**:
- Stack deletion failures mark account as FAILED with detailed error information
- Failed accounts block pool replenishment until manually resolved
- SNS notifications sent for both success and failure cases
- CloudWatch metrics track cleanup duration and success rate

### Project Account (Pool)

**Purpose**: Pre-configured accounts ready for SageMaker Unified Studio project assignment

**Deployed Resources** (after Setup Orchestrator completes):
- VPC with 3 private subnets across 3 availability zones
- IAM roles:
  - ManageAccessRole (DataZone project management)
  - ProvisioningRole (DataZone environment provisioning)
  - SMUS-AccountPoolFactory-DomainAccess (cross-account access with ExternalId)
  - SMUS-AccountPoolFactory-StackSetExecution (StackSet deployments)
- EventBridge rules (forward events to Domain account central bus)
- S3 bucket for blueprint artifacts (versioned, encrypted)
- RAM share for DataZone domain access
- 17 enabled DataZone blueprints with policy grants
- CloudFormation stacks for all above resources

**State in DynamoDB**: AVAILABLE (ready for assignment)

**What happens when assigned**:
1. DataZone deploys project CloudFormation stacks
2. CloudFormation events trigger Pool Manager
3. DynamoDB state changes: AVAILABLE → ASSIGNED
4. Account removed from pool inventory

**What happens when deleted**:
1. User deletes project in SMUS UI
2. DataZone deletes project CloudFormation stacks
3. CloudFormation DELETE_COMPLETE events trigger Pool Manager
4. Pool Manager checks for remaining DataZone stacks in the account
5. Account reclamation based on ReclaimStrategy:
   
   **DELETE Strategy** (default):
   - Pool Manager removes account from DynamoDB
   - Account still exists in AWS Organizations (manual deletion required)
   - Pool replenishes by creating new accounts
   - Use case: Compliance requirements, account limits not a concern
   
   **REUSE Strategy** (cost-optimized):
   - Pool Manager invokes DeprovisionAccount Lambda
   - DynamoDB state: ASSIGNED → CLEANING
   - DeprovisionAccount removes all project stacks (preserves infrastructure)
   - Stack deletion in reverse dependency order (10-15 minutes typical)
   - On success: DynamoDB state CLEANING → AVAILABLE (account returned to pool)
   - On failure: DynamoDB state CLEANING → FAILED (blocks replenishment, requires manual fix)
   - Pool reuses cleaned accounts instead of creating new ones
   - Use case: Cost optimization, faster replenishment, account limit constraints

**Account Recycling Benefits** (REUSE strategy):
- Reduces AWS account creation costs
- Faster replenishment (no account creation delay)
- Stays within AWS Organizations account limits
- Maintains approved infrastructure (no re-deployment needed)
- Automatic cleanup with dependency-aware deletion

## Account Reconciliation & Recycling

The Account Pool Factory includes two additional Lambda functions for self-healing and account lifecycle management.

### Lambda: AccountReconciler

**Trigger**: EventBridge scheduled rule (hourly) or manual invocation

**Design principle**: Detect-only. The reconciler never fixes anything — it only detects problems and marks accounts FAILED with a descriptive reason. All fixing is delegated to the AccountRecycler.

**What it does**:
1. Assumes `SMUS-AccountPoolFactory-AccountCreation` role in Org Admin account
2. Lists accounts in the Target OU via `list_accounts_for_parent`
3. Filters by name prefix, verifies/backfills `ManagedBy: AccountPoolFactory` + `PoolName` tags
4. Reconciles against DynamoDB:
   - Untracked org accounts → creates ORPHANED records
   - AVAILABLE accounts → validates DomainAccess role + all 5 setup stacks
   - DynamoDB records with no matching org account → SUSPENDED
5. Marks unhealthy AVAILABLE accounts as FAILED with descriptive reason:
   - `NEEDS_STACKSET: DomainAccess role not assumable`
   - `NEEDS_SETUP: Missing: DataZone-VPC-*, DataZone-Blueprints-*, ...`
6. Publishes CloudWatch metrics
7. With `autoRecycle=true`: invokes AccountRecycler for FAILED/ORPHANED accounts
8. With `autoReplenish=true`: invokes Pool Manager if AVAILABLE < MinimumPoolSize

**IAM Role**: `SMUS-AccountPoolFactory-AccountReconciler-Role`

### Lambda: AccountRecycler

**Trigger**: Invoked by AccountReconciler (`autoRecycle=true`), EventBridge, or manual invocation

**Design principle**: The fixer. Routes accounts based on failure reason, fixes in parallel, self-triggers near the 900s timeout so processing continues across Lambda invocations.

**What it does**:
1. Pre-processes `NEEDS_STACKSET` accounts as a single batch StackSet operation (avoids `OperationInProgressException` from concurrent calls)
2. Processes accounts based on state + failure reason:
   - `NEEDS_STACKSET` → deploy DomainAccess StackSet → run SetupOrchestrator → AVAILABLE
   - `NEEDS_SETUP` → run SetupOrchestrator (idempotent, skips healthy stacks) → AVAILABLE
   - `CLEANING` → DeprovisionAccount → SetupOrchestrator → AVAILABLE
   - `ORPHANED` → ensure StackSet → SetupOrchestrator → AVAILABLE
3. Recoverable failures (NEEDS_SETUP, NEEDS_STACKSET) auto-reset retryCount — never permanently stuck
4. Near 900s timeout: checks for remaining work, self-triggers async, returns
5. `updateBlueprints` mode: updates Blueprints stack on all AVAILABLE accounts (rolling, no deprovision)

**IAM Role**: `SMUS-AccountPoolFactory-AccountRecycler-Role`

**Throttle resilience**: Transient `TooManyRequestsException` errors on Lambda invocations do not increment the retry counter. The account's retry count is reset and the next reconciler cycle retries cleanly.

### Self-Healing Loop

```
EventBridge (rate: 1 hour)
  │
  └─► AccountReconciler
        ├─ Lists all pool accounts in target OU
        ├─ Validates AVAILABLE accounts (role + stacks)
        ├─ Marks unhealthy → FAILED (with reason)
        └─ autoRecycle=true → invokes AccountRecycler
                │
                └─► AccountRecycler
                      ├─ Batch StackSet fix for NEEDS_STACKSET accounts
                      ├─ Enqueues NEEDS_SETUP / CLEANING / ORPHANED accounts → SQS
                      └─ Returns immediately (no thread blocking)
                                │
                                └─► SQS AccountPoolFactory-SetupQueue
                                      │  (MaxConcurrency=10, one message per account)
                                      └─► SetupOrchestrator × N (parallel, controlled)
                                            └─► All accounts → AVAILABLE
```

## Domain Access: Org-Wide RAM Share

Instead of creating individual RAM shares per pool account (which caused resource policy bloat with 200+ shares), the system uses a single org-wide RAM share:

- **Share name**: `DataZone-Domain-Share-OrgWide`
- **Principal**: OU ARN (`arn:aws:organizations::ACCOUNT:ou/ORG/OU-ID`)
- **Resource**: DataZone domain ARN
- **Coverage**: All accounts in the target OU automatically see the domain

This eliminates per-account RAM share creation from the SetupOrchestrator workflow. The `create_ram_share_and_verify_domain()` function now just verifies domain visibility without creating any shares.

## Blueprint Policy Grants

Each pool account's `DataZone-Blueprints-{account_id}` CloudFormation stack includes 17 `AWS::DataZone::PolicyGrant` resources (one per blueprint). These grants:

- Allow CONTRIBUTOR projects in the root domain unit (and all child units) to create environments from each blueprint
- Are deployed via CloudFormation using the domain's service role — the Admin IAM role cannot call `AddPolicyGrant` directly for `ENVIRONMENT_BLUEPRINT_CONFIGURATION` entity type
- Use `EntityIdentifier: {AWS::AccountId}:{BlueprintId}` which auto-resolves to the correct account

This means policy grants are automatically applied when SetupOrchestrator deploys the blueprint stack — no separate grant step needed per account.





---

## Navigation

[← Back to README](../README.md) | [Org Admin Guide](OrgAdminGuide.md) | [Domain Admin Guide](DomainAdminGuide.md) | [Security Guide](SecurityGuide.md) | [Testing Guide](TestingGuide.md)

---

## Known Limitations

### ON_CREATE Not Supported with Account Pools

DataZone account pools only support `MANUAL` resolution strategy. Environment configurations with `ON_CREATE` deployment mode do not work — the Lambda is never invoked during project creation for ON_CREATE environments.

**Impact**: All environment configurations in pool-backed project profiles must use `ON_DEMAND` deployment mode. Users create environments manually after project creation.

**Consequence for project creation**: The client (script or UI) must explicitly resolve the account before calling `CreateProject`. It must call `listAuthorizedAccountsRequest` first, pick an account, then pass it in `userParameters` for every environment config. See the call sequence in Step 1 above.

### StackSet Operations Are Serialized

CloudFormation StackSets only allow one operation at a time per StackSet. When the recycler processes multiple `NEEDS_STACKSET` accounts concurrently, it batches them into a single `create_stack_instances` call with all account IDs to avoid `OperationInProgressException`.

### Lambda Timeout for Large Pools

The AccountRecycler has a 900s Lambda timeout. With 200+ accounts to process, it self-triggers near the timeout to continue in the next invocation. Each wave processes ~10 accounts concurrently (~5 min per wave for setup).

---

## Project Structure

```
AccountPoolFactory/
├── 01-org-account/                              # Org admin governance (pool-agnostic)
│   ├── config.yaml                              # Approved stacksets, OU definitions
│   ├── scripts/
│   │   ├── deploy/
│   │   │   ├── 01-deploy.sh                     # Deploy governance stack + upload stacksets + write SSM
│   │   │   └── 02-verify.sh                     # Verify CF stack, IAM roles, StackSets, per-OU SSM
│   │   ├── cleanup/cleanup.sh
│   │   └── resolve-config.sh                    # Org config resolution
│   └── templates/cloudformation/
│       └── SMUS-AccountPoolFactory-OrgAdmin.yaml  # IAM roles + S3 bucket CF stack
│
├── 02-domain-account/                           # Domain admin pool management
│   ├── config.yaml                              # Pool definitions (sizing, stacksets, OU mapping)
│   ├── scripts/
│   │   ├── deploy/
│   │   │   ├── 01-deploy.sh                     # Deploy infrastructure stack + all Lambdas
│   │   │   ├── 02-deploy-project-profile.sh     # Create/update DataZone project profile
│   │   │   ├── 03-verify.sh                     # Verify stack, Lambdas, DynamoDB, domain, pool
│   │   │   ├── 04-seed-pool.sh                  # Trigger initial pool replenishment
│   │   │   └── 05-start-ui.sh                   # Start web UI (mock or live mode)
│   │   ├── cleanup/cleanup.sh
│   │   ├── resolve-config.sh                    # Domain config resolution
│   │   └── utils/                               # Operational utilities
│   │       ├── check-pool-status.sh
│   │       ├── check-account-state.sh
│   │       ├── monitor-pool.py
│   │       └── ...
│   └── templates/cloudformation/
│       └── 01-infrastructure.yaml               # DynamoDB, Lambdas, EventBridge, SNS, SSM
│
├── approved-stacksets/                          # StackSet templates (org-approved)
│   └── cloudformation/
│       ├── idc/                                 # IDC domain templates (uploaded to S3 by org deploy)
│       │   ├── 01-domain-access.yaml
│       │   ├── 02-vpc-setup.yaml
│       │   ├── 03-iam-roles.yaml
│       │   ├── 04-eventbridge-rules.yaml
│       │   ├── 05-project-role.yaml
│       │   ├── 06-blueprint-enablement.yaml
│       │   └── 07-glue-lf-test-data.yaml
│       └── iam/                                 # IAM domain templates (not currently used)
│           └── 06-blueprint-enablement.yaml
│
├── src/                                         # Lambda source code
│   ├── account-provider/lambda_function_prod.py
│   ├── pool-manager/lambda_function.py
│   ├── setup-orchestrator/lambda_function.py
│   ├── deprovision-account/lambda_function.py
│   ├── provision-account/lambda_function.py
│   ├── account-reconciler/lambda_function.py
│   └── account-recycler/lambda_function.py
│
├── ui/
│   ├── mock-server.py          # Dev server (mock + live mode, hot reload)
│   ├── pool-console/           # Pool health, account states, ops
│   └── project-creator/        # Create projects interactively
│
├── tests/                      # Integration and setup tests
└── docs/
```

## Lambda Packaging

`SetupOrchestrator` zip bundles both the Python source and all CF templates from `approved-stacksets/cloudformation/idc/` flat — the Lambda reads them directly at runtime via `open(template_path)`. The deploy script handles this automatically:

```bash
zip setup-orchestrator.zip -j src/setup-orchestrator/lambda_function.py
zip setup-orchestrator.zip -j approved-stacksets/cloudformation/idc/*.yaml
```

## Scripts Reference

| Script | Account | What it does |
|--------|---------|-------------|
| `01-org-account/scripts/deploy/01-deploy.sh` | Org Admin | CF stack + S3 upload + per-OU SSM params + StackSet definitions |
| `01-org-account/scripts/deploy/02-verify.sh` | Org Admin | Verify CF stack, IAM roles, StackSets, per-OU SSM |
| `02-domain-account/deploy/01-deploy.sh [--lambdas-only]` | Domain | Infrastructure CF stack + all 7 Lambdas |
| `02-domain-account/deploy/02-deploy-project-profile.sh` | Domain | Create/update DataZone project profile with account pool |
| `02-domain-account/scripts/deploy/03-verify.sh` | Domain | Verify stack, Lambdas, DynamoDB, domain, pool, profile |
| `02-domain-account/scripts/deploy/04-seed-pool.sh [pool-name]` | Domain | Trigger initial replenishment |
| `02-domain-account/scripts/deploy/05-start-ui.sh [--live]` | Domain | Start web UI |
| `02-domain-account/scripts/utils/check-pool-status.sh` | Domain | Account counts by state + recent logs |
| `02-domain-account/scripts/utils/check-account-state.sh <account-id>` | Domain | DynamoDB record + CF stacks for one account |
| `02-domain-account/scripts/utils/invoke-reconciler.sh` | Domain | Run reconciler with options |
| `02-domain-account/scripts/utils/invoke-recycler.sh` | Domain | Run recycler with options |
| `02-domain-account/scripts/utils/cleanup-failed-accounts.sh` | Domain | Remove FAILED accounts to unblock replenishment |
| `02-domain-account/scripts/utils/clear-dynamodb-table.sh` | Domain | ⚠️ Wipe all pool state |
