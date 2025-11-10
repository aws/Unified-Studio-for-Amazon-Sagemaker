"""Unit tests for Bedrock client (mocked)."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from smus_cicd.agent.bedrock_client import BedrockClient


@pytest.fixture
def mock_bedrock():
    """Mock Bedrock client."""
    with patch('boto3.client') as mock_client:
        mock_bedrock = Mock()
        mock_client.return_value = mock_bedrock
        yield mock_bedrock


def test_bedrock_client_init():
    """Test BedrockClient initialization."""
    with patch('boto3.client'):
        client = BedrockClient('test-model', 'us-east-1')
        assert client.model_id == 'test-model'
        assert client.region == 'us-east-1'


def test_invoke_basic(mock_bedrock):
    """Test basic invoke."""
    # Setup mock response
    mock_response = {
        'body': MagicMock()
    }
    mock_response['body'].read.return_value = json.dumps({
        'content': [{'text': 'Hello!'}]
    }).encode()
    mock_bedrock.invoke_model.return_value = mock_response
    
    client = BedrockClient('test-model')
    response = client.invoke(
        messages=[{"role": "user", "content": "Hi"}]
    )
    
    assert response == 'Hello!'
    assert mock_bedrock.invoke_model.called


def test_invoke_with_system_prompt(mock_bedrock):
    """Test invoke with system prompt."""
    mock_response = {
        'body': MagicMock()
    }
    mock_response['body'].read.return_value = json.dumps({
        'content': [{'text': 'Response'}]
    }).encode()
    mock_bedrock.invoke_model.return_value = mock_response
    
    client = BedrockClient('test-model')
    response = client.invoke(
        messages=[{"role": "user", "content": "Test"}],
        system_prompt="You are helpful"
    )
    
    # Check system prompt was included
    call_args = mock_bedrock.invoke_model.call_args
    body = json.loads(call_args[1]['body'])
    assert 'system' in body
    assert body['system'] == "You are helpful"


def test_invoke_with_context(mock_bedrock):
    """Test invoke with conversation history and context."""
    mock_response = {
        'body': MagicMock()
    }
    mock_response['body'].read.return_value = json.dumps({
        'content': [{'text': 'Answer'}]
    }).encode()
    mock_bedrock.invoke_model.return_value = mock_response
    
    client = BedrockClient('test-model')
    response = client.invoke_with_context(
        user_message="What is X?",
        conversation_history=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ],
        retrieved_context=["Doc 1", "Doc 2"]
    )
    
    assert response == 'Answer'
    
    # Check context was included
    call_args = mock_bedrock.invoke_model.call_args
    body = json.loads(call_args[1]['body'])
    messages = body['messages']
    
    # Should have history + new message with context
    assert len(messages) == 3
    assert "Doc 1" in messages[-1]['content']
    assert "Doc 2" in messages[-1]['content']


def test_invoke_error_handling(mock_bedrock):
    """Test error handling."""
    from botocore.exceptions import ClientError
    
    mock_bedrock.invoke_model.side_effect = ClientError(
        {'Error': {'Code': 'ValidationException', 'Message': 'Invalid input'}},
        'InvokeModel'
    )
    
    client = BedrockClient('test-model')
    
    with pytest.raises(Exception) as exc_info:
        client.invoke(messages=[{"role": "user", "content": "Test"}])
    
    assert 'ValidationException' in str(exc_info.value)
