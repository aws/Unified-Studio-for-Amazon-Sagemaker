# DeprovisionAccount Lambda Design

## Overview

The DeprovisionAccount Lambda safely cleans project accounts for reuse by removing all non-approved CloudFormation stacks and resources, then returning the account to the AVAILABLE pool.

## Architecture

### Location
- **Account**: Domain Account (994753223772)
- **Invoked By**: PoolManager Lambda (when project is deleted)
- **Targets**: Project accounts via AccountPoolFactory-DomainAccess role

### Key Responsibilities
1. Identify all CloudFormation stacks in project account
2. Determine which stacks are "approved" (part of base infrastructure)
3. Delete non-approved stacks in reverse dependency order
4. Handle deletion failures gracefully
5. Update DynamoDB state (CLEANING → AVAILABLE or FAILED)
6. Notify on completion or failure

## Approved Stacks (Protected)

These stacks are part of the base account infrastructure and should NOT be deleted:

1. **AccountPoolFactory-StackSetExecutionRole** - StackSet execution role
2. **AccountPoolFactory-DomainAccess** - Cross-account access role (created by StackSet)
3. Any stack created by approved StackSets from Org Management account

### How to Identify Approved Stacks
- Check stack tags for `ManagedBy: AccountPoolFactory`
- Check if stack was created by a StackSet (has `StackSetId` in metadata)
- Maintain allowlist of approved stack name patterns

## Stack Deletion Strategy

### 1. Discovery Phase
```python
# List all stacks in account
stacks = list_all_stacks(account_id)

# Categorize stacks
approved_stacks = []
project_stacks = []

for stack in stacks:
    if is_approved_stack(stack):
        approved_stacks.append(stack)
    else:
        project_stacks.append(stack)
```

### 2. Dependency Analysis
```python
# Build dependency graph from stack outputs/imports
dependency_graph = build_dependency_graph(project_stacks)

# Determine deletion order (reverse topological sort)
deletion_order = reverse_topological_sort(dependency_graph)
```

### 3. Deletion Execution
```python
# Delete stacks in reverse order
for stack in deletion_order:
    try:
        delete_stack_with_retry(stack)
        wait_for_deletion(stack, timeout=600)
    except DeletionFailure as e:
        # Mark account as FAILED
        # Record which stack failed
        # Send notification
        raise
```

## State Machine Flow

```
ASSIGNED (project deleted)
    ↓
CLEANING (deprovision started)
    ↓
    ├─→ AVAILABLE (cleanup successful)
    └─→ FAILED (cleanup failed)
```

## Error Handling

### Recoverable Errors
- **Stack doesn't exist**: Skip, continue
- **Stack already deleting**: Wait for completion
- **Temporary API throttling**: Retry with exponential backoff

### Non-Recoverable Errors
- **Stack deletion failed**: Mark account FAILED, record error
- **Protected resources**: Mark account FAILED, manual intervention required
- **Timeout exceeded**: Mark account FAILED, partial cleanup state

### Failed Account Handling
When cleanup fails:
1. Update DynamoDB: `state=FAILED`, `failedStep=deprovision`, `errorMessage=<details>`
2. Record which stack failed: `failedStack=<stack-name>`
3. Send SNS notification with:
   - Account ID
   - Failed stack name
   - Error message
   - Manual cleanup instructions
4. Block pool replenishment until resolved

## Lambda Implementation

### Function Signature
```python
def lambda_handler(event, context):
    """
    Event format:
    {
        "accountId": "123456789012",
        "requestId": "cleanup-12345",
        "domainId": "dzd-xxx",
        "domainAccountId": "994753223772"
    }
    """
```

### Key Functions

#### 1. Stack Discovery
```python
def list_all_stacks(cf_client) -> List[Dict]:
    """List all stacks (excluding DELETED)"""
    
def is_approved_stack(stack: Dict) -> bool:
    """Check if stack is part of approved infrastructure"""
    
def get_stack_dependencies(cf_client, stack_name: str) -> List[str]:
    """Get stacks that depend on this stack via exports"""
```

#### 2. Dependency Resolution
```python
def build_dependency_graph(stacks: List[Dict]) -> Dict:
    """Build graph of stack dependencies"""
    
def reverse_topological_sort(graph: Dict) -> List[str]:
    """Return deletion order (leaves first, roots last)"""
```

#### 3. Stack Deletion
```python
def delete_stack_safe(cf_client, stack_name: str, max_retries: int = 3):
    """Delete stack with retry logic"""
    
def wait_for_stack_deletion(cf_client, stack_name: str, timeout: int = 600):
    """Wait for stack deletion to complete"""
    
def handle_deletion_failure(stack_name: str, error: Exception):
    """Handle stack deletion failure"""
```

#### 4. State Management
```python
def update_account_state(account_id: str, state: str, **kwargs):
    """Update DynamoDB account record"""
    
def mark_account_available(account_id: str):
    """Mark account as AVAILABLE for reuse"""
    
def mark_account_failed(account_id: str, error_details: Dict):
    """Mark account as FAILED with error details"""
```

## Execution Flow

### Happy Path
```
1. Receive cleanup request from PoolManager
2. Assume AccountPoolFactory-DomainAccess role in project account
3. List all CloudFormation stacks
4. Identify approved vs project stacks
5. Build dependency graph
6. Delete project stacks in reverse order
7. Verify all project stacks deleted
8. Update DynamoDB: state=AVAILABLE
9. Return success
```

