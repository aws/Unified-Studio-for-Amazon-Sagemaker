# Knowledge Base Setup - User Approval & Waiting

## User Approval Flow

When running `smus-cli kb setup`, users will see:

```
======================================================================
🚀 Knowledge Base Setup - CREATE Stack
======================================================================

Region: us-east-2
Account: 198737698272
User Role: arn:aws:iam::198737698272:role/Admin

Resources to create:
  1. IAM Role: SMUSCLIKnowledgeBaseRole
  2. OpenSearch Encryption Policy: smus-cli-kb-encryption
  3. OpenSearch Network Policy: smus-cli-kb-network
  4. OpenSearch Data Access Policy: smus-cli-kb-access
  5. OpenSearch Collection: smus-cli-kb (VECTORSEARCH)

Additional resources (created after stack):
  6. OpenSearch Index: bedrock-knowledge-base-default-index
  7. Bedrock Knowledge Base: SMUS-CLI-KB
  8. Data Source: SMUS-CLI-Docs
  9. Ingestion Job: (started)

Estimated time: ~5-6 minutes
======================================================================

Proceed? (yes/no): 
```

### User Options
- **yes** or **y**: Proceed with setup
- **no** or anything else: Cancel setup

## Proper Waiting

### CloudFormation Stack
- Uses CloudFormation waiters with progress updates
- Polls every 15 seconds
- Shows elapsed time: "Still working... (45s elapsed)"
- Waits for `CREATE_COMPLETE` or `UPDATE_COMPLETE`
- Typical time: 3-5 minutes

### OpenSearch Index
- Waits 30 seconds after creation for index to be ready
- Required for Bedrock to validate index exists

### Knowledge Base
- Polls KB status every 10 seconds (max 5 minutes)
- Waits for status = `ACTIVE`
- Required before starting ingestion job

### Policy Propagation
- Waits 2 minutes after collection creation
- Allows OpenSearch policies to propagate
- Prevents permission errors

## Idempotency

### Stack Already Exists
```
📝 Updating existing stack...
✅ Stack already up to date
```

### Resources Already Exist
- KB: "✅ Knowledge Base already exists: {kb_id}"
- Data Source: "✅ Data source already exists: {ds_id}"
- Index: "✅ Index already exists: {index_name}"

## Auto-Approve Mode

For automated/testing scenarios:

```python
outputs = deploy_kb_stack(region='us-east-2', auto_approve=True)
```

Skips user approval prompt, proceeds directly to deployment.

## Test Results

### Full Setup Test
```
✅ test_kb_full_setup_with_cloudformation PASSED
   - Deploys stack with auto_approve=True
   - Creates all resources
   - Starts ingestion
   - Cleans up
```

### Idempotency Test
```
✅ test_kb_stack_idempotency PASSED
   - Deploys stack twice
   - Verifies same outputs
   - No errors on second run
```

## Demo Script

Run `python tests/agent/demo_kb_setup.py` to see the approval flow interactively.
