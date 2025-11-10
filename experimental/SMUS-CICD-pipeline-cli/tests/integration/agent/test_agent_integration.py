"""Integration tests for agent with real AWS services."""

import pytest
import os
import boto3
from botocore.exceptions import ClientError

from smus_cicd.agent.bedrock_client import BedrockClient
from smus_cicd.agent.kb_retrieval import KnowledgeBaseRetriever
from smus_cicd.agent.config import load_config, get_kb_id


# Skip if no AWS credentials
pytestmark = pytest.mark.skipif(
    not os.environ.get('AWS_ACCESS_KEY_ID') and not os.path.exists(os.path.expanduser('~/.aws/credentials')),
    reason="AWS credentials not available"
)


@pytest.fixture
def check_bedrock_access():
    """Check if Bedrock is accessible."""
    try:
        bedrock = boto3.client('bedrock', region_name='us-east-1')
        bedrock.list_foundation_models(byProvider='anthropic')
        return True
    except Exception:
        pytest.skip("Bedrock not accessible in this account/region")


@pytest.fixture
def model_id():
    """Get model ID for testing."""
    return 'anthropic.claude-3-5-haiku-20241022-v1:0'


class TestBedrockIntegration:
    """Integration tests for Bedrock client."""
    
    def test_invoke_real_model(self, check_bedrock_access, model_id):
        """Test invoking real Bedrock model."""
        client = BedrockClient(model_id, 'us-east-1')
        
        response = client.invoke(
            messages=[{"role": "user", "content": "Say 'test successful' and nothing else"}],
            max_tokens=100
        )
        
        assert response is not None
        assert len(response) > 0
        assert 'test successful' in response.lower()
    
    def test_invoke_with_system_prompt(self, check_bedrock_access, model_id):
        """Test invoke with system prompt."""
        client = BedrockClient(model_id, 'us-east-1')
        
        response = client.invoke(
            messages=[{"role": "user", "content": "What are you?"}],
            system_prompt="You are a SMUS CLI expert. Answer in 5 words or less.",
            max_tokens=50
        )
        
        assert response is not None
        assert len(response.split()) <= 10  # Should be brief
    
    def test_invoke_with_conversation_history(self, check_bedrock_access, model_id):
        """Test invoke with conversation history."""
        client = BedrockClient(model_id, 'us-east-1')
        
        response = client.invoke_with_context(
            user_message="What did I just say?",
            conversation_history=[
                {"role": "user", "content": "My name is Alice"},
                {"role": "assistant", "content": "Hello Alice!"}
            ],
            max_tokens=100
        )
        
        assert response is not None
        assert 'alice' in response.lower()


class TestKBIntegration:
    """Integration tests for Knowledge Base retrieval."""
    
    @pytest.fixture
    def kb_id(self):
        """Get KB ID from config if available."""
        kb_id = get_kb_id()
        if not kb_id:
            pytest.skip("No Knowledge Base configured. Run: smus-cli kb setup")
        return kb_id
    
    def test_retrieve_from_kb(self, kb_id):
        """Test retrieving from real KB."""
        retriever = KnowledgeBaseRetriever(kb_id, 'us-east-1')
        
        docs = retriever.retrieve(
            "How do I deploy to multiple targets?",
            max_results=3
        )
        
        # Should get some results
        assert isinstance(docs, list)
        # May be empty if KB is new or not ingested yet
        if docs:
            assert all(isinstance(doc, str) for doc in docs)
            assert all(len(doc) > 0 for doc in docs)
    
    def test_retrieve_with_metadata(self, kb_id):
        """Test retrieving with metadata."""
        retriever = KnowledgeBaseRetriever(kb_id, 'us-east-1')
        
        results = retriever.retrieve_with_metadata(
            "pipeline manifest",
            max_results=2
        )
        
        assert isinstance(results, list)
        if results:
            assert 'text' in results[0]
            assert 'score' in results[0]
            assert 'source' in results[0]


class TestEndToEnd:
    """End-to-end integration tests."""
    
    def test_chat_agent_basic_qa(self, check_bedrock_access, model_id):
        """Test basic Q&A without KB."""
        from smus_cicd.agent.chat_agent import SMUSChatAgent
        
        agent = SMUSChatAgent(model_id=model_id, kb_id=None)
        
        response = agent._process_message("What is SMUS CLI?")
        
        assert response is not None
        assert len(response) > 0
        assert isinstance(response, str)
    
    def test_chat_agent_with_kb(self, check_bedrock_access, model_id):
        """Test Q&A with KB if available."""
        from smus_cicd.agent.chat_agent import SMUSChatAgent
        
        kb_id = get_kb_id()
        if not kb_id:
            pytest.skip("No KB configured")
        
        agent = SMUSChatAgent(model_id=model_id, kb_id=kb_id)
        
        response = agent._process_message("How do I create a pipeline manifest?")
        
        assert response is not None
        assert len(response) > 0
        
        # Should have conversation history
        assert len(agent.conversation_history) == 2  # user + assistant
    
    def test_conversation_history_maintained(self, check_bedrock_access, model_id):
        """Test conversation history is maintained."""
        from smus_cicd.agent.chat_agent import SMUSChatAgent
        
        agent = SMUSChatAgent(model_id=model_id, kb_id=None)
        
        # First message
        agent._process_message("My name is Bob")
        
        # Second message referencing first
        response = agent._process_message("What is my name?")
        
        assert 'bob' in response.lower()
        assert len(agent.conversation_history) == 4  # 2 exchanges


@pytest.mark.slow
class TestKBSetup:
    """Integration tests for KB setup (slow, creates resources)."""
    
    def test_kb_bucket_uri_generation(self):
        """Test KB bucket URI generation."""
        from smus_cicd.agent.kb_setup import get_kb_bucket_uri
        
        uri = get_kb_bucket_uri('123456789012')
        assert uri == 's3://smus-cli-kb-123456789012/'
    
    # Note: Actual KB creation test would be very slow and create resources
    # Run manually with: pytest -m slow tests/integration/agent/
