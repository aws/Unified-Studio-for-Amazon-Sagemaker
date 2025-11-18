# GenAI Workflow - Bedrock Agent Example

This workflow demonstrates how to create and test AWS Bedrock Agents using SageMaker Unified Studio CICD pipeline.

## Structure

```
genai/
├── README.md                           # This file
├── manifest.yaml                 # Pipeline configuration
├── job-code/                           # Lambda functions and agent code
│   ├── lambda_mask_string.py          # Lambda function for masking strings
│   └── requirements.txt               # Python dependencies
├── workflows/                          # Workflow definitions and notebooks
│   ├── bedrock_agent_notebook.ipynb   # Parameterized notebook for agent creation
│   └── genai_dev_workflow.yaml        # Airflow workflow definition
└── app_tests/                     # Pipeline tests
```

## Features

- **Account-Agnostic**: Uses environment variables and dynamic connections
- **Parameterized**: Notebook parameters can be customized via workflow YAML
- **Cleanup First**: Deletes previous test runs before creating new resources
- **No End Cleanup**: Leaves resources for inspection after workflow completion

## Workflow Steps

1. **Cleanup**: Removes agents and lambda functions from previous runs
2. **Create Agent**: Creates a calculator agent with code interpreter
3. **Attach Tool**: Adds mask_string tool from Python function
4. **Test Agent**: Validates agent with calculation and masking tasks

## Parameters

- `agent_name`: Name of the Bedrock agent (default: "calculator_agent")
- `agent_llm`: LLM model to use (default: "us.anthropic.claude-3-5-sonnet-20241022-v2:0")
- `force_recreate`: Force recreation of existing agents (default: true)

## Usage

```bash
# Deploy to test environment
smus-cli deploy test --manifest genai/manifest.yaml

# Run workflow
smus-cli run --workflow genai_dev_workflow --targets test --manifest genai/manifest.yaml
```
# Trigger workflow




