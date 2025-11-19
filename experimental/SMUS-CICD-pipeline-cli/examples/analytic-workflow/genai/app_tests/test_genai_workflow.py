"""Test GenAI workflow execution and agent creation."""

import os
import boto3


def test_bedrock_agent_created():
    """Verify that the Bedrock agent was created successfully."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    
    bedrock_agent = boto3.client("bedrock-agent", region_name=region)
    
    # List agents to find our test agent
    response = bedrock_agent.list_agents(maxResults=100)
    
    agents = response.get("agentSummaries", [])
    test_agents = [a for a in agents if "test_agent" in a.get("agentName", "")]
    
    assert len(test_agents) > 0, "Bedrock agent 'test_agent' not found"
    
    agent = test_agents[0]
    agent_id = agent["agentId"]
    agent_status = agent["agentStatus"]
    
    print(f"✓ Found agent: {agent['agentName']} (ID: {agent_id}, Status: {agent_status})")
    
    # Verify agent is in a valid state
    assert agent_status in [
        "CREATING",
        "PREPARED",
        "NOT_PREPARED",
    ], f"Agent in unexpected status: {agent_status}"

