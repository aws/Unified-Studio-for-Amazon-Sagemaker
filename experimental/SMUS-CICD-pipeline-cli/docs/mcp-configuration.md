# MCP Configuration Guide

← [Back to Main README](../README.md)


## Overview

The MCP server knowledge base is configurable via YAML files. This allows you to customize what documentation and templates are loaded into the Q CLI integration.

## Default Configuration

The default configuration is in `mcp-config.yaml` at the repository root:

```yaml
docs:
  - path: README.md
    description: Main project documentation
  - path: docs/
    description: All documentation files
    recursive: true
    include: ['*.md', '*.pdf']

templates:
  cicd_pipelines:
    - path: examples/
      description: Pipeline manifest examples
      include: ['*pipeline*.yaml']
  
  github_workflows:
    - path: .github/workflows/
      description: GitHub Actions workflows
      include: ['*.yml', '*.yaml']
  
  airflow_workflows:
    - path: examples/workflows/
      description: Airflow DAG examples
      include: ['*.py']
      exclude: ['__pycache__/', '*.pyc']
```

## Configuration Structure

### Docs Section

Defines documentation files to include in the knowledge base:

- `path`: File or directory path (relative to repository root)
- `description`: Human-readable description
- `recursive`: (Optional) Search subdirectories
- `include`: (Optional) File patterns to include (glob patterns)

### Templates Section

Organized by category with multiple template sources:

- **cicd_pipelines**: Pipeline manifest templates
- **github_workflows**: GitHub Actions workflow templates
- **airflow_workflows**: Airflow DAG templates

Each template source supports:
- `path`: Directory or file path
- `description`: Human-readable description
- `include`: File patterns to include
- `exclude`: Patterns to exclude

## Using Custom Configuration

### Setup with Custom Config

```bash
smus-cli integrate qcli --configure my-config.yaml
```

### Example Custom Configuration

```yaml
docs:
  - path: README.md
  - path: docs/
    recursive: true
    include: ['*.md']
  - path: internal-docs/
    recursive: true
    include: ['*.md', '*.txt']

templates:
  cicd_pipelines:
    - path: my-templates/pipelines/
      include: ['*.yaml']
  
  github_workflows:
    - path: .github/workflows/
      include: ['*.yml']
  
  airflow_workflows:
    - path: dags/
      include: ['*.py']
      exclude: ['test_*.py', '__pycache__/']
  
  custom_scripts:
    - path: scripts/
      include: ['*.sh', '*.py']
```

## Environment Variable

The configuration path is passed via the `SMUS_MCP_CONFIG` environment variable to the MCP server.

## Querying the Knowledge Base

Once configured, use Q CLI to query:

```bash
q chat
You: Show me a pipeline example
You: What GitHub workflows are available?
You: How do I configure Airflow workflows?
```

The MCP server will search across all configured docs and templates.
