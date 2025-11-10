"""Test CloudFormation-based KB setup."""

import pytest
import boto3
import time
from smus_cicd.agent.kb_setup import (
    deploy_kb_stack,
    create_opensearch_index,
    create_bedrock_kb,
    create_data_source,
    start_ingestion,
    delete_kb_stack
)


@pytest.mark.integration
def test_kb_full_setup_with_cloudformation():
    """Test complete KB setup using CloudFormation stack."""
    region = 'us-east-2'
    
    try:
        # 1. Deploy CloudFormation stack (auto-approve for tests)
        print("\n=== Step 1: Deploy CloudFormation Stack ===")
        outputs = deploy_kb_stack(region=region, auto_approve=True)
        
        assert 'CollectionEndpoint' in outputs
        assert 'CollectionArn' in outputs
        assert 'KnowledgeBaseRoleArn' in outputs
        assert 'BucketName' in outputs
        
        print(f"✅ Stack outputs: {outputs}")
        
        # Wait for policies to propagate
        print("\n⏳ Waiting 2 minutes for policies to propagate...")
        time.sleep(120)
        
        # 2. Create OpenSearch index
        print("\n=== Step 2: Create OpenSearch Index ===")
        create_opensearch_index(
            collection_endpoint=outputs['CollectionEndpoint'],
            region=region
        )
        
        # 3. Create Bedrock KB
        print("\n=== Step 3: Create Bedrock Knowledge Base ===")
        kb_result = create_bedrock_kb(
            role_arn=outputs['KnowledgeBaseRoleArn'],
            collection_arn=outputs['CollectionArn'],
            region=region
        )
        
        assert 'kb_id' in kb_result
        kb_id = kb_result['kb_id']
        print(f"✅ KB ID: {kb_id}")
        
        # 4. Create data source
        print("\n=== Step 4: Create Data Source ===")
        ds_id = create_data_source(
            kb_id=kb_id,
            bucket_name=outputs['BucketName'],
            region=region
        )
        
        assert ds_id
        print(f"✅ Data Source ID: {ds_id}")
        
        # 5. Start ingestion
        print("\n=== Step 5: Start Ingestion ===")
        job_id = start_ingestion(kb_id=kb_id, ds_id=ds_id, region=region)
        
        assert job_id
        print(f"✅ Ingestion Job ID: {job_id}")
        
        print("\n✅ Full KB setup completed successfully!")
        
    except Exception as e:
        # Show stack events before cleanup
        print(f"\n❌ Error: {e}")
        print("\n=== Stack Events ===")
        cfn = boto3.client('cloudformation', region_name=region)
        try:
            events = cfn.describe_stack_events(StackName='smus-cli-kb-stack')
            for event in events['StackEvents'][:10]:
                if 'FAILED' in event['ResourceStatus']:
                    print(f"❌ {event['LogicalResourceId']}: {event['ResourceStatus']}")
                    print(f"   {event.get('ResourceStatusReason', 'N/A')}")
        except:
            pass
        raise
    finally:
        # Cleanup
        print("\n=== Cleanup ===")
        delete_kb_stack(region=region)


@pytest.mark.integration
def test_kb_stack_idempotency():
    """Test that stack deployment is idempotent."""
    region = 'us-east-2'
    
    try:
        # Deploy stack twice
        print("\n=== First deployment ===")
        outputs1 = deploy_kb_stack(region=region, auto_approve=True)
        
        print("\n=== Second deployment (should be idempotent) ===")
        outputs2 = deploy_kb_stack(region=region, auto_approve=True)
        
        # Should get same outputs
        assert outputs1['CollectionArn'] == outputs2['CollectionArn']
        assert outputs1['KnowledgeBaseRoleArn'] == outputs2['KnowledgeBaseRoleArn']
        
        print("✅ Stack deployment is idempotent")
        
    finally:
        delete_kb_stack(region=region)


if __name__ == '__main__':
    # Run full setup test
    test_kb_full_setup_with_cloudformation()