### Failure Path
```
1-5. Same as happy path
6. Stack deletion fails (e.g., protected resource)
7. Update DynamoDB: state=FAILED, failedStack=<name>, errorMessage=<error>
8. Send SNS notification
9. Return failure (blocks pool replenishment)
```

## Configuration

### Environment Variables
```yaml
DYNAMODB_TABLE_NAME: AccountPoolFactory-Accounts
SNS_TOPIC_ARN: arn:aws:sns:...
DOMAIN_ID: dzd-xxx
DELETION_TIMEOUT: 600  # seconds per stack
MAX_RETRIES: 3
```

### Approved Stack Patterns
```python
APPROVED_STACK_PATTERNS = [
    'AccountPoolFactory-*',  # All AccountPoolFactory infrastructure
    'StackSet-*',            # StackSet-created stacks
]

APPROVED_STACK_TAGS = {
    'ManagedBy': 'AccountPoolFactory'
}
```

## IAM Permissions

### Lambda Role (in Domain Account)
```yaml
- Effect: Allow
  Action:
    - sts:AssumeRole
  Resource: arn:aws:iam::*:role/AccountPoolFactory-DomainAccess

- Effect: Allow
  Action:
    - dynamodb:UpdateItem
    - dynamodb:GetItem
  Resource: !GetAtt AccountsTable.Arn

- Effect: Allow
  Action:
    - sns:Publish
  Resource: !Ref AlertTopic
```

### AccountPoolFactory-DomainAccess Role (in Project Account)
```yaml
- Effect: Allow
  Action:
    - cloudformation:ListStacks
    - cloudformation:DescribeStacks
    - cloudformation:DescribeStackResources
    - cloudformation:ListStackResources
    - cloudformation:DeleteStack
    - cloudformation:DescribeStackEvents
  Resource: '*'

- Effect: Allow
  Action:
    - cloudformation:ListExports
  Resource: '*'
```

## Monitoring & Alerts

### CloudWatch Metrics
- `DeprovisionStarted`: Count of cleanup operations started
- `DeprovisionSucceeded`: Count of successful cleanups
- `DeprovisionFailed`: Count of failed cleanups
- `StacksDeleted`: Count of stacks deleted per cleanup
- `CleanupDuration`: Time taken for cleanup (seconds)

### SNS Notifications
- **Success**: Account cleaned and returned to pool
- **Failure**: Cleanup failed, manual intervention required
- **Timeout**: Cleanup exceeded timeout threshold

## Testing Strategy

### Unit Tests
1. Stack categorization (approved vs project)
2. Dependency graph building
3. Topological sort for deletion order
4. Error handling for various failure scenarios

### Integration Tests
1. Clean account with simple stack
2. Clean account with dependent stacks
3. Handle stack with protected resources
4. Handle stack deletion timeout
5. Verify state transitions in DynamoDB

### End-to-End Test
1. Create project with DataZone environment
2. Delete project (triggers cleanup)
3. Verify all project stacks deleted
4. Verify approved stacks remain
5. Verify account returns to AVAILABLE state
6. Create new project in same account

## Deployment

### CloudFormation Template
```yaml
DeprovisionAccountFunction:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: DeprovisionAccount
    Runtime: python3.12
    Handler: lambda_function.lambda_handler
    Timeout: 900  # 15 minutes
    MemorySize: 512
    Environment:
      Variables:
        DYNAMODB_TABLE_NAME: !Ref AccountsTable
        SNS_TOPIC_ARN: !Ref AlertTopic
        DOMAIN_ID: !Ref DomainId
```

### Deployment Script
```bash
scripts/02-domain-account/deploy/03-deploy-deprovision-lambda.sh
```

## Future Enhancements

1. **Parallel Stack Deletion**: Delete independent stacks concurrently
2. **Resource Cleanup**: Delete orphaned resources (S3 buckets, etc.)
3. **Cost Optimization**: Identify and remove expensive resources
4. **Cleanup Verification**: Verify account is truly clean before marking AVAILABLE
5. **Partial Cleanup Recovery**: Resume cleanup from last successful step

## Security Considerations

1. **Least Privilege**: Only delete non-approved stacks
2. **Audit Trail**: Log all deletion operations
3. **Rollback Protection**: Never delete approved infrastructure
4. **Timeout Protection**: Prevent infinite cleanup loops
5. **Error Isolation**: Failed cleanup doesn't affect other accounts

## Manual Intervention Procedures

When cleanup fails:

1. **Identify Failed Stack**:
   ```bash
   aws dynamodb get-item --table-name AccountPoolFactory-Accounts \
     --key '{"accountId":{"S":"123456789012"}}'
   ```

2. **Investigate Failure**:
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name <failed-stack> \
     --profile project-account
   ```

3. **Manual Cleanup**:
   ```bash
   # Delete protected resources manually
   # Then retry cleanup
   aws lambda invoke --function-name DeprovisionAccount \
     --payload '{"accountId":"123456789012","requestId":"manual-retry"}'
   ```

4. **Force Available** (last resort):
   ```bash
   aws dynamodb update-item --table-name AccountPoolFactory-Accounts \
     --key '{"accountId":{"S":"123456789012"}}' \
     --update-expression "SET #state = :state" \
     --expression-attribute-names '{"#state":"state"}' \
     --expression-attribute-values '{":state":{"S":"AVAILABLE"}}'
   ```

## Success Criteria

- ✅ All non-approved stacks deleted successfully
- ✅ Approved infrastructure remains intact
- ✅ Account state updated to AVAILABLE
- ✅ No orphaned resources remain
- ✅ Cleanup completes within timeout (15 minutes)
- ✅ Failed cleanups properly marked and reported
