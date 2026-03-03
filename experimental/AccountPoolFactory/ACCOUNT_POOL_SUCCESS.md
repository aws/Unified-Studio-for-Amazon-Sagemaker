# Account Pool Integration - SUCCESS! 🎉

## Test Date
March 3, 2026

## Summary
Successfully validated the complete DataZone Account Pool integration with custom Lambda handler.

## What Works ✅

### 1. ListAccountsInAccountPool API
- Lambda is invoked correctly by DataZone
- Returns list of authorized accounts with regions
- Event structure: `listAuthorizedAccountsRequest` with domain details

### 2. Create Project with Account Pool
- Correct API: `aws datazone create-project` with `--user-parameters`
- Parameter structure:
  ```json
  {
    "environmentConfigurationName": "Tooling",
    "environmentResolvedAccount": {
      "awsAccountId": "004878717744",
      "regionName": "us-east-2",
      "sourceAccountPoolId": "d47walsa85zkx5"
    }
  }
  ```
- Must provide resolved accounts for ALL environments that have account pools configured
- ON_CREATE environments will be created immediately
- ON_DEMAND environments will be created later when requested

### 3. ValidateAccountAuthorizationRequest
- Lambda is invoked during project creation
- Event structure: `validateAccountAuthorizationRequest` with:
  - `awsAccountId`: Account to validate
  - `regionName`: Region to validate (NOT `awsRegion`!)
  - `domainIdentifier`: Domain ID
  - `userIdentifier`: User creating the project
- Lambda returns `authResult`: "GRANT" or "DENY"

### 4. Deployment Flow
- Project status: ACTIVE
- Deployment status progression:
  1. PENDING_DEPLOYMENT
  2. IN_PROGRESS (validation passed!)
  3. FAILED_DEPLOYMENT (expected - CF3 not deployed yet)

## Key Findings 🔍

### Lambda Event Structure
```python
# listAuthorizedAccountsRequest
{
  "operationRequest": {
    "listAuthorizedAccountsRequest": {
      "domainIdentifier": "dzd-4igt64u5j25ko9",
      "domainUnitIdentifier": "6kg8zlq8mvid9l",
      "domainRegion": "us-east-2",
      "domainPartition": "aws",
      "userIdentifier": "4b89ed84-9842-45dd-a2e5-15e49eda2b03",
      "maxResults": 100,
      "nextToken": null
    },
    "validateAccountAuthorizationRequest": null
  }
}

# validateAccountAuthorizationRequest
{
  "operationRequest": {
    "listAuthorizedAccountsRequest": null,
    "validateAccountAuthorizationRequest": {
      "domainIdentifier": "dzd-4igt64u5j25ko9",
      "awsAccountId": "004878717744",
      "regionName": "us-east-2",  # NOT awsRegion!
      "userIdentifier": "4b89ed84-9842-45dd-a2e5-15e49eda2b03"
    }
  }
}
```

### Critical Bug Fix
- **WRONG**: `region = request.get('awsRegion')`
- **CORRECT**: `region = request.get('regionName')`

### AccountResolutionRole Trust Policy
- DataZone does NOT pass `aws:SourceAccount` or `aws:SourceArn` context keys
- Trust policy CANNOT have these conditions
- This is a DataZone API bug/limitation

### Profile Configuration
- When account pools are configured on a profile, ALL environments must have resolved accounts
- This applies to both ON_CREATE and ON_DEMAND environments
- Validation fails if any environment is missing a resolved account

## Current Deployment Failure (Expected) ⚠️

### Error
```
"Tooling": [
  {
    "code": "403",
    "message": "Caller is not authorized to create environment using blueprintId 3owsbi7jjppvc9"
  }
]
```

### Root Cause
Project account (004878717744) doesn't have:
1. CF3 IAM roles deployed
2. Blueprint enablement configured
3. VPC setup (if required)

### Next Steps
This is exactly what the Setup Orchestrator Lambda should handle:
1. Create RAM share for domain
2. Verify domain visibility in project account
3. Deploy CF3 StackSet (IAM roles, VPC, etc.)
4. Enable blueprints in project account
5. Create policy grants in domain account
6. Mark account as available in pool

## Test Results 📊

### Project Created
- Project ID: dc8wy15jbbh8yx
- Project Name: test-pool-project-1772547342-9461
- Account: 004878717744 (TestAccount-100)
- Region: us-east-2
- Profile: 3q3bu487vip8a1 (All capabilities - Account Pool v2)

### Lambda Invocations
- ListAccountsInAccountPool: ✅ Multiple successful calls
- ValidateAccountAuthorizationRequest: ✅ Called during project creation
- Authorization Result: ✅ GRANT

### Deployment Status
- Validation: ✅ PASSED
- Authorization: ✅ GRANTED
- Deployment: ❌ FAILED (expected - account not set up)

## Conclusion 🎯

The DataZone Account Pool integration is **WORKING CORRECTLY**! 

The Lambda handler successfully:
- Lists authorized accounts
- Validates account/region pairs
- Returns proper authorization results

The deployment failure is expected and correct - it's failing because we haven't set up the project account yet. This validates that our orchestration workflow design is correct:

1. ✅ User calls ListAccountsInAccountPool
2. ✅ User picks account and creates project
3. ✅ DataZone validates account via Lambda
4. ✅ DataZone attempts to deploy environment
5. ⏭️ Setup Orchestrator should prepare the account (not implemented yet)

## Files
- Test script: `tests/setup/scripts/test-project-with-account-v2.sh`
- Lambda code: `src/account-provider/lambda_function.py`
- CloudFormation: `templates/cloudformation/02-domain-account/account-provider-lambda.yaml`
