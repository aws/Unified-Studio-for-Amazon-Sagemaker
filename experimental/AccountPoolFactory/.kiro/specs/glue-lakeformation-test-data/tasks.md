# Tasks — Glue/Lake Formation Test Data Infrastructure

## Task 1: Create `06-create-test-data.py` (Phase 1 Domain Account Setup)

- [x] 1.1 Create `scripts/02-domain-account/deploy/06-create-test-data.py` with shebang, imports, and configuration constants (REGION, DATABASES, TABLES dicts)
- [x] 1.2 Implement `setup_lf_admin(lf_client, sts_client)` — adds caller's IAM role as LF data lake admin (additive, preserves existing admins)
- [x] 1.3 Implement `create_s3_bucket_and_data(s3_client, bucket_name, region)` — creates S3 bucket and uploads sample CSV files (customers.csv, transactions.csv with 3-5 rows each)
- [x] 1.4 Implement `create_glue_databases(glue_client, databases)` — creates Glue databases, idempotent (skips if exists)
- [x] 1.5 Implement `revoke_iam_allowed_principals(lf_client, databases)` — removes IAM_ALLOWED_PRINCIPALS from all databases, idempotent
- [x] 1.6 Implement `create_glue_tables(glue_client, tables, bucket_name)` — creates Glue tables with correct schema and S3 locations, idempotent
- [x] 1.7 Implement `register_lakeformation(lf_client, bucket_name, account_id)` — registers S3 location with LF and grants domain account permissions
- [x] 1.8 Implement `main()` — orchestrates steps 1-6 in correct order (setup_lf_admin → S3 → databases → revoke IAM_ALLOWED_PRINCIPALS → tables → register LF), make script executable

## Task 2: Create `07-glue-lf-test-data.yaml` StackSet Template

- [x] 2.1 Create `templates/cloudformation/stacksets/idc/07-glue-lf-test-data.yaml` with Parameters (DomainAccountId, DomainId) and Conditions
- [x] 2.2 Add Custom Resource (Lambda-backed) that grants Lake Formation cross-account permissions from domain account to project account (DESCRIBE on databases, SELECT+DESCRIBE on tables)
- [x] 2.3 Add Glue::Database resource link resources for `apf_test_customers` and `apf_test_transactions` pointing to domain account shared databases
- [x] 2.4 Add LakeFormation permission resources granting project account principals read access to the resource links

## Task 3: Update `org-config.yaml` with StackSet 07

- [x] 3.1 Add `07-glue-lf-test-data.yaml` as a wave 2 entry in the `stacksets` list (after `05-project-role.yaml`, before `06-blueprint-enablement.yaml`) with `# TEST ONLY` comment

## Task 4: Create `test-lf-single-account.py` (Phase 2 Single Account Test)

- [x] 4.1 Create `tests/integration/test-lf-single-account.py` with shebang, imports, config loading (same pattern as `test-e2e-pool-lifecycle.py`), and constants
- [x] 4.2 Implement Step 0 (verify credentials) and Step 1 (pick one AVAILABLE pool account from AccountProvider Lambda)
- [x] 4.3 Implement Step 2 (deploy StackSet 07 instance to selected account — check if exists, create if not, poll for completion)
- [x] 4.4 Implement Step 3 (create DataZone project forced to use the selected account) and Step 4 (wait for ASSIGNED state and deployment completion)
- [x] 4.5 Implement Athena verification helpers: `run_athena_query()`, `get_athena_results()`, `verify_athena_connection()` — SHOW DATABASES + SELECT query
- [x] 4.6 Implement Step 5 (verify Athena connection), Step 6 (cleanup — delete project), Step 7 (wait for account to return to AVAILABLE), and final result reporting

## Task 5: Create `test-lf-fleet-rollout.py` (Phase 3 Fleet-Wide Rollout)

- [x] 5.1 Create `tests/integration/test-lf-fleet-rollout.py` with shebang, imports, config loading, argparse (`--phase available|assigned|all`), and constants
- [x] 5.2 Implement `get_accounts_by_state(ddb, state)` — scans DynamoDB with pagination for accounts in a given state
- [x] 5.3 Implement `rollout_available_accounts()` — triggers cleanupStacks via AccountRecycler Lambda for all AVAILABLE accounts
- [x] 5.4 Implement `rollout_assigned_accounts()` — creates StackSet 07 instances for ASSIGNED accounts (skip existing, max concurrency 5, failure tolerance 2, poll for completion, report failures)
- [x] 5.5 Implement `main()` — dispatches to available/assigned/all phases, reports overall result

## Task 6: Update `test-e2e-pool-lifecycle.py` with Step 5b Athena Verification

- [x] 6.1 Add Athena helper functions (`run_athena_query`, `get_athena_results`) to the e2e test file
- [x] 6.2 Add `verify_athena_connection(dz, domain_id, project_id)` function that checks SHOW DATABASES and SELECT query
- [x] 6.3 Insert Step 5b after the existing Step 5 (ASSIGNED state reached) — call `verify_athena_connection`, report pass/fail, continue with cleanup on failure

## Task 7: Update `docs/TestingGuide.md`

- [x] 7.1 Add "Test Data Infrastructure (Glue/Lake Formation)" section after the "End-to-End Lifecycle Test" section with prerequisites, Phase 1/2/3 instructions, credential switching notes, and full end-to-end sequence
