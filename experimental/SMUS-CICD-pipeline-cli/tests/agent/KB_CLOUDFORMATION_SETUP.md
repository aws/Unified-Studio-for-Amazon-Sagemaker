# Knowledge Base CloudFormation Setup - COMPLETE ✅

## Summary
Successfully implemented CloudFormation-based KB setup for SMUS CLI Agent.

## Architecture

### Manual One-Time Setup
- **S3 Bucket**: `smus-cli-kb-docs-{account-id}` (created once manually)
  - Long-term: Will be a public bucket for all customers
  - Current: Private bucket, hardcoded ARN pattern in code

### CloudFormation Stack (5 resources)
1. **IAM Role**: `SMUSCLIKnowledgeBaseRole`
   - Trust policy for bedrock.amazonaws.com
   - S3 access to hardcoded bucket ARN
   - OpenSearch Serverless access
   - AmazonBedrockFullAccess managed policy

2. **Encryption Policy**: `smus-cli-kb-encryption`
   - AWS-owned key for collection

3. **Network Policy**: `smus-cli-kb-network`
   - Public access to collection

4. **Data Access Policy**: `smus-cli-kb-access`
   - Principals: KB role + user role (parameterized)
   - Permissions: Collection and index CRUD

5. **OpenSearch Collection**: `smus-cli-kb`
   - Type: VECTORSEARCH
   - Waits for ACTIVE status

### CLI-Created Resources (4 resources)
6. **OpenSearch Index**: `bedrock-knowledge-base-default-index`
   - Engine: FAISS (required by Bedrock)
   - Dimension: 1024 (Titan v2)
   - Created via OpenSearch Python client

7. **Bedrock Knowledge Base**: `SMUS-CLI-KB`
   - Embedding model: Titan Text Embeddings V2 (1024 dimensions)
   - Storage: OpenSearch Serverless

8. **Data Source**: `SMUS-CLI-Docs`
   - Type: S3
   - Bucket: Hardcoded pattern

9. **Ingestion Job**: Started after KB is ACTIVE

## Test Results
```
test_kb_full_setup_with_cloudformation PASSED in 267.86s (0:04:27)
```

### Test Flow
1. ✅ Deploy CloudFormation stack (5 resources)
2. ✅ Wait 2 minutes for policies to propagate
3. ✅ Create OpenSearch index with FAISS/1024 dimensions
4. ✅ Create Bedrock KB with Titan v2
5. ✅ Create data source pointing to S3 bucket
6. ✅ Wait for KB to be ACTIVE
7. ✅ Start ingestion job
8. ✅ Cleanup: Delete KB and stack

## Key Learnings

### S3 Bucket
- **Issue**: CloudFormation bucket creation caused conflicts during rapid create/delete cycles
- **Solution**: Create bucket once manually, hardcode ARN pattern in code
- **Future**: Will be a public bucket shared by all customers

### OpenSearch Index
- **Engine**: Must use FAISS (not nmslib) for Bedrock compatibility
- **Dimensions**: Must match embedding model (1024 for Titan v2, 1536 for Titan v1)
- **Manual creation**: Required before KB creation via OpenSearch API

### Embedding Model
- **Available**: Only Titan v2 in us-east-2
- **ARN**: `arn:aws:bedrock:us-east-2::foundation-model/amazon.titan-embed-text-v2:0`
- **Dimensions**: 1024

### Timing
- **Policy propagation**: 2 minutes wait after collection creation
- **KB activation**: Wait for ACTIVE status before starting ingestion
- **Index creation**: 30 seconds wait after creation

## Files Created
- `src/smus_cicd/agent/kb_stack.yaml` - CloudFormation template
- `src/smus_cicd/agent/kb_setup.py` - Setup functions
- `tests/agent/test_kb_cloudformation_setup.py` - Integration test

## Next Steps
1. Add CLI commands: `smus-cli kb setup`, `smus-cli kb sync`, `smus-cli kb delete`
2. Save KB ID and Data Source ID to config after setup
3. Add documentation for users
4. Test idempotency (update test)
