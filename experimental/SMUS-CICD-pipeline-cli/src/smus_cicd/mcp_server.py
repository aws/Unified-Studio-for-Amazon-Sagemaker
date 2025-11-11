#!/usr/bin/env python3
"""MCP Server for SMUS CLI integration with Q CLI."""

import json
import sys
from pathlib import Path
from typing import Any, Dict


class SMUSMCPServer:
    """MCP Server exposing SMUS CLI capabilities to Q CLI."""

    def __init__(self):
        """Initialize SMUS MCP server."""
        self.docs = self._load_local_docs()

    def _load_local_docs(self):
        """Load README and examples from filesystem."""
        docs = {}

        # Load README
        readme_path = Path(__file__).parent.parent.parent / "README.md"
        if readme_path.exists():
            docs["readme"] = readme_path.read_text()

        # Load examples
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        if examples_dir.exists():
            docs["examples"] = {}
            for yaml_file in examples_dir.rglob("*.yaml"):
                if "pipeline" in yaml_file.name.lower():
                    docs["examples"][yaml_file.name] = yaml_file.read_text()

        return docs

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP request from Q CLI."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            client_version = params.get("protocolVersion", "2024-11-05")
            return {
                "result": {
                    "protocolVersion": client_version,
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": {"name": "smus-cli", "version": "1.0.0"},
                },
                "jsonrpc": "2.0",
                "id": request_id,
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            return {"result": self.list_tools(), "jsonrpc": "2.0", "id": request_id}
        elif method == "tools/call":
            return {
                "result": self.call_tool(params),
                "jsonrpc": "2.0",
                "id": request_id,
            }
        elif method == "resources/list":
            return {"result": self.list_resources(), "jsonrpc": "2.0", "id": request_id}
        elif method == "resources/read":
            return {
                "result": self.read_resource(params),
                "jsonrpc": "2.0",
                "id": request_id,
            }
        else:
            return {
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "jsonrpc": "2.0",
                "id": request_id,
            }

    def list_tools(self) -> Dict[str, Any]:
        """List available SMUS tools."""
        return {
            "tools": [
                {
                    "name": "query_smus_kb",
                    "description": "Search SMUS CLI documentation and examples",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Question about SMUS CLI, pipelines, or deployment",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 5,
                            },
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "get_pipeline_example",
                    "description": "Get example pipeline.yaml manifest for specific use case",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "use_case": {
                                "type": "string",
                                "description": "Use case: notebooks, etl, ml-training, analytics",
                                "enum": [
                                    "notebooks",
                                    "etl",
                                    "ml-training",
                                    "analytics",
                                ],
                            }
                        },
                        "required": ["use_case"],
                    },
                },
                {
                    "name": "validate_pipeline",
                    "description": "Validate pipeline.yaml against the official SMUS pipeline manifest schema",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "yaml_content": {
                                "type": "string",
                                "description": "Pipeline YAML content to validate",
                            }
                        },
                        "required": ["yaml_content"],
                    },
                },
            ]
        }

    def call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute SMUS tool."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "query_smus_kb":
            return self.query_kb(arguments)
        elif tool_name == "get_pipeline_example":
            return self.get_example(arguments)
        elif tool_name == "validate_pipeline":
            return self.validate_pipeline(arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def query_kb(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search local docs."""
        query = args.get("query", "").lower()
        max_results = args.get("max_results", 5)

        results = []

        # Search README
        if "readme" in self.docs and query in self.docs["readme"].lower():
            results.append(
                f"From README:\n{self._extract_relevant(self.docs['readme'], query)}"
            )

        # Search examples
        for name, content in self.docs.get("examples", {}).items():
            if query in content.lower() or query in name.lower():
                results.append(f"From {name}:\n{content[:500]}...")
                if len(results) >= max_results:
                    break

        if not results:
            results.append(
                "No results found. Try: 'pipeline', 'bundle', 'workflow', 'deploy', 'targets'"
            )

        response_text = f"Search results for '{query}':\n\n" + "\n\n".join(
            results[:max_results]
        )
        return {"content": [{"type": "text", "text": response_text}]}

    def _extract_relevant(self, text, query, context=200):
        """Extract relevant section around query."""
        idx = text.lower().find(query)
        if idx == -1:
            return text[:500]

        start = max(0, idx - context)
        end = min(len(text), idx + len(query) + context)
        return "..." + text[start:end] + "..."

    def get_example(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get pipeline example for use case."""
        use_case = args.get("use_case", "notebooks")

        examples = {
            "notebooks": """
# Example: Notebook Deployment Pipeline
pipelineName: NotebookPipeline

targets:
  dev:
    stage: DEV
    default: true
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION}
    project:
      name: dev-project
    bundle_target_configuration:
      storage:
        - name: notebooks
          connectionName: default.s3_shared
          targetDirectory: notebooks

  test:
    stage: TEST
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION}
    project:
      name: test-project
    initialization:
      project:
        create: true
        profileName: 'All capabilities'

bundle:
  storage:
    - name: notebooks
      connectionName: default.s3_shared
      include: ['notebooks/*.ipynb']
      exclude: ['.ipynb_checkpoints/']

workflows:
  - workflowName: execute_notebooks
    connectionName: project.workflow_serverless
    engine: airflow-serverless
    triggerPostDeployment: false
""",
            "etl": """
# Example: ETL Pipeline
pipelineName: ETLPipeline

targets:
  dev:
    stage: DEV
    default: true
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION}
    project:
      name: dev-etl

bundle:
  storage:
    - name: scripts
      connectionName: default.s3_shared
      include: ['scripts/*.py', 'sql/*.sql']

workflows:
  - workflowName: etl_workflow
    connectionName: project.workflow_mwaa
    engine: MWAA
""",
            "ml-training": """
# Example: ML Training Pipeline
pipelineName: MLTrainingPipeline

targets:
  dev:
    stage: DEV
    default: true
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION}
    project:
      name: ml-dev

bundle:
  storage:
    - name: training
      connectionName: default.s3_shared
      include: ['training/*.py', 'models/']
""",
            "analytics": """
# Example: Analytics Pipeline
pipelineName: AnalyticsPipeline

targets:
  dev:
    stage: DEV
    default: true
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION}
    project:
      name: analytics-dev

bundle:
  storage:
    - name: queries
      connectionName: default.s3_shared
      include: ['queries/*.sql']

workflows:
  - workflowName: analytics_workflow
    connectionName: project.athena
    engine: athena
""",
        }

        example = examples.get(use_case, examples["notebooks"])

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"SMUS Pipeline Example for {use_case}:\n\n{example}",
                }
            ]
        }

    def validate_pipeline(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate pipeline YAML using official manifest schema."""
        yaml_content = args.get("yaml_content")

        try:
            import yaml

            from .pipeline.validation import load_schema, validate_manifest_schema

            # Parse YAML
            try:
                data = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                return {
                    "content": [
                        {"type": "text", "text": f"❌ YAML Syntax Error:\n{str(e)}"}
                    ]
                }

            # Validate against official schema
            schema = load_schema()
            is_valid, errors = validate_manifest_schema(data, schema)

            if not is_valid:
                error_text = "❌ Schema Validation Failed:\n\n"
                for i, error in enumerate(errors, 1):
                    error_text += f"{i}. {error}\n"
                return {"content": [{"type": "text", "text": error_text}]}

            # Success with details
            success_text = "✅ Pipeline is valid!\n\n"
            success_text += f"Pipeline: {data.get('pipelineName', 'N/A')}\n"
            success_text += f"Targets: {', '.join(data.get('targets', {}).keys())}\n"
            success_text += (
                f"Bundle sections: {len(data.get('bundle', {}).get('storage', []))}\n"
            )

            if "workflows" in data:
                success_text += f"Workflows: {len(data.get('workflows', []))}\n"

            success_text += "\nValidated against pipeline-manifest-schema.yaml"

            return {"content": [{"type": "text", "text": success_text}]}

        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"❌ Validation error: {str(e)}"}]
            }

    def list_resources(self) -> Dict[str, Any]:
        """List available SMUS resources."""
        return {
            "resources": [
                {
                    "uri": "smus://docs/pipeline-manifest",
                    "name": "Pipeline Manifest Documentation",
                    "description": "Complete pipeline.yaml schema and examples",
                    "mimeType": "text/markdown",
                },
                {
                    "uri": "smus://docs/getting-started",
                    "name": "Getting Started Guide",
                    "description": "Quick start guide for SMUS CLI",
                    "mimeType": "text/markdown",
                },
            ]
        }

    def read_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read SMUS resource."""
        uri = params.get("uri")

        if uri == "smus://docs/pipeline-manifest":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "text/markdown",
                        "text": "Pipeline manifest documentation...",
                    }
                ]
            }

        return {"error": f"Unknown resource: {uri}"}


def main():
    """Run MCP server."""

    def log(msg):
        print(f"[MCP] {msg}", file=sys.stderr, flush=True)

    log("Starting SMUS MCP server")
    server = SMUSMCPServer()
    log("Server initialized")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                log("EOF received, exiting")
                break

            log(f"Received: {line.strip()[:100]}")
            request = json.loads(line)
            response = server.handle_request(request)

            if response is not None:
                response_str = json.dumps(response)
                log(f"Sending: {response_str[:100]}")
                print(response_str, flush=True)
            else:
                log("No response needed (notification)")
        except json.JSONDecodeError as e:
            log(f"JSON decode error: {e}")
            continue
        except Exception as e:
            log(f"Error: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
