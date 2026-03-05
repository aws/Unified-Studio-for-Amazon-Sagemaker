# ProvisionAccount Lambda - Secure Account Provisioning Design

## Problem Statement

The current architecture has a security vulnerability:
- SetupOrchestrator (Domain account) needs to assume `OrganizationAccountAccessRole` in new accounts
- This role has NO ExternalId protection (trusts entire Org Admin account)
- SetupOrchestrator has wildcard permission: `arn:aws:iam::*:role/OrganizationAccountAccessRole`
- This creates confused deputy vulnerability

## Solution: ProvisionAccount Lambda in Org Admin Account

Create a dedicated Lambda in the Org Admin account that handles:
1. Account creation via Organizations API
2. Deploying StackSet execution role (uses OrganizationAccountAccessRole)
3. Deploying TrustPolicy StackSet (creates AccountPoolFactory-DomainAccess with ExternalId)
4. Returns ready-to-use account ID to Domain account

## Architecture

### Current Flow (Insecure)
```
PoolManager (Domain: 994753223772)
  ├─> Assumes AccountCreation role (Org Admin: 495869084367)
  ├─> Creates account via Organizations API
  ├─> Invokes SetupOrchestrator (Domain: 994753223772)
  │   ├─> Assumes OrganizationAccountAccessRole (new account) ← NO EXTERNALID!
  │   ├─> Deploys StackSet execution role
  │   ├─> Deploys TrustPolicy StackSet
  │   ├─> Assumes AccountPoolFactory-DomainAccess (new account) ← HAS EXTERNALID
  │   └─> Configures account (VPC, IAM, S3, blueprints)
  └─> Updates DynamoDB
```

### Proposed Flow (Secure)
```
PoolManager (Domain: 994753223772)
  ├─> Invokes ProvisionAccount Lambda (Org Admin: 495869084367) ← CROSS-ACCOUNT
  │   ├─> Creates account via Organizations API
  │   ├─> Moves account to target OU
  │   ├─> Assumes OrganizationAccountAccessRole (new account) ← ONLY THIS LAMBDA
  │   ├─> Deploys StackSet execution role via CloudFormation
  │   ├─> Deploys TrustPolicy StackSet (creates AccountPoolFactory-DomainAccess)
  │   ├─> Waits for StackSet completion
  │   └─> Returns account ID
  ├─> Invokes SetupOrchestrator (Domain: 994753223772)
  │   ├─> Assumes AccountPoolFactory-DomainAccess (new account) ← HAS EXTERNALID
  │   └─> Configures account (VPC, IAM, S3, blueprints)
  └─> Updates DynamoDB
```

## Security Benefits

1. **No wildcard permissions**: SetupOrchestrator no longer needs `arn:aws:iam::*:role/OrganizationAccountAccessRole`
2. **Org Admin control**: Only Org Admin account touches OrganizationAccountAccessRole
3. **ExternalId from start**: Domain account only uses AccountPoolFactory-DomainAccess with ExternalId
4. **Clear audit trail**: All org-level operations in one Lambda
5. **Separation of concerns**: Org Admin provisions, Domain configures

## Implementation Details

### 1. ProvisionAccount Lambda (Org Admin Account)

**Location**: `src/provision-account/lambda_function.py`

**Responsibilities**:
- Create account via Organizations API
- Move account to target OU
- Deploy StackSet execution role directly to new account
- Deploy TrustPolicy StackSet to create AccountPoolFactory-DomainAccess role
- Wait for StackSet completion
- Return account ID to caller

**Input**:
```json
{
  "action": "provision",
  "accountName": "DataZone-Pool-001",
  "accountEmail": "pool001@example.com",
  "ouId": "ou-n5om-otvkrtx2",
  "domainId": "dzd-5o0lje5xgpeuw9",
  "domainAccountId": "994753223772",
  "orgAdminAccountId": "495869084367"
}
```

**Output**:
```json
{
  "status": "SUCCESS",
  "accountId": "123456789012",
  "message": "Account provisioned and ready for configuration"
}
```

**IAM Role**: `AccountPoolFactory-ProvisionAccount-Role`

**Permissions**:
```yaml
- organizations:CreateAccount
- organizations:DescribeAccount
- organizations:DescribeCreateAccountStatus
- organizations:MoveAccount
- organizations:ListParents
- sts:AssumeRole on OrganizationAccountAccessRole (any account)
- cloudformation:CreateStack
- cloudformation:DescribeStacks
- cloudformation:CreateStackInstances
- cloudformation:DescribeStackSetOperation
- cloudformation:ListStackInstances
```

**Resource Policy** (allows Domain account to invoke):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::994753223772:role/AccountPoolFactory-PoolManager-Role"
    },
    "Action": "lambda:InvokeFunction",
    "Condition": {
      "StringEquals": {
        "lambda:FunctionArn": "arn:aws:lambda:us-east-2:495869084367:function:ProvisionAccount"
      }
    }
  }]
}
```

### 2. PoolManager Changes (Domain Account)

**Remove**:
- Organizations API calls (CreateAccount, DescribeCreateAccountStatus, MoveAccount)
- Permission to assume AccountCreation role in Org Admin

**Add**:
- Cross-account Lambda invoke to ProvisionAccount
- Permission: `lambda:InvokeFunction` on ProvisionAccount Lambda ARN

**New Flow**:
```python
# Instead of creating account directly
response = lambda_client.invoke(
    FunctionName='arn:aws:lambda:us-east-2:495869084367:function:ProvisionAccount',
    InvocationType='RequestResponse',
    Payload=json.dumps({
        'action': 'provision',
        'accountName': account_name,
        'accountEmail': account_email,
        'ouId': target_ou_id,
        'domainId': domain_id,
        'domainAccountId': domain_account_id,
        'orgAdminAccountId': org_admin_account_id
    })
)

