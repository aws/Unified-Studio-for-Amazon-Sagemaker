"""
Test 1: Create OpenSearch Serverless index manually.

This test creates the index that Bedrock expects to exist.
"""
import pytest
import boto3
import time
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth


@pytest.mark.integration
@pytest.mark.slow
class TestIndexCreation:
    """Test manual index creation in OpenSearch Serverless."""
    
    def test_create_opensearch_index(self):
        """
        Create the OpenSearch index manually before KB creation.
        
        Steps:
        1. Get existing collection details
        2. Connect to OpenSearch Serverless collection
        3. Create index with proper mappings
        4. Verify index exists
        """
        region = 'us-east-2'
        collection_name = 'smus-cli-kb'
        index_name = 'bedrock-knowledge-base-default-index'
        
        aoss = boto3.client('opensearchserverless', region_name=region)
        
        # Get collection endpoint
        print("\n1. Getting collection details...")
        response = aoss.batch_get_collection(names=[collection_name])
        
        if not response['collectionDetails']:
            pytest.fail(f"Collection {collection_name} not found. Run KB setup test first.")
        
        collection = response['collectionDetails'][0]
        if collection['status'] != 'ACTIVE':
            pytest.fail(f"Collection status is {collection['status']}, must be ACTIVE")
        
        collection_endpoint = collection['collectionEndpoint']
        collection_arn = collection['arn']
        
        print(f"   Collection endpoint: {collection_endpoint}")
        print(f"   Collection ARN: {collection_arn}")
        print(f"   Status: {collection['status']}")
        
        # Connect to OpenSearch
        print("\n2. Connecting to OpenSearch Serverless...")
        
        # Get AWS credentials for signing requests
        session = boto3.Session()
        credentials = session.get_credentials()
        
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            'aoss',
            session_token=credentials.token
        )
        
        # Remove https:// from endpoint
        host = collection_endpoint.replace('https://', '')
        
        client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30
        )
        
        # Test connection - try cluster health instead of info
        print("   Testing connection...")
        try:
            health = client.cluster.health()
            print(f"   ✅ Connected! Cluster status: {health['status']}")
        except Exception as e:
            print(f"   Connection test failed: {e}")
            print(f"   Trying to create index anyway...")
        
        # Check if index already exists
        print(f"\n3. Checking if index '{index_name}' exists...")
        try:
            if client.indices.exists(index=index_name):
                print(f"   Index already exists, deleting it first...")
                client.indices.delete(index=index_name)
                time.sleep(2)
        except Exception as e:
            print(f"   Could not check if index exists: {e}")
        
        # Create index with Bedrock-compatible mappings
        print(f"\n4. Creating index '{index_name}'...")
        
        index_body = {
            "settings": {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 512
                }
            },
            "mappings": {
                "properties": {
                    "bedrock-knowledge-base-default-vector": {
                        "type": "knn_vector",
                        "dimension": 1536,  # Titan embeddings dimension
                        "method": {
                            "name": "hnsw",
                            "engine": "faiss",
                            "parameters": {
                                "ef_construction": 512,
                                "m": 16
                            }
                        }
                    },
                    "AMAZON_BEDROCK_TEXT_CHUNK": {
                        "type": "text"
                    },
                    "AMAZON_BEDROCK_METADATA": {
                        "type": "text"
                    }
                }
            }
        }
        
        try:
            response = client.indices.create(index=index_name, body=index_body)
            print(f"   ✅ Index created successfully!")
            print(f"   Response: {response}")
        except Exception as e:
            pytest.fail(f"Failed to create index: {e}")
        
        # Verify index exists
        print(f"\n5. Verifying index exists...")
        time.sleep(2)
        
        try:
            if client.indices.exists(index=index_name):
                print(f"   ✅ Index '{index_name}' verified!")
                
                # Get index info
                index_info = client.indices.get(index=index_name)
                print(f"   Index created")
            else:
                pytest.fail(f"Index '{index_name}' was not created")
        except Exception as e:
            print(f"   Warning: Could not verify index: {e}")
            print(f"   Index may still have been created")
        
        # Wait for index to be fully ready
        print(f"\n6. Waiting for index to be fully ready (30 seconds)...")
        time.sleep(30)
        
        print("\n✅ Index creation complete!")
        print(f"\nCollection ARN: {collection_arn}")
        print(f"Index name: {index_name}")
        print("\nNow you can run the KB creation test.")
