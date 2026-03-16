# Requirements Document

## Introduction

This feature creates a testing infrastructure that provisions sample Glue databases and tables with minimal test data in the domain account (994753223772), registers them in Lake Formation, and shares them to project accounts via a new StackSet template (`07-glue-lf-test-data.yaml`). The StackSet runs in wave 2 alongside VPC/IAM/EventBridge templates, with its only dependency being the wave 1 domain-access role. A phased rollout strategy (single account → fleet-wide) ensures safe deployment.

## Glossary

- **Domain_Account**: AWS account 994753223772 that hosts the DataZone domain, Glue catalog, and Lake Formation resources
- **Org_Admin_Account**: AWS account 495869084367 that manages AWS Organizations and StackSet operations
- **Project_Account**: An AWS account from the pool that is assigned to a DataZone project
- **Create_Test_Data_Script**: The Python script `06-create-test-data.py` that provisions Glue databases, tables, S3 sample data, and Lake Formation registration in the domain account
- **StackSet_07**: The CloudFormation StackSet template `07-glue-lf-test-data.yaml` deployed to project accounts for cross-account Lake Formation sharing
- **Lake_Formation**: AWS Lake Formation service used for fine-grained access control on Glue catalog resources
- **Resource_Link**: A Glue catalog entry in a project account that points to a shared database/table in the domain account
- **IAM_ALLOWED_PRINCIPALS**: A default Glue permission that bypasses Lake Formation access control; must be revoked for LF-only sharing
- **Single_Account_Test**: The Phase 2 integration test (`test-lf-single-account.py`) that validates the full sharing pipeline on one account
- **Fleet_Rollout_Script**: The Phase 3 script (`test-lf-fleet-rollout.py`) that deploys StackSet 07 to all pool accounts
- **Org_Config**: The `01-org-account/config.yaml` file that defines approved StackSets and their wave ordering

## Requirements

### Requirement 1: Create Test Data in Domain Account

**User Story:** As a platform engineer, I want to create sample Glue databases and tables with test data in the domain account, so that I have a known dataset for validating Lake Formation cross-account sharing.

#### Acceptance Criteria

1. WHEN the Create_Test_Data_Script runs, THE Create_Test_Data_Script SHALL create an S3 bucket named `apf-test-data-{account_id}` in us-east-2 and upload CSV sample data files for each table
2. WHEN the Create_Test_Data_Script runs, THE Create_Test_Data_Script SHALL create two Glue databases: `apf_test_customers` and `apf_test_transactions`
3. WHEN the Create_Test_Data_Script runs, THE Create_Test_Data_Script SHALL create Glue tables (`customers`, `transactions`) with columns matching the defined schema and storage descriptors pointing to the S3 CSV data
4. WHEN the Create_Test_Data_Script runs, THE Create_Test_Data_Script SHALL register the S3 bucket location with Lake Formation and grant the domain account full permissions on all databases and tables
5. WHEN the Create_Test_Data_Script runs a second time, THE Create_Test_Data_Script SHALL skip existing resources without error (idempotent behavior)

### Requirement 2: Lake Formation Admin and Permission Setup

**User Story:** As a platform engineer, I want the script to configure Lake Formation admin roles and revoke default IAM permissions, so that Lake Formation is the sole authority for access control on shared databases.

#### Acceptance Criteria

1. WHEN the Create_Test_Data_Script runs, THE Create_Test_Data_Script SHALL add the caller's IAM role as a Lake Formation data lake administrator before creating databases
2. WHEN adding the caller as a Lake Formation admin, THE Create_Test_Data_Script SHALL preserve existing data lake administrators (additive, not replacement)
3. WHEN Glue databases are created, THE Create_Test_Data_Script SHALL revoke IAM_ALLOWED_PRINCIPALS permissions from each database using `batch_revoke_permissions`
4. IF IAM_ALLOWED_PRINCIPALS has already been revoked from a database, THEN THE Create_Test_Data_Script SHALL continue without error


### Requirement 3: StackSet Template for Cross-Account Sharing

**User Story:** As a platform engineer, I want a StackSet template that creates Lake Formation resource links in project accounts, so that project users can access shared test data through their local Glue catalog.

#### Acceptance Criteria

1. THE StackSet_07 SHALL create Glue database resource links in the project account pointing to the shared databases (`apf_test_customers`, `apf_test_transactions`) in the Domain_Account
2. THE StackSet_07 SHALL grant Lake Formation cross-account permissions (`DESCRIBE` on databases, `SELECT` and `DESCRIBE` on tables) to the project account
3. THE StackSet_07 SHALL deploy as a wave 2 StackSet, running in parallel with VPC/IAM/EventBridge templates
4. THE StackSet_07 SHALL depend only on the wave 1 domain-access role and have no dependency on wave 2 IAM roles or wave 3 blueprint enablement

