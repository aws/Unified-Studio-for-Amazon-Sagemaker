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

### add-bedrock-invoke-policy.sh

Adds an inline IAM policy to the SageMaker execution role to allow invoking Bedrock agents and models.

**Purpose**: Enables notebooks and workflows to invoke Bedrock agents and models.

**Usage**:
```bash
./add-bedrock-invoke-policy.sh
```

**What it does**:
- Adds inline policy `BedrockInvokeAgentPolicy` to `AmazonSageMakerUserIAMExecutionRole`
- Grants permissions:
  - `bedrock:InvokeAgent` - Invoke Bedrock agents
  - `bedrock:InvokeModel` - Invoke Bedrock models
  - `bedrock:GetAgent` - Get agent details
  - `bedrock:ListAgents` - List available agents

**Required for**: GenAI workflow examples that invoke Bedrock agents from notebooks

## Running All Setup Scripts

To configure all required IAM policies for GenAI workflows:

```bash
cd setup
./add-agent-passrole-policy.sh
./add-bedrock-invoke-policy.sh
```