result = json.loads(response['Payload'].read())
if result['status'] == 'SUCCESS':
    account_id = result['accountId']
    # Continue with SetupOrchestrator invocation
```

### 3. SetupOrchestrator Changes (Domain Account)

**Remove**:
- Wave 0: StackSet deployment (now done by ProvisionAccount)
- Permission to assume OrganizationAccountAccessRole
- Permission to assume StackSetManagement role in Org Admin
- `deploy_stackset_instance()` function

**Simplify**:
- Start directly at Wave 1 (VPC deployment)
- Assume AccountPoolFactory-DomainAccess exists from the start

**New Flow**:
```python
def execute_setup_workflow(account_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    # Wave 1: VPC Deployment (foundation)
    vpc_result = deploy_vpc(account_id, config)
    
    # Wave 2: IAM Roles + EventBridge Rules (parallel)
    iam_result, eb_result = execute_wave_parallel([...])
    
    # ... rest of waves unchanged
```

## Deployment Sequence

### Phase 1: Deploy ProvisionAccount Lambda (Org Admin)

1. Create Lambda source code: `src/provision-account/lambda_function.py`
2. Create CloudFormation template: `templates/cloudformation/01-org-mgmt-account/deploy/05-provision-account-lambda.yaml`
3. Create deployment script: `scripts/01-org-mgmt-account/deploy/05-deploy-provision-account.sh`
4. Deploy to Org Admin account (495869084367)

### Phase 2: Update Domain Account Infrastructure

1. Update `templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml`:
   - Remove `sts:AssumeRole` on OrganizationAccountAccessRole from SetupOrchestrator
   - Remove `sts:AssumeRole` on StackSetManagement role from SetupOrchestrator
   - Add `lambda:InvokeFunction` permission to PoolManager for ProvisionAccount
   - Remove Organizations permissions from PoolManager
   - Remove AccountCreation role assumption from PoolManager

2. Update PoolManager Lambda code: `src/pool-manager/lambda_function.py`
   - Replace Organizations API calls with Lambda invoke
   - Update error handling

3. Update SetupOrchestrator Lambda code: `src/setup-orchestrator/lambda_function.py`
   - Remove Wave 0 (StackSet deployment)
   - Remove `deploy_stackset_instance()` function
   - Start at Wave 1

4. Redeploy infrastructure stack
5. Redeploy Lambda functions

## Testing Plan

1. **Unit test ProvisionAccount Lambda**:
   - Test account creation
   - Test StackSet execution role deployment
   - Test TrustPolicy StackSet deployment
   - Test error handling

2. **Integration test**:
   - Clear DynamoDB table
   - Trigger pool replenishment
   - Verify PoolManager invokes ProvisionAccount
   - Verify account is created with proper roles
   - Verify SetupOrchestrator can assume AccountPoolFactory-DomainAccess
   - Verify full account configuration completes

3. **Security validation**:
   - Verify SetupOrchestrator cannot assume OrganizationAccountAccessRole
   - Verify only ProvisionAccount can assume OrganizationAccountAccessRole
   - Verify ExternalId is required for AccountPoolFactory-DomainAccess

## Rollback Plan

If issues arise:
1. Keep old Lambda code in `src/pool-manager/lambda_function.py.backup`
2. Keep old infrastructure template in `templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml.backup`
3. Redeploy old versions if needed
4. Delete ProvisionAccount Lambda from Org Admin

## Timeline

- **Phase 1** (Org Admin): 30 minutes
  - Create ProvisionAccount Lambda code
  - Create CloudFormation template
  - Deploy to Org Admin account

- **Phase 2** (Domain Account): 45 minutes
  - Update infrastructure template
  - Update PoolManager code
  - Update SetupOrchestrator code
  - Redeploy

- **Testing**: 30 minutes
  - Clear DynamoDB
  - Trigger replenishment
  - Verify end-to-end flow

**Total**: ~2 hours

## Success Criteria

- ✅ ProvisionAccount Lambda deployed in Org Admin account
- ✅ PoolManager successfully invokes ProvisionAccount cross-account
- ✅ New accounts created with AccountPoolFactory-DomainAccess role (ExternalId protected)
- ✅ SetupOrchestrator successfully configures accounts using AccountPoolFactory-DomainAccess
- ✅ No permissions for SetupOrchestrator to assume OrganizationAccountAccessRole
- ✅ Full account creation and configuration completes successfully
- ✅ Pool replenishment works end-to-end

## Open Questions

1. Should ProvisionAccount Lambda also handle account deletion/cleanup?
2. Should we add retry logic in ProvisionAccount for StackSet failures?
3. Should we add CloudWatch alarms for ProvisionAccount failures?

## References

- AWS Organizations API: https://docs.aws.amazon.com/organizations/latest/APIReference/
- Cross-account Lambda invocation: https://docs.aws.amazon.com/lambda/latest/dg/access-control-resource-based.html
- Confused Deputy Problem: https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html
- StackSets: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/what-is-cfnstacksets.html
