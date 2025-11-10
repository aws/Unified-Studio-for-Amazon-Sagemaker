# KB Setup Cleanup Fixes

## Issues Found

### 1. Orphaned OpenSearch Collection
**Problem**: When CloudFormation stack creation fails, the collection may be partially created but not tracked by the stack. On retry, CloudFormation tries to create it again and fails with "AlreadyExists".

**Error**:
```
Collection: Resource of type 'AWS::OpenSearchServerless::Collection' 
with identifier 'smus-cli-kb' already exists.
```

**Fix**: Added collection cleanup to `delete_kb_stack()`:
```python
# Clean up orphaned OpenSearch collection
response = aoss.batch_get_collection(names=['smus-cli-kb'])
if response['collectionDetails']:
    collection_id = response['collectionDetails'][0]['id']
    aoss.delete_collection(id=collection_id)
```

### 2. Empty Failure Details
**Problem**: Error display showed "Failure details:" but no actual details.

**Fix**: Fixed the loop to actually show failed resources:
```python
shown = 0
for event in events['StackEvents']:
    if 'FAILED' in event['ResourceStatus'] and shown < 5:
        reason = event.get('ResourceStatusReason', 'Unknown')
        print(f"  • {event['LogicalResourceId']}: {reason}")
        shown += 1
```

### 3. Incomplete Cleanup
**Problem**: `delete_kb_stack()` only cleaned up the stack, leaving orphaned resources.

**Fix**: Now cleans up in order:
1. Bedrock Knowledge Base (if exists)
2. CloudFormation Stack
3. OpenSearch Collection (if orphaned)
4. Data Access Policy (if orphaned)
5. Network Policy (if orphaned)
6. Encryption Policy (if orphaned)

## Complete Cleanup Order

```
delete_kb_stack(region)
    ↓
1. Delete Bedrock KB (SMUS-CLI-KB)
    ↓
2. Delete CloudFormation Stack (smus-cli-kb-stack)
    ↓
3. Delete Orphaned Collection (smus-cli-kb)
    ↓
4. Delete Orphaned Policies:
   - smus-cli-kb-access (data)
   - smus-cli-kb-network (network)
   - smus-cli-kb-encryption (encryption)
```

## Usage

### Clean Up Everything
```bash
smus-cli kb delete
```

Or programmatically:
```python
from smus_cicd.agent.kb_setup import delete_kb_stack
delete_kb_stack(region='us-east-1')
```

### After Cleanup
Stack creation should now succeed without "AlreadyExists" errors.

## Test Results

✅ Cleanup now removes all orphaned resources
✅ Fresh setup works after cleanup
✅ Error messages show actual failure reasons
