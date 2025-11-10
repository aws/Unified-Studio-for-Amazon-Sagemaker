"""Unit tests for KB retrieval (mocked)."""

import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from smus_cicd.agent.kb_retrieval import KnowledgeBaseRetriever


@pytest.fixture
def mock_bedrock_agent():
    """Mock Bedrock Agent Runtime client."""
    with patch('boto3.client') as mock_client:
        mock_agent = Mock()
        mock_client.return_value = mock_agent
        yield mock_agent


def test_retriever_init():
    """Test retriever initialization."""
    with patch('boto3.client'):
        retriever = KnowledgeBaseRetriever('kb-123', 'us-east-1')
        assert retriever.kb_id == 'kb-123'
        assert retriever.region == 'us-east-1'


def test_retrieve_basic(mock_bedrock_agent):
    """Test basic retrieval."""
    mock_bedrock_agent.retrieve.return_value = {
        'retrievalResults': [
            {
                'content': {'text': 'Document 1'},
                'score': 0.9
            },
            {
                'content': {'text': 'Document 2'},
                'score': 0.8
            }
        ]
    }
    
    retriever = KnowledgeBaseRetriever('kb-123')
    docs = retriever.retrieve('test query')
    
    assert len(docs) == 2
    assert docs[0] == 'Document 1'
    assert docs[1] == 'Document 2'


def test_retrieve_filters_low_scores(mock_bedrock_agent):
    """Test retrieval filters low scores."""
    mock_bedrock_agent.retrieve.return_value = {
        'retrievalResults': [
            {
                'content': {'text': 'Good doc'},
                'score': 0.9
            },
            {
                'content': {'text': 'Bad doc'},
                'score': 0.3
            }
        ]
    }
    
    retriever = KnowledgeBaseRetriever('kb-123')
    docs = retriever.retrieve('test query', min_score=0.5)
    
    assert len(docs) == 1
    assert docs[0] == 'Good doc'


def test_retrieve_no_kb_id(mock_bedrock_agent):
    """Test retrieval with no KB ID."""
    retriever = KnowledgeBaseRetriever(None)
    docs = retriever.retrieve('test query')
    
    assert docs == []
    assert not mock_bedrock_agent.retrieve.called


def test_retrieve_kb_not_found(mock_bedrock_agent):
    """Test retrieval when KB not found."""
    mock_bedrock_agent.retrieve.side_effect = ClientError(
        {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'KB not found'}},
        'Retrieve'
    )
    
    retriever = KnowledgeBaseRetriever('kb-123')
    docs = retriever.retrieve('test query')
    
    assert docs == []


def test_retrieve_with_metadata(mock_bedrock_agent):
    """Test retrieval with metadata."""
    mock_bedrock_agent.retrieve.return_value = {
        'retrievalResults': [
            {
                'content': {'text': 'Document 1'},
                'score': 0.9,
                'location': {
                    's3Location': {
                        'uri': 's3://bucket/doc1.md'
                    }
                }
            }
        ]
    }
    
    retriever = KnowledgeBaseRetriever('kb-123')
    results = retriever.retrieve_with_metadata('test query')
    
    assert len(results) == 1
    assert results[0]['text'] == 'Document 1'
    assert results[0]['score'] == 0.9
    assert results[0]['source'] == 's3://bucket/doc1.md'


def test_retrieve_max_results(mock_bedrock_agent):
    """Test max results parameter."""
    mock_bedrock_agent.retrieve.return_value = {
        'retrievalResults': []
    }
    
    retriever = KnowledgeBaseRetriever('kb-123')
    retriever.retrieve('test query', max_results=10)
    
    # Check max_results was passed
    call_args = mock_bedrock_agent.retrieve.call_args
    assert call_args[1]['retrievalConfiguration']['vectorSearchConfiguration']['numberOfResults'] == 10
