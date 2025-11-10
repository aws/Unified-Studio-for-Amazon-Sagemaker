"""
Test 2: Create Bedrock Knowledge Base with existing index.

This test assumes the index already exists (created by test_kb_index_creation.py).
"""
import pytest
import boto3


@pytest.mark.integration
class TestKBCreationWithIndex:
    """Test KB creation when index already exists."""
    
    def test_create_kb_with_existing_index(self):
        """
        Create Bedrock Knowledge Base using pre-existing OpenSearch index.
        
        Prerequisites:
        - Run test_kb_index_creation.py first to create the index
        - Collection must be ACTIVE
        - Index 'bedrock-knowledge-base-default-index' must exist
        """
        region = 'us-east-2'
        collection_name = 'smus-cli-kb'
        index_name = 'bedrock-knowledge-base-default-index'
        
        aoss = boto3.client('opensearchserverless', region_name=region)
        bedrock_agent = boto3.client('bedrock-agent', region_name=region)
        iam = boto3.client('iam')
        sts = boto3.client('sts')
        
        account_id = sts.get_caller_identity()['Account']
        
        # Get collection ARN
        print("\n1. Getting collection details...")
        response = aoss.batch_get_collection(names=[collection_name])
        
        if not response['collectionDetails']:
            pytest.fail(f"Collection {collection_name} not found")
        
        collection = response['collectionDetails'][0]
        if collection['status'] != 'ACTIVE':
            pytest.fail(f"Collection status is {collection['status']}, must be ACTIVE")
        
        collection_arn = collection['arn']
        print(f"   Collection ARN: {collection_arn}")
        
        # Get KB role ARN
        print("\n2. Getting KB role...")
        role_name = 'SMUSCLIKnowledgeBaseRole'
        try:
            role_response = iam.get_role(RoleName=role_name)
            role_arn = role_response['Role']['Arn']
            print(f"   Role ARN: {role_arn}")
        except:
            pytest.fail(f"Role {role_name} not found. Run KB setup test first.")
        
        # Create Knowledge Base
        print(f"\n3. Creating Knowledge Base...")
        print(f"   Using index: {index_name}")
        
        try:
            kb_response = bedrock_agent.create_knowledge_base(
                name='SMUS-CLI-KB-Test',
                description='SMUS CLI Knowledge Base with pre-created index',
                roleArn=role_arn,
                knowledgeBaseConfiguration={
                    'type': 'VECTOR',
                    'vectorKnowledgeBaseConfiguration': {
                        'embeddingModelArn': f'arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v1'
                    }
                },
                storageConfiguration={
                    'type': 'OPENSEARCH_SERVERLESS',
                    'opensearchServerlessConfiguration': {
                        'collectionArn': collection_arn,
                        'vectorIndexName': index_name,
                        'fieldMapping': {
                            'vectorField': 'bedrock-knowledge-base-default-vector',
                            'textField': 'AMAZON_BEDROCK_TEXT_CHUNK',
                            'metadataField': 'AMAZON_BEDROCK_METADATA'
                        }
                    }
                }
            )
            
            kb_id = kb_response['knowledgeBase']['knowledgeBaseId']
            kb_status = kb_response['knowledgeBase']['status']
            
            print(f"\n✅ SUCCESS! Knowledge Base created!")
            print(f"   KB ID: {kb_id}")
            print(f"   Status: {kb_status}")
            
            # Verify KB exists
            print(f"\n4. Verifying Knowledge Base...")
            kb_details = bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)
            print(f"   Name: {kb_details['knowledgeBase']['name']}")
            print(f"   Status: {kb_details['knowledgeBase']['status']}")
            print(f"   Created: {kb_details['knowledgeBase']['createdAt']}")
            
            # Create data source
            print(f"\n5. Creating data source...")
            s3_bucket = f"smus-cli-kb-{account_id}"
            
            ds_response = bedrock_agent.create_data_source(
                knowledgeBaseId=kb_id,
                name='SMUS-CLI-Docs',
                dataSourceConfiguration={
                    'type': 'S3',
                    's3Configuration': {
                        'bucketArn': f'arn:aws:s3:::{s3_bucket}'
                    }
                }
            )
            
            ds_id = ds_response['dataSource']['dataSourceId']
            print(f"   ✅ Data source created: {ds_id}")
            
            print(f"\n✅ COMPLETE! Knowledge Base is ready!")
            print(f"\nKB ID: {kb_id}")
            print(f"Data Source ID: {ds_id}")
            print(f"\nTo sync data: aws bedrock-agent start-ingestion-job --knowledge-base-id {kb_id} --data-source-id {ds_id} --region {region}")
            
            # Store IDs for cleanup
            return kb_id, ds_id
            
        except Exception as e:
            pytest.fail(f"Failed to create Knowledge Base: {e}")
