"""Test GenAI workflow execution and agent creation."""

import boto3


def test_bedrock_agent_created(smus_config):
    """Verify that the Bedrock agent was created successfully."""
    region = smus_config["region"]
    
    bedrock_agent = boto3.client("bedrock-agent", region_name=region)
    
    # List agents to find our test agent
    response = bedrock_agent.list_agents(maxResults=100)
    
    agents = response.get("agentSummaries", [])
    test_agents = [a for a in agents if "mortgage_test_agent" in a.get("agentName", "")]
    
    assert len(test_agents) > 0, "Bedrock agent 'mortgage_test_agent' not found"
    
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


def test_workflow_completed_successfully(smus_config):
    """Verify the workflow run completed successfully."""
    from smus_cicd.helpers.airflow_serverless import list_workflows, get_workflow_runs
    
    region = smus_config["region"]
    project_name = smus_config["project_name"]
    
    # List workflows to find our workflow
    workflows = list_workflows(region=region)
    assert workflows.get("success"), "Failed to list workflows"
    
    workflow_list = workflows.get("workflows", [])
    genai_workflows = [
        w
        for w in workflow_list
        if "genai_dev_workflow" in w.get("Name", "")
        and project_name in w.get("Name", "")
    ]
    
    assert len(genai_workflows) > 0, "GenAI workflow not found"
    
    workflow_arn = genai_workflows[0]["Arn"]
    
    # Get recent runs
    runs = get_workflow_runs(workflow_arn, region=region)
    assert runs.get("success"), "Failed to get workflow runs"
    
    run_list = runs.get("runs", [])
    assert len(run_list) > 0, "No workflow runs found"
    
    # Check most recent run
    latest_run = run_list[0]
    status = latest_run.get("Status")
    
    assert status == "SUCCEEDED", f"Latest workflow run status: {status}"
    print(f"✓ Workflow completed successfully (run_id: {latest_run.get('RunId')})")
