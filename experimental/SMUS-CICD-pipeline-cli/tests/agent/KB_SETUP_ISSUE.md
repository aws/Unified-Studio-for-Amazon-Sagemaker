# Knowledge Base Setup Issue - Detailed Analysis

## Error
```
ValidationException: The knowledge base storage configuration provided is invalid... 
Dependency error document status code: 404, error message: no such index [bedrock-knowledge-base-default-index]
```

## What We're Creating (Step by Step)

### 1. S3 Bucket ✅
- **Name**: `smus-cli-kb-{account-id}`
- **Purpose**: Store documentation files that will be indexed
- **Status**: Creates successfully

### 2. IAM Role ✅
- **Name**: `SMUSCLIKnowledgeBaseRole`
- **Trust Policy**: Allows `bedrock.amazonaws.com` to assume the role
- **Permissions**:
  - S3 read access to KB bucket
  - OpenSearch Serverless `aoss:APIAccessAll` permission
  - `AmazonBedrockFullAccess` managed policy
- **Status**: Creates successfully

### 3. OpenSearch Serverless Security Policies ✅
Three policies required before creating collection:

#### a. Encryption Policy
```json
{
  "Rules": [{
    "ResourceType": "collection",
    "Resource": ["collection/smus-cli-kb"]
  }],
  "AWSOwnedKey": true
}
```
- **Name**: `smus-cli-kb-encryption`
- **Type**: `encryption`
- **Status**: Creates successfully

#### b. Network Policy
```json
[{
  "Rules": [{
    "ResourceType": "collection",
    "Resource": ["collection/smus-cli-kb"]
  }],
  "AllowFromPublic": true
}]
```
- **Name**: `smus-cli-kb-network`
- **Type**: `network`
- **Status**: Creates successfully

#### c. Data Access Policy
```json
[{
  "Rules": [
    {
      "ResourceType": "collection",
      "Resource": ["collection/smus-cli-kb"],
      "Permission": [
        "aoss:CreateCollectionItems",
        "aoss:UpdateCollectionItems",
        "aoss:DescribeCollectionItems"
      ]
    },
    {
      "ResourceType": "index",
      "Resource": ["index/smus-cli-kb/*"],
      "Permission": [
        "aoss:CreateIndex",
        "aoss:UpdateIndex",
        "aoss:DescribeIndex",
        "aoss:ReadDocument",
        "aoss:WriteDocument"
      ]
    }
  ],
  "Principal": [
    "arn:aws:iam::{account}:role/SMUSCLIKnowledgeBaseRole",
    "arn:aws:iam::{account}:role/Admin"  // Current user's role
  ]
}]
```
- **Name**: `smus-cli-kb-access`
- **Type**: `data`
- **Status**: Creates successfully
- **Note**: Includes both KB role and current user role as principals

### 4. OpenSearch Serverless Collection ✅
- **Name**: `smus-cli-kb`
- **Type**: `VECTORSEARCH`
- **Status**: Creates successfully, becomes ACTIVE after ~20-30 seconds
- **ARN**: `arn:aws:aoss:us-east-2:{account}:collection/{collection-id}`

### 5. Wait for Policy Propagation ✅
- **Duration**: 120 seconds (2 minutes)
- **Purpose**: Allow data access policies to fully propagate
- **Status**: Completes successfully

### 6. Bedrock Knowledge Base ❌ FAILS HERE
```python
bedrock_agent.create_knowledge_base(
    name='SMUS-CLI-KB',
    roleArn='arn:aws:iam::{account}:role/SMUSCLIKnowledgeBaseRole',
    knowledgeBaseConfiguration={
        'type': 'VECTOR',
        'vectorKnowledgeBaseConfiguration': {
            'embeddingModelArn': 'arn:aws:bedrock:us-east-2::foundation-model/amazon.titan-embed-text-v1'
        }
    },
    storageConfiguration={
        'type': 'OPENSEARCH_SERVERLESS',
        'opensearchServerlessConfiguration': {
            'collectionArn': 'arn:aws:aoss:us-east-2:{account}:collection/{id}',
            'vectorIndexName': 'bedrock-knowledge-base-default-index',
            'fieldMapping': {
                'vectorField': 'bedrock-knowledge-base-default-vector',
                'textField': 'AMAZON_BEDROCK_TEXT_CHUNK',
                'metadataField': 'AMAZON_BEDROCK_METADATA'
            }
        }
    }
)
```

**Error**: Bedrock tries to validate that the index `bedrock-knowledge-base-default-index` exists in the collection, but it doesn't exist yet.

## The Problem

According to AWS documentation, when you create a Knowledge Base with OpenSearch Serverless:
1. You create the collection first
2. You create the Knowledge Base pointing to the collection
3. **Bedrock should automatically create the index** when you create a data source and sync it

However, our error shows that Bedrock is trying to **validate the index exists** during KB creation (step 2), before we even create the data source (step 3).

## Questions for You

1. **Does the index need to be created manually first?**
   - If yes, how do we create it via OpenSearch API?
   - What should the index mapping look like?

2. **Are we using the wrong index name or field mappings?**
   - We're using AWS documented defaults: `bedrock-knowledge-base-default-index`
   - Field names: `bedrock-knowledge-base-default-vector`, `AMAZON_BEDROCK_TEXT_CHUNK`, `AMAZON_BEDROCK_METADATA`

3. **Is there a different KB creation flow for OpenSearch Serverless?**
   - Should we create the data source first somehow?
   - Is there a parameter to skip index validation?

4. **Do we need additional permissions?**
   - The KB role has `aoss:APIAccessAll`
   - The data access policy includes index creation permissions
   - Is something else needed?

## Test File
Run the isolated test:
```bash
cd /Users/amirbo/code/smus/experimental/SMUS-CICD-pipeline-cli
python -m pytest tests/agent/test_kb_setup_issue.py -v -s
```

This test creates all resources from scratch and will fail at the KB creation step with the exact error.

## AWS Documentation References
- [Knowledge Base Setup](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html)
- [OpenSearch Serverless Vector Search](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-vector-search.html)
- [Bedrock KB API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_CreateKnowledgeBase.html)


---

## UPDATE: Latest Finding (2025-11-09 15:30)

### Fix Applied
✅ **Data Access Policy now uses actual KB role ARN** instead of hardcoded role name
- Was hardcoding: `f"arn:aws:iam::{account_id}:role/SMUSCLIKnowledgeBaseRole"`
- Now passing: Actual `kb_role_arn` from role creation to ensure correct ARN

### Result
❌ **Still fails with same "no such index" error**

### Conclusion
The data access policy permissions are NOW correct (KB role is properly included). The real blocker is that **the OpenSearch index `bedrock-knowledge-base-default-index` doesn't exist and Bedrock is trying to validate it exists before creating the KB**.

According to AWS docs, Bedrock should create this index automatically, but it's failing validation first.

### Next Steps to Try
1. **Create index manually** via OpenSearch Python client before KB creation
2. **Check if index name matters** - try different names or auto-generation
3. **Reverse-engineer AWS Console** - see what it does differently
4. **Contact AWS Support** - this might be a known issue or limitation
