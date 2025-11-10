"""Integration tests for SMUS CLI Agent with real AWS services."""
import pytest
import boto3
from pathlib import Path
from smus_cicd.agent.bedrock_client import BedrockClient
from smus_cicd.agent.kb_retrieval import KnowledgeBaseRetriever
from smus_cicd.agent.chat_agent import SMUSChatAgent
from smus_cicd.agent.kb_setup import create_user_kb, cleanup_kb


# Use inference profile for cross-region routing
DEFAULT_MODEL = "us.anthropic.claude-3-5-haiku-20241022-v1:0"


@pytest.mark.integration
class TestBedrockIntegration:
    """Test real Bedrock API calls."""
    
    def test_bedrock_invoke_model(self):
        """Test invoking Bedrock model with real API."""
        client = BedrockClient(model_id=DEFAULT_MODEL, region='us-east-2')
        
        response = client.invoke(
            messages=[{"role": "user", "content": "What is Amazon SageMaker Unified Studio? Answer in one sentence."}],
            max_tokens=100
        )
        
        assert response is not None
        assert len(response) > 0
    
    def test_bedrock_conversation(self):
        """Test multi-turn conversation."""
        client = BedrockClient(model_id=DEFAULT_MODEL, region='us-east-2')
        
        # First turn
        response1 = client.invoke(
            messages=[{"role": "user", "content": "What is a pipeline?"}],
            max_tokens=50
        )
        assert len(response1) > 0
        
        # Second turn with history
        response2 = client.invoke(
            messages=[
                {"role": "user", "content": "What is a pipeline?"},
                {"role": "assistant", "content": response1},
                {"role": "user", "content": "How do I create one?"}
            ],
            max_tokens=50
        )
        assert len(response2) > 0


@pytest.mark.integration
@pytest.mark.slow
class TestKnowledgeBaseSetup:
    """Test KB setup and teardown."""
    
    def test_kb_full_setup_and_cleanup(self):
        """Test complete KB setup and cleanup flow."""
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        
        # Clean up any leftover resources from previous failed runs
        aoss = boto3.client('opensearchserverless', region_name='us-east-2')
        try:
            response = aoss.batch_get_collection(names=['smus-cli-kb'])
            if response['collectionDetails']:
                collection_id = response['collectionDetails'][0]['id']
                aoss.delete_collection(id=collection_id)
                print(f"Cleaned up leftover collection: {collection_id}")
                # Wait for deletion
                import time
                time.sleep(30)
        except Exception:
            pass
        
        # Setup
        kb_id, ds_id = create_user_kb(account_id)
        
        assert kb_id is not None
        assert ds_id is not None
        
        # Verify KB exists
        bedrock_agent = boto3.client('bedrock-agent', region_name='us-east-2')
        kb_response = bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)
        assert kb_response['knowledgeBase']['status'] in ['ACTIVE', 'CREATING']
        
        # Verify S3 bucket exists
        s3 = boto3.client('s3', region_name='us-east-2')
        bucket_name = f"smus-cli-kb-{account_id}"
        s3.head_bucket(Bucket=bucket_name)
        
        # Verify collection exists
        collection_response = aoss.batch_get_collection(names=['smus-cli-kb'])
        assert len(collection_response['collectionDetails']) > 0
        
        # Cleanup
        cleanup_kb(kb_id, ds_id)
        
        # Verify cleanup
        with pytest.raises(Exception):
            bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)


@pytest.mark.integration
class TestKnowledgeBaseIntegration:
    """Test real Knowledge Base retrieval."""
    
    def test_kb_retrieval(self):
        """Test retrieving from Knowledge Base."""
        from smus_cicd.agent.config import load_config
        
        config = load_config()
        kb_id = config.get('bedrock', {}).get('knowledge_base_id')
        
        if not kb_id:
            pytest.skip("Knowledge Base not configured")
        
        kb = KnowledgeBaseRetriever(kb_id=kb_id, region='us-east-2')
        
        results = kb.retrieve(
            query="How do I deploy to multiple targets?",
            max_results=3
        )
        
        assert len(results) > 0
        assert any('deploy' in r['text'].lower() for r in results)


@pytest.mark.integration
class TestChatAgentIntegration:
    """Test complete chat agent with real AWS."""
    
    def test_agent_simple_question(self):
        """Test agent answering a simple question."""
        # Pass kb_id=False to skip KB setup
        agent = SMUSChatAgent(model_id=DEFAULT_MODEL, kb_id=False)
        
        response = agent._process_message("What is SMUS CLI?")
        
        assert response is not None
        assert len(response) > 20
    
    def test_agent_conversation_context(self):
        """Test agent maintains conversation context."""
        # Pass kb_id=False to skip KB setup
        agent = SMUSChatAgent(model_id=DEFAULT_MODEL, kb_id=False)
        
        # First message
        response1 = agent._process_message("What are targets?")
        assert len(response1) > 0
        
        # Follow-up using context
        response2 = agent._process_message("How many can I have?")
        assert len(response2) > 0
        assert len(agent.conversation_history) == 4  # 2 turns = 4 messages
