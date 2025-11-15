# IAM Role Management Feature

## Overview
Added support for automatic IAM role creation and policy attachment during project initialization.

## Changes Made

### 1. New IAM Helper Module
**File**: `src/smus_cicd/helpers/iam.py`

Functions:
- `create_or_update_project_role()`: Creates new role or attaches policies to existing role
- `_load_trust_policy()`: Loads trust policy template with account ID substitution
- `_attach_policies()`: Attaches policies to role (skips already attached)

### 2. Trust Policy Template
**File**: `src/smus_cicd/resources/project_role_trust_policy.json`

Trust policy for project roles with services:
- athena.amazonaws.com
- emr-serverless.amazonaws.com
- glue.amazonaws.com
- airflow-serverless.amazonaws.com
- redshift.amazonaws.com
- bedrock.amazonaws.com
- datazone.amazonaws.com
- lakeformation.amazonaws.com
- sagemaker.amazonaws.com
- scheduler.amazonaws.com

Account ID is dynamically replaced from domain account.

### 3. Project Manager Updates
**File**: `src/smus_cicd/helpers/project_manager.py`

Added methods:
- `_get_policy_arns()`: Extracts policy ARNs from target configuration
- Updated `ensure_project_exists()`: Integrates role creation/policy attachment

### 4. Documentation
**File**: `docs/manifest-schema.md`

Updated initialization.project.role section with:
- `arn`: Optional existing role ARN
- `policies`: List of policy ARNs (AWS managed or customer managed)

## Usage

### Common Scenario 1: Create New Role with Policies (Default Name)
```yaml
targets:
  dev:
    initialization:
      project:
        create: true
        role:
          policies:
            - arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
            - arn:aws:iam::aws:policy/AmazonAthenaFullAccess
            - arn:aws:iam::123456789012:policy/MyCustomPolicy
```
Creates role: `smus-{project-name}-role`

### Common Scenario 2: Create New Role with Custom Name
```yaml
targets:
  dev:
    initialization:
      project:
        create: true
        role:
          name: my-analytics-role
          policies:
            - arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
```
Creates role: `my-analytics-role`

### Common Scenario 3: Use Existing Role
```yaml
targets:
  prod:
    initialization:
      project:
        create: true
        role:
          arn: arn:aws:iam::123456789012:role/existing-role
```
Uses existing role as-is.

### Advanced: Attach Policies to Existing Role
```yaml
targets:
  prod:
    initialization:
      project:
        create: true
        role:
          arn: arn:aws:iam::123456789012:role/existing-role
          policies:
            - arn:aws:iam::aws:policy/AmazonS3FullAccess
```
Attaches additional policies to existing role (infrequent use case).

## Behavior

1. **Role Creation**: Only happens during project creation (when `initialization.project.create: true`)
2. **Policy Attachment**: Supports both AWS managed and customer managed policies
3. **Idempotency**: Skips already attached policies
4. **Error Handling**: Raises exceptions on policy attachment failures

## Testing

Run unit tests:
```bash
python tests/run_tests.py --type unit
```

Run integration tests:
```bash
python tests/run_tests.py --type integration
```