### Requirement 4: Org Config Integration

**User Story:** As a platform engineer, I want the new StackSet template registered in 01-org-account/config.yaml, so that it is automatically deployed during account provisioning.

#### Acceptance Criteria

1. WHEN the StackSet_07 entry is added to Org_Config, THE Org_Config SHALL list it as a wave 2 template with a `# TEST ONLY` comment
2. THE Org_Config SHALL place the StackSet_07 entry alongside existing wave 2 templates (after `05-project-role.yaml` and before `06-blueprint-enablement.yaml`)

### Requirement 5: Single Account Integration Test

**User Story:** As a platform engineer, I want a single-account integration test that validates the full Lake Formation sharing pipeline, so that I can verify correctness before fleet-wide rollout.

#### Acceptance Criteria

1. WHEN the Single_Account_Test runs, THE Single_Account_Test SHALL pick one AVAILABLE pool account from DynamoDB
2. WHEN the Single_Account_Test runs, THE Single_Account_Test SHALL deploy StackSet_07 to the selected account and create a DataZone project forced to use that account
3. WHEN deployment completes, THE Single_Account_Test SHALL verify that shared databases are visible via `SHOW DATABASES` through an Athena connection
4. WHEN deployment completes, THE Single_Account_Test SHALL verify that `SELECT * FROM apf_test_customers.customers LIMIT 5` returns at least one row
5. WHEN verification completes, THE Single_Account_Test SHALL clean up by deleting the project and waiting for the account to return to AVAILABLE state
6. IF the Single_Account_Test fails at any step, THEN THE Single_Account_Test SHALL attempt cleanup before exiting with exit code 1

### Requirement 6: Fleet-Wide Rollout

**User Story:** As a platform engineer, I want a fleet-wide rollout script that deploys StackSet 07 to all pool accounts, so that all existing accounts receive the test data sharing infrastructure.

#### Acceptance Criteria

1. WHEN the Fleet_Rollout_Script runs with `--phase available`, THE Fleet_Rollout_Script SHALL trigger `cleanupStacks` for all AVAILABLE accounts so the reconciler re-provisions them with the new StackSet
2. WHEN the Fleet_Rollout_Script runs with `--phase assigned`, THE Fleet_Rollout_Script SHALL create StackSet_07 instances for all ASSIGNED accounts that do not already have one
3. WHEN deploying to ASSIGNED accounts, THE Fleet_Rollout_Script SHALL skip accounts that already have a StackSet_07 instance
4. WHEN deploying to ASSIGNED accounts, THE Fleet_Rollout_Script SHALL use a maximum concurrency of 5 and failure tolerance of 2
5. IF a StackSet deployment fails for specific accounts, THEN THE Fleet_Rollout_Script SHALL report the failed accounts with status reasons and exit with code 1

### Requirement 7: E2E Test Athena Verification

**User Story:** As a platform engineer, I want the existing e2e lifecycle test to verify Athena access to shared test data, so that the full data sharing pipeline is validated as part of the standard test suite.

#### Acceptance Criteria

1. WHEN the e2e lifecycle test reaches the ASSIGNED state and deployment completes, THE e2e lifecycle test SHALL execute a new Step 5b that verifies Athena connectivity to shared test data
2. WHEN executing Step 5b, THE e2e lifecycle test SHALL confirm that `apf_test_customers` and `apf_test_transactions` databases are visible via `SHOW DATABASES`
3. WHEN executing Step 5b, THE e2e lifecycle test SHALL confirm that querying `apf_test_customers.customers` returns at least one row
4. IF the Athena verification fails, THEN THE e2e lifecycle test SHALL report the failure and continue with cleanup

### Requirement 8: Documentation Update

**User Story:** As a platform engineer, I want the TestingGuide updated with the new test data infrastructure section, so that team members can follow the phased rollout process.

#### Acceptance Criteria

1. WHEN the TestingGuide is updated, THE TestingGuide SHALL include a "Test Data Infrastructure (Glue/Lake Formation)" section after the existing "End-to-End Lifecycle Test" section
2. THE TestingGuide SHALL document prerequisites, Phase 1 (create test data), Phase 2 (single account test), and Phase 3 (fleet-wide rollout) with exact CLI commands
3. THE TestingGuide SHALL document the credential switching requirements between domain account and org admin account for each phase
