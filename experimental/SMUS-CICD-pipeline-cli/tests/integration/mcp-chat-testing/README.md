# Q CLI Conversation Test Scenarios

This directory contains automated conversation scenarios that simulate realistic interactions between users and Q CLI using the SMUS MCP server.

## Overview

Each YAML file defines a conversation scenario with:
- User inputs
- MCP tool calls
- Assertions to validate responses
- Expected outcomes

## Scenario Format

```yaml
scenario: scenario_name
description: What this scenario tests

turns:
  - type: user_input
    message: "User's question or request"
  
  - type: tool_call
    tool: query_smus_kb
    arguments:
      query: "search term"
    save_as: result_name
  
  - type: assertion
    check: contains
    target: result_name
    value: "expected text"

expected_outcome:
  key: value
```

## Turn Types

### user_input
Simulates user message in conversation.

```yaml
- type: user_input
  message: "I want to create a pipeline"
```

### tool_call
Calls an MCP tool and saves the result.

```yaml
- type: tool_call
  tool: get_pipeline_example
  arguments:
    use_case: "etl"
  save_as: pipeline
```

**Available Tools:**
- `query_smus_kb` - Search documentation
- `get_pipeline_example` - Generate pipeline template
- `validate_pipeline` - Validate pipeline YAML

### assertion
Validates tool call results.

```yaml
- type: assertion
  check: contains
  target: pipeline
  value: "pipelineName"
```

**Check Types:**
- `contains` - Text contains value (case-insensitive)
- `not_contains` - Text does not contain value
- `valid_yaml` - Content is valid YAML
- `regex` - Text matches regex pattern

## Variable Resolution

Use `${variable}` syntax to reference saved results:

```yaml
- type: tool_call
  tool: validate_pipeline
  arguments:
    yaml_content: "${pipeline.content[0].text}"
```

## Running Tests

### Run all scenarios:
```bash
pytest tests/integration/test_qcli_conversations.py -v
```

### Run specific scenario:
```bash
pytest tests/integration/test_qcli_conversations.py::test_glue_job_pipeline_conversation -v
```

### Debug mode:
```bash
pytest tests/integration/test_qcli_conversations.py -v -s
```

## Creating New Scenarios

1. Create a new YAML file in this directory
2. Define the conversation flow
3. Add assertions to validate behavior
4. Run tests to verify

Example:
```yaml
scenario: my_new_scenario
description: Test something specific

turns:
  - type: user_input
    message: "User question"
  
  - type: tool_call
    tool: query_smus_kb
    arguments:
      query: "search term"
    save_as: result
  
  - type: assertion
    check: contains
    target: result
    value: "expected"
```

## Existing Scenarios

- **glue_job_pipeline.yaml** - Create CICD for AWS Glue job
- **validate_pipeline.yaml** - Validate existing pipeline
- **notebook_deployment.yaml** - Deploy Jupyter notebooks

## Best Practices

1. **Keep scenarios focused** - Test one workflow per scenario
2. **Use descriptive names** - Make it clear what's being tested
3. **Add assertions** - Validate key outputs at each step
4. **Document expected outcomes** - Help future maintainers understand intent
5. **Test error cases** - Include scenarios for common mistakes

## Limitations

- Tests MCP tools directly, not actual Q CLI
- Cannot test Q's natural language understanding
- Cannot test Q's response generation
- Deterministic only (no AI variability)

## Manual Verification

For full validation:
1. Run automated tests (validates tool behavior)
2. Manually test with Q CLI (validates user experience)
3. Document any differences in `docs/Q_CLI_CONVERSATION_EXAMPLES.md`
