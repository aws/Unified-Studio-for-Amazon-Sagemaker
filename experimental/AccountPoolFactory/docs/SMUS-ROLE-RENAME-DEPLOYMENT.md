# SMUS Role Rename - Deployment Progress

## Overview
Renaming all AccountPoolFactory IAM roles to use SMUS- prefix. All local files (templates, scripts, Lambda code, docs) already updated. This tracks the AWS stack redeployments.

## Role Rename Mapping
| Old Name | New Name |
|---|---|
| `AWSCloudFormationStackSetAdministrationRole` | `SMUS-AccountPoolFactory-StackSetAdmin` |
| `AWSCloudFormationStackSetExecutionRole` | `SMUS-AccountPoolFactory-StackSetExecution` |
| `AccountPoolFactory-ProvisionAccount-Role` | `SMUS-AccountPoolFactory-ProvisionAccount-Role` |
| `AccountPoolFactory-DomainAccess` | `SMUS-AccountPoolFactory-DomainAccess` |
| `AccountPoolFactory-PoolManager-Role` | `SMUS-AccountPoolFactory-PoolManager-Role` |
| `AccountPoolFactory-SetupOrchestrator-Role` | `SMUS-AccountPoolFactory-SetupOrchestrator-Role` |
| `AccountPoolFactory-AccountCreation` | `SMUS-AccountPoolFactory-AccountCreation` |
| `AccountPoolFactory-StackSetManagement` | **DELETED** (unused) |
| `AccountPoolFactory-AccountCreation` (old stack) | **DELETED** (unused) |

## Deployment Order (safe sequence to avoid breaking trust chains)

### Step 1: Domain Account — Infrastructure (amirbo+3)
- **Script**: `./scripts/02-domain-account/deploy/01-deploy-infrastructure.sh`
- **Stack**: `AccountPoolFactory-Infrastructure`
- **Roles renamed**: PoolManager-Role, SetupOrchestrator-Role
- **Status**: ✅ DONE
- **Script**: `./scripts/01-org-mgmt-account/deploy/01-deploy-stackset-roles.sh`
- **Stack**: `AccountPoolFactory-StackSetRoles`
- **Roles renamed**: StackSetAdmin (was AWSCloudFormationStackSetAdministrationRole)
- **Status**: ✅ DONE

### Step 3: Org Admin — ProvisionAccount Lambda (amirbo+1)
- **Script**: `./scripts/01-org-mgmt-account/deploy/05-deploy-provision-account.sh`
- **Stack**: `AccountPoolFactory-ProvisionAccount`
- **Roles renamed**: ProvisionAccount-Role
- **Note**: Had to delete and recreate stack — old `SourceArn` on Lambda Permission was invalid (IAM role ARN not valid for cross-account invoke). Removed `SourceArn`, account-level principal is sufficient.
- **Status**: ✅ DONE

### Step 4: Org Admin — AccountCreation Role (amirbo+1)
- **Script**: `./scripts/01-org-mgmt-account/deploy/02-deploy-account-creation-role.sh`
- **Stack**: `AccountPoolFactory-AccountCreationRole`
- **Roles renamed**: AccountCreation
- **Status**: ✅ DONE

### Step 5: Org Admin — DomainAccess StackSet (amirbo+1)
- **Script**: `./scripts/01-org-mgmt-account/deploy/04-deploy-domain-access-stackset.sh`
- **StackSet**: `SMUS-AccountPoolFactory-DomainAccess`
- **Roles renamed**: DomainAccess in project accounts (new accounts going forward)
- **Status**: ✅ DONE

### Step 6: Org Admin — StackSetExecution Role via StackSet (amirbo+1)
- **Mechanism**: New accounts get SMUS-AccountPoolFactory-StackSetExecution via ProvisionAccount Lambda
- **Note**: Existing accounts retain old role; only new accounts get SMUS-prefixed role
- **Status**: ✅ DONE (handled by ProvisionAccount Lambda for new accounts)

### Step 7: Update SSM Parameter for AccountCreation Role ARN (amirbo+3)
- **Parameter**: `/AccountPoolFactory/PoolManager/OrgAdminRoleArn`
- **Old value**: `arn:aws:iam::495869084367:role/AccountPoolFactory-AccountCreation`
- **New value**: `arn:aws:iam::495869084367:role/SMUS-AccountPoolFactory-AccountCreation`
- **Status**: ✅ DONE

### Step 8: Delete old unused stacks (amirbo+1)
- **Note**: Old `AccountPoolFactory-AccountCreationRole` stack was updated in-place (Step 4), not a separate stack
- **Status**: ✅ N/A

### Step 9: Deploy updated Lambda code (amirbo+3)
- **Script**: `./scripts/02-domain-account/deploy/02-deploy-lambdas.sh`
- **Lambdas**: PoolManager, SetupOrchestrator, DeprovisionAccount
- **Status**: ✅ DONE

### Step 10: End-to-end verification
- **Status**: ✅ DONE
- **Verified roles in Domain Account (994753223772)**:
  - `SMUS-AccountPoolFactory-PoolManager-Role` ✅
  - `SMUS-AccountPoolFactory-SetupOrchestrator-Role` ✅
  - PoolManager Lambda using correct role ✅
  - SetupOrchestrator Lambda using correct role ✅
  - DeprovisionAccount Lambda using correct role ✅
- **Verified roles in Org Admin Account (495869084367)**:
  - `SMUS-AccountPoolFactory-StackSetAdmin` ✅
  - `SMUS-AccountPoolFactory-ProvisionAccount-Role` ✅
  - `SMUS-AccountPoolFactory-AccountCreation` ✅
  - ProvisionAccount Lambda using correct role ✅
- **Verified StackSets**:
  - `SMUS-AccountPoolFactory-DomainAccess` StackSet ACTIVE ✅
- **SSM Parameter** `/AccountPoolFactory/PoolManager/OrgAdminRoleArn` updated ✅
