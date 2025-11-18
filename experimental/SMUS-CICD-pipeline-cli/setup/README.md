# Setup Scripts

## IAM Policy Configuration

### add-agent-passrole-policy.sh

Adds an inline IAM policy to the SageMaker execution role to allow passing the Bedrock agent execution role.

**Purpose**: Enables GenAI workflows to create Bedrock agents by granting permission to pass `DEFAULT_AgentExecutionRole` to the Bedrock service.

**Usage**:
```bash
./add-agent-passrole-policy.sh
```

**What it does**:
- Adds inline policy `BedrockAgentPassRolePolicy` to `AmazonSageMakerUserIAMExecutionRole`
- Grants `iam:PassRole` permission for `DEFAULT_AgentExecutionRole` to `bedrock.amazonaws.com`

**Required for**: GenAI workflow examples that create Bedrock agents
