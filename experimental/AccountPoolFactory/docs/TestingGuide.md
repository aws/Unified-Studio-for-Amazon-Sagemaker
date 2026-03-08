# Account Pool Factory - Testing Guide

Step-by-step guide for deploying and testing the Account Pool Factory from scratch, starting with clean AWS accounts.

## Account Setup Options

| Setup | Accounts | Use Case |
|-------|----------|----------|
| Multi-Account (recommended) | 3: Org Admin, Domain, Project accounts | Production-like, full isolation |
| Single-Account | 1: Everything in one account | Quick testing, limited isolation |

This guide covers the multi-account setup. For single-account, see [Single Account Setup](#single-account-setup) at the end.

## Prerequisites

- AWS CLI installed and configured
- Python 3.12+
- 3 AWS accounts (or ability to create them):
  - **Org Admin account** — manages AWS Organizations and account creation
  - **Domain account** — hosts SageMaker Unified Studio / DataZone domain
  - **Project account(s)** — created by the pool, assigned to users
- AWS Organizations enabled in the Org Admin account
- A DataZone domain created in the Domain account (via SageMaker Unified Studio console)

### Configuration

```bash
cd experimental/AccountPoolFactory
cp config.yaml.template config.yaml
# Edit config.yaml with your account IDs, domain ID, region, etc.
```

Key config values:
- `aws.region` — e.g., `us-east-2`
- `aws.account_id` — Org Admin account ID
- `aws.domain_account_id` — Domain account ID
- `datazone.domain_id` — your DataZone domain ID
- `datazone.root_domain_unit_id` — root domain unit ID
- `organization.target_ou_id` — OU where project accounts will be placed

---

## Multi-Account Deployment

### Overview

```
Step 1-3: Org Admin account (prerequisites + solution deployment)
Step 4-6: Domain account (prerequisites + solution deployment)
Step 7:   Test the solution end-to-end
```

---

## Org Admin Account (account 1)

> Switch to Org Admin account credentials before running these steps.

### Step 1: Create Organization Structure (prerequisite)

Creates OUs in AWS Organizations where project accounts will be placed.

```bash
./tests/setup/deploy-organization.sh
```

**What it does:**
- Deploys `tests/setup/templates/organization-structure.yaml`
- Creates business-unit OUs (e.g., RetailBanking/CustomerAnalytics)
- Saves OU IDs to `ou-ids.json` and updates `config.yaml`

**Template:** `tests/setup/templates/organization-structure.yaml`

**Expected output:**
```
✅ Stack deployed: AccountPoolFactory-Organization-Test
   Target OU: ou-xxxx-xxxxxxxx (RetailBanking/CustomerAnalytics)
```

---

### Step 2: Deploy StackSet Roles (solution)

Creates the IAM roles needed for CloudFormation StackSet administration.

```bash
./scripts/01-org-mgmt-account/deploy/01-deploy-stackset-roles.sh
```

**What it does:**
- Deploys `templates/cloudformation/01-org-mgmt-account/deploy/01-stackset-roles.yaml`
- Creates `SMUS-AccountPoolFactory-StackSetAdmin` role
- Stack name: `AccountPoolFactory-StackSetRoles`

**Expected output:**
```
✅ StackSet roles deployed
   Role: SMUS-AccountPoolFactory-StackSetAdmin
```

---

### Step 3: Deploy ProvisionAccount Lambda + StackSet (solution)

Creates the Lambda that provisions new AWS accounts, and the StackSet that deploys cross-account access roles to project accounts.

```bash
./scripts/01-org-mgmt-account/deploy/02-deploy-provision-account.sh
```

**What it does:**
- Deploys `templates/cloudformation/01-org-mgmt-account/deploy/02-provision-account.yaml`
  - `SMUS-AccountPoolFactory-AccountCreation` role (Organizations API access)
  - `ProvisionAccount` Lambda + execution role
  - Lambda invoke permission for Domain account
- Creates StackSet `SMUS-AccountPoolFactory-DomainAccess` using template `03-domain-access-stackset.yaml`
  - This StackSet deploys `SMUS-AccountPoolFactory-DomainAccess` role to each new project account
- Deploys Lambda code from `src/provision-account/`
- Stack name: `AccountPoolFactory-ProvisionAccount`

**Templates:**
- `templates/cloudformation/01-org-mgmt-account/deploy/02-provision-account.yaml` (CF stack)
- `templates/cloudformation/01-org-mgmt-account/deploy/03-domain-access-stackset.yaml` (StackSet template body, not a standalone stack)

**Expected output:**
```
✅ ProvisionAccount stack deployed
✅ StackSet SMUS-AccountPoolFactory-DomainAccess created
✅ Lambda code deployed
```

### Verify Org Admin Account

Run the verification script to confirm all resources are deployed correctly:

```bash
./scripts/01-org-mgmt-account/deploy/verify-org-mgmt-account.sh
```

---

## Domain Account (account 2)

> Switch to Domain account credentials before running these steps.

### Step 4: Create DataZone Domain (prerequisite)

This is done manually through the SageMaker Unified Studio console.

1. Go to SageMaker Unified Studio console in your Domain account
2. Create a new domain
3. Note the Domain ID (`dzd-xxxxxxxxxxxxxx`) and Root Domain Unit ID
4. Update `config.yaml` with these values

The domain will be verified as part of the domain account verification script in Step 8.

---

### Step 5: Deploy Infrastructure (solution)

Deploys all Account Pool Factory infrastructure to the Domain account in a single stack + Lambda code packages.

```bash
./scripts/02-domain-account/deploy/01-deploy-infrastructure.sh
```

**What it does:**
- Deploys `templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml`
  - DynamoDB table: `AccountPoolFactory-AccountState`
  - SNS topic: `AccountPoolFactory-Alerts`
  - EventBridge bus: `AccountPoolFactory-CentralBus`
  - 4 Lambda functions: PoolManager, SetupOrchestrator, DeprovisionAccount, AccountProvider
  - 4 IAM roles (all `SMUS-AccountPoolFactory-*` prefixed)
  - SSM parameters under `/AccountPoolFactory/*`
  - CloudWatch Log Group for AccountProvider
- Deploys Lambda code from:
  - `src/pool-manager/lambda_function.py`
  - `src/setup-orchestrator/lambda_function.py` (+ CF templates from `03-project-account/deploy/`)
  - `src/deprovision-account/lambda_function.py`
  - `src/account-provider/lambda_function_prod.py`
- Stack name: `AccountPoolFactory-Infrastructure`

**Expected output:**
```
✅ Infrastructure stack deployed
✅ Pool Manager code updated
✅ Setup Orchestrator code updated
✅ DeprovisionAccount code updated
✅ AccountProvider code updated
```

---

### Step 6: Add Policy Grant for Project Profile

Adds the "All Capabilities - Account Pool" profile to the domain unit's `CREATE_PROJECT_FROM_PROJECT_PROFILE` grant. This is a one-time domain-level operation.

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
bash tests/setup/deploy-policy-grants-cf.sh
```

**What it does**:
- Reads current grants on the root domain unit
- Adds a new grant for profile `5riu03k7l71zc9` (All Capabilities - Account Pool)
- Does NOT touch existing grants for other profiles

> Note: `CREATE_ENVIRONMENT_FROM_BLUEPRINT` grants are now embedded directly in the `blueprint-enablement-iam.yaml` template and deployed automatically per pool account via SetupOrchestrator. No separate per-account grant step needed.

---

### Step 7: Create DataZone Account Pool (prerequisite)

Creates the DataZone account pool that connects to the AccountProvider Lambda. This pool is what DataZone uses to request accounts for new projects.

```bash
./tests/setup/04-create-account-pool.sh
```

**What it does:**
- Looks up the `AccountProvider` Lambda ARN and role ARN
- Creates a DataZone account pool named `AccountPoolFactory` with `MANUAL` resolution strategy
- Links the pool to the AccountProvider Lambda
- Saves pool details to `account-pool-details.json`

**Script:** `tests/setup/04-create-account-pool.sh`

**Expected output:**
```
🚀 Creating DataZone Account Pool
==================================
Lambda Function ARN: arn:aws:lambda:us-east-2:994753223772:function:AccountProvider
Lambda Role ARN: arn:aws:iam::994753223772:role/SMUS-AccountPoolFactory-AccountResolution-Role

📦 Creating account pool...

✅ Account pool created successfully!
Pool ID: xxxxxxxxxx
Pool Name: AccountPoolFactory
Resolution Strategy: MANUAL
```

---

### Step 8: Deploy Project Profile (solution)

Creates the DataZone project profile that uses the account pool. This profile defines which blueprints are available and connects them to the pool for automatic account assignment.

```bash
./scripts/02-domain-account/deploy/02-deploy-project-profile.sh
```

**What it does:**
- Reads the account pool ID from `account-pool-details.json` (or fetches from DataZone)
- Fetches all blueprint IDs from the domain
- Deploys `templates/cloudformation/02-domain-account/deploy/02-project-profile-with-pool.yaml`
- Stack name: `AccountPoolFactory-ProjectProfile`

**Script:** `scripts/02-domain-account/deploy/02-deploy-project-profile.sh`

**Expected output:**
```
🚀 Deploying Project Profile with Account Pool
================================================
Account Pool ID: xxxxxxxxxx

📋 Fetching blueprint IDs from domain...
  LakehouseCatalog: bp-xxxxxxxx
  Tooling: bp-xxxxxxxx
  ...

📦 Deploying project profile stack...
✅ Project profile deployed!
```

### Verify Domain Account

Run the verification script to confirm all resources are deployed correctly:

```bash
./scripts/02-domain-account/deploy/verify-domain-account.sh
```

---

## End-to-End Testing

> Stay in Domain account credentials for these steps.

### Step 9: Seed the Account Pool

Triggers the Pool Manager Lambda to create the initial set of project accounts. The Pool Manager calls the ProvisionAccount Lambda in the Org Admin account, which creates new AWS accounts via Organizations.

```bash
./tests/setup/03-seed-test-accounts.sh
```

**What it does:**
- Invokes `PoolManager` Lambda with `{"action":"force_replenishment"}`
- Pool Manager creates accounts up to `minimum_pool_size` (configured in `config.yaml`)
- Each account goes through: `CREATING` → `PROVISIONING` → `AVAILABLE`

**Script:** `tests/setup/03-seed-test-accounts.sh`

**Expected output:**
```
🌱 Seeding initial account pool
================================
🚀 Triggering pool replenishment...
📄 Response:
{"statusCode": 200, "body": "Pool replenishment triggered"}
```

**Monitor progress:**
```bash
./scripts/utils/check-pool-status.sh
```

This shows account counts by state (CREATING → PROVISIONING → AVAILABLE) and recent Lambda logs.

> Account creation takes several minutes per account. The StackSet `SMUS-AccountPoolFactory-DomainAccess` will automatically deploy the domain access role to each new account.

---

### Step 10: Create a Test Project (IDC Domain)

Creates a DataZone project using the pool-backed profile. This is the real end-to-end test.

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
python3 .test-create-from-pool-IDC.py
```

**What it does**:
1. Calls AccountProvider Lambda to get an available pool account
2. Looks up the `default_project_owner` SSO user from config.yaml
3. Creates project with all 17 env configs pointing to the pool account + pool ID
4. Adds the owner as PROJECT_OWNER
5. Polls until deployment completes
6. Prints result + portal URL

**Expected output**:
```
Running in domain account 994753223772
Pool has 100 available accounts
Using account: 054012425702
Owner 'analyst1-amirbo': 9a6721e929-...

Creating project 'test-pool-idc-1772979085'...
  Project created: adwbpi493gd9k9
  Owner added: analyst1-amirbo

Polling...
  [1] ACTIVE  IN_PROGRESS
  [3] ACTIVE  SUCCESSFUL_DEPLOYMENT

=== Result ===
  Status:     ACTIVE
  Deployment: SUCCESSFUL_DEPLOYMENT
  No failures ✅
  Portal: https://dzd-4h7jbz76qckoh5.sagemaker.us-east-2.on.aws/projects/adwbpi493gd9k9
```

---

## Cleanup

### Domain Account Cleanup

Deletes all Account Pool Factory infrastructure from the domain account.

> Switch to Domain account credentials first.

```bash
./scripts/02-domain-account/cleanup/cleanup-domain-account.sh
```

**What it deletes:**
- `AccountPoolFactory-Infrastructure` stack (Lambdas, DynamoDB, SNS, IAM roles, SSM params)
- `AccountPoolFactory-ProjectProfile` stack

> This does NOT close accounts in the pool. Accounts must be closed separately via Organizations.

### Org Admin Account Cleanup

Deletes all Account Pool Factory resources from the Org Admin account.

> Switch to Org Admin account credentials first.

```bash
./scripts/01-org-mgmt-account/cleanup/cleanup-org-mgmt-account.sh
```

**What it deletes:**
- `SMUS-AccountPoolFactory-DomainAccess` StackSet (and all instances)
- `AccountPoolFactory-ProvisionAccount` stack
- `AccountPoolFactory-StackSetRoles` stack
- Any legacy StackSets

### Full Cleanup (all accounts)

For a complete teardown of everything including test accounts:

```bash
./scripts/cleanup-all.sh
```

> Review the script before running — it will close test accounts, which is irreversible.

### Test Organization Cleanup

To remove the test OU structure (from Step 1):

> Switch to Org Admin account credentials.

```bash
aws cloudformation delete-stack \
  --stack-name AccountPoolFactory-Organization-Test \
  --region us-east-2
```

---

## Single Account Setup

For simpler setups, the Org Admin and Domain roles can run in the same AWS account. Project accounts are still dynamically created via Organizations.

## Account Reconciliation & Recycling Testing

### Prerequisites

Run all commands from the domain account:
```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
cd experimental/AccountPoolFactory
```

### Check Pool Status

```bash
bash scripts/utils/check-pool-status.sh
```

### Check a Single Account

```bash
# Domain creds → DynamoDB state
bash scripts/utils/check-account-state.sh 054012425702

# Org Admin creds → CloudFormation stacks
eval $(isengardcli credentials amirbo+1@amazon.com)
bash scripts/utils/check-account-state.sh 054012425702
```

### Run Reconciler — Dry Run

```bash
bash scripts/utils/invoke-reconciler.sh --dry-run
```

Shows what would change without writing to DynamoDB.

### Run Reconciler — Live with Auto-Recycle

```bash
bash scripts/utils/invoke-reconciler.sh --auto-recycle
```

Marks unhealthy accounts FAILED and triggers the recycler for them.

### Run Recycler — Single Account

```bash
bash scripts/utils/invoke-recycler.sh --account 054012425702
# Force re-process even if AVAILABLE:
bash scripts/utils/invoke-recycler.sh --account 054012425702 --force
```

### Run Recycler — All Recyclable Accounts (async)

```bash
bash scripts/utils/invoke-recycler.sh --all --async
```

Fires async — recycler self-triggers near 900s timeout until all accounts are healthy.

### Update Blueprints on All Pool Accounts (rolling)

Use this after updating `blueprint-enablement-iam.yaml` to push changes to all 213 accounts without deprovisioning:

```bash
bash scripts/utils/invoke-recycler.sh --update-blueprints --async
```

### End-to-End Test — IDC Domain (current)

Creates a project from the pool using the IDC domain flow. No role configs needed.

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
python3 .test-create-from-pool-IDC.py
```

**What it does**:
1. Calls AccountProvider Lambda to get an available pool account
2. Looks up `analyst1-amirbo` SSO user profile ID
3. Creates project with all 17 env configs pointing to the pool account
4. Adds `analyst1-amirbo` as PROJECT_OWNER
5. Polls until deployment completes
6. Prints result + portal URL

### Test — Domain Account as Environment Account

Creates a project using the domain account itself (no pool). Useful for isolating authorization issues.

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
python3 .test-create-domain-account.py
```

### Monitor Recycler Progress

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
aws logs tail /aws/lambda/AccountRecycler --follow --region us-east-2
```

Key log patterns to watch:
- `Pre-processing N NEEDS_STACKSET accounts as batch` — batch StackSet fix starting
- `[account_id] Blueprints updated` — blueprint update complete
- `Transitioned to AVAILABLE` — account successfully recycled
- `self-trigger` — recycler continuing in next wave

**Differences from multi-account:**
- One account hosts both AWS Organizations management and the DataZone domain
- All scripts (org-mgmt + domain) run against the same account — no credential switching needed
- `config.yaml`: set `aws.account_id` and `aws.domain_account_id` to the same value

**Steps:**
1. Create Organization structure: `./tests/setup/deploy-organization.sh`
2. Deploy StackSet roles: `./scripts/01-org-mgmt-account/deploy/01-deploy-stackset-roles.sh`
3. Deploy ProvisionAccount Lambda + StackSet: `./scripts/01-org-mgmt-account/deploy/02-deploy-provision-account.sh`
4. Create DataZone domain (via SageMaker Unified Studio console)
5. Deploy infrastructure: `./scripts/02-domain-account/deploy/01-deploy-infrastructure.sh`
6. Create account pool: `./tests/setup/04-create-account-pool.sh`
7. Deploy project profile: `./scripts/02-domain-account/deploy/02-deploy-project-profile.sh`
8. Seed and test: same as Steps 9-10 above
