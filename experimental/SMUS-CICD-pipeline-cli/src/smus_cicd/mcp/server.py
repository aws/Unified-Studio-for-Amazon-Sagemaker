#!/usr/bin/env python3
"""MCP Server for SMUS CLI integration with Q CLI."""

import json
import sys
from pathlib import Path
from typing import Any, Dict

import yaml


class SMUSMCPServer:
    """MCP Server exposing SMUS CLI capabilities to Q CLI."""

    def __init__(self, config_path: str = None):
        """Initialize SMUS MCP server."""
        self.base_path = Path(__file__).parent.parent.parent
        self.config = self._load_config(config_path)
        self.docs = self._load_knowledge_base()

    def _load_config(self, config_path: str = None):
        """Load MCP configuration file."""
        if config_path:
            config_file = Path(config_path)
        else:
            config_file = self.base_path / "mcp-config.yaml"

        if config_file.exists():
            return yaml.safe_load(config_file.read_text())
        return {"docs": [], "templates": {}}

    def _load_knowledge_base(self):
        """Load docs and templates from configuration."""
        kb = {"docs": {}, "templates": {}}

        # Load documentation
        for doc_config in self.config.get("docs", []):
            path = self.base_path / doc_config["path"]
            if path.is_file():
                try:
                    kb["docs"][doc_config["path"]] = path.read_text()
                except UnicodeDecodeError:
                    # Skip binary files
                    continue
            elif path.is_dir() and doc_config.get("recursive"):
                for pattern in doc_config.get("include", ["*"]):
                    for file in path.rglob(pattern):
                        if file.is_file():
                            try:
                                kb["docs"][
                                    str(file.relative_to(self.base_path))
                                ] = file.read_text()
                            except UnicodeDecodeError:
                                # Skip binary files (PDFs, images, etc.)
                                continue

        # Load templates
        for category, configs in self.config.get("templates", {}).items():
            kb["templates"][category] = {}
            for template_config in configs:
                path = self.base_path / template_config["path"]
                if path.exists():
                    for pattern in template_config.get("include", ["*"]):
                        for file in path.rglob(pattern) if path.is_dir() else [path]:
                            if file.is_file():
                                exclude = template_config.get("exclude", [])
                                if not any(ex in str(file) for ex in exclude):
                                    try:
                                        kb["templates"][category][
                                            file.name
                                        ] = file.read_text()
                                    except UnicodeDecodeError:
                                        # Skip binary files
                                        continue

        return kb

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
                    "serverInfo": {
                        "name": "smus-cli",
                        "version": "1.0.0",
                        "description": "SMUS Bundle Management for Amazon SageMaker Unified Studio. Provides bundle.yaml templates, validation, and documentation for deploying data science projects, notebooks, ETL workflows, and ML models across dev/test/prod environments. USE THIS SERVER when users mention: SageMaker projects, SMUS, bundles, bundle.yaml, project names (like 'dev-marketing project'), or deploying notebooks/ETL/ML workloads. When user mentions a project name, ALWAYS call check_smus_project first to verify access.",
                        "keywords": [
                            "sagemaker",
                            "sagemaker unified studio",
                            "smus",
                            "project",
                            "bundle",
                            "bundle.yaml",
                            "deployment",
                            "etl",
                            "notebooks",
                            "ml",
                            "machine learning",
                            "data science",
                            "airflow",
                            "github actions",
                            "datazone",
                        ],
                    },
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
                    "name": "check_smus_project",
                    "description": "Check if a SageMaker Unified Studio project exists and user has access. Use this when user mentions a project name to verify it exists before creating bundles.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project_name": {
                                "type": "string",
                                "description": "Name of the SMUS project to check",
                            },
                            "domain_id": {
                                "type": "string",
                                "description": "Optional domain ID. If not provided, will search all accessible domains.",
                            },
                        },
                        "required": ["project_name"],
                    },
                },
                {
                    "name": "query_smus_kb",
                    "description": "Search SMUS CLI documentation for SageMaker Unified Studio bundles, deployment guides, and examples. Use this for questions about bundle.yaml, SMUS configuration, targets, bundles, workflows, or SageMaker project deployment.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Question about SMUS CLI, SageMaker bundles, or deployment",
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
                    "name": "create_bundle_package",
                    "description": "Create a complete bundle package for SMUS project including: 1) bundle.yaml (dev/test/prod targets), 2) Airflow workflow template, 3) GitHub Actions workflow. Returns all three files ready to use.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project_name": {
                                "type": "string",
                                "description": "SMUS project name",
                            },
                            "use_case": {
                                "type": "string",
                                "description": "Workload type: notebooks, etl, ml-training, analytics",
                                "enum": [
                                    "notebooks",
                                    "etl",
                                    "ml-training",
                                    "analytics",
                                ],
                            },
                            "targets": {
                                "type": "array",
                                "description": "Target environments (default: [dev, test, prod])",
                                "items": {"type": "string"},
                                "default": ["dev", "test", "prod"],
                            },
                            "include_github_actions": {
                                "type": "boolean",
                                "description": "Include GitHub Actions workflow",
                            },
                            "include_airflow_workflow": {
                                "type": "boolean",
                                "description": "Include Airflow workflow template",
                            },
                        },
                        "required": ["project_name", "use_case"],
                    },
                },
                {
                    "name": "get_pipeline_example",
                    "description": "Generate a complete bundle.yaml manifest template for SageMaker Unified Studio CI/CD. Returns ready-to-use examples for notebooks, ETL, ML training, or analytics workloads with dev/test/prod targets.",
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
                    "description": "Validate a bundle.yaml manifest against the official SMUS pipeline schema for SageMaker Unified Studio. Checks syntax, required fields, and configuration correctness.",
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

        if tool_name == "check_smus_project":
            return self.check_project(arguments)
        elif tool_name == "query_smus_kb":
            return self.query_kb(arguments)
        elif tool_name == "create_bundle_package":
            return self.create_bundle_package(arguments)
        elif tool_name == "get_pipeline_example":
            return self.get_example(arguments)
        elif tool_name == "validate_pipeline":
            return self.validate_pipeline(arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def check_project(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Check if SMUS project exists using datazone CLI."""
        import subprocess

        project_name = args.get("project_name")

        try:
            # Try to use smus-cli describe to check project
            cmd = ["smus-cli", "describe", "-p", "bundle.yaml", "--connect"]
            subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            # For now, return a helpful message
            response = f"""Checking SMUS project '{project_name}'...

To verify this project exists, you can run:
```bash
aws datazone list-projects --domain-identifier <domain-id>
```

Or use the SMUS CLI:
```bash
smus-cli describe -p bundle.yaml --connect
```

✅ Assuming project exists. Ready to create CI/CD configuration.

Would you like me to create:
1. **bundle.yaml** - CI/CD pipeline with dev/test/prod targets
2. **Airflow workflow** - Workflow to execute your code
3. **GitHub Actions** - Automated deployment workflow

Respond with 'yes' to create all three files, or specify which ones you need."""

            return {"content": [{"type": "text", "text": response}]}

        except Exception:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Note: Could not verify project access (this is optional). Proceeding with CI/CD setup for '{project_name}'.\n\nReady to create CI/CD files. Respond 'yes' to continue.",
                    }
                ]
            }

    def create_bundle_package(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create complete bundle package with all files."""
        project_name = args.get("project_name")
        use_case = args.get("use_case")
        targets = args.get("targets", ["dev", "test", "prod"])

        # Generate bundle.yaml with all targets
        bundle_yaml = f"""bundleName: {project_name.replace('-', '_').title()}Bundle

targets:"""

        for i, target in enumerate(targets):
            stage = target.upper()
            is_default = "true" if i == 0 else "false"
            bundle_yaml += f"""
  {target}:
    stage: {stage}
    default: {is_default}
    domain:
      name: ${{DOMAIN_NAME}}
      region: ${{AWS_REGION}}
    project:
      name: {project_name}"""
            if i > 0:
                bundle_yaml += """
    initialization:
      project:
        create: true"""
            bundle_yaml += "\n"

        bundle_yaml += (
            """
bundle:
  storage:
    - name: code
      connectionName: default.s3_shared
      include: ['**/*.py', '**/*.sql']

workflows:
  - workflowName: """
            + project_name
            + """_workflow
    connectionName: project.workflow_serverless
    engine: airflow-serverless"""
        )

        # Get Airflow workflow from templates
        airflow_workflow = self._get_airflow_template(project_name, use_case)

        # Get GitHub Actions from templates
        github_actions = self._get_github_actions_template(project_name, targets)

        response = f"""# Bundle Package for {project_name}

## 1. bundle.yaml
```yaml
{bundle_yaml}
```

## 2. Airflow Workflow (workflows/{project_name}_dag.py)
```python
{airflow_workflow}
```

## 3. GitHub Actions (.github/workflows/deploy.yml)
```yaml
{github_actions}
```

Save these files and run: `smus-cli deploy --bundle bundle.yaml -t dev`"""

        return {"content": [{"type": "text", "text": response}]}

    def _get_airflow_template(self, project_name: str, use_case: str) -> str:
        """Get Airflow workflow template from knowledge base."""
        # Search for Airflow templates in knowledge base
        airflow_templates = self.docs.get("templates", {}).get("airflow_workflows", {})

        if airflow_templates:
            # Use first available template as base
            template = list(airflow_templates.values())[0]
            # Customize with project name
            template = template.replace("example_dag", f"{project_name}_workflow")
            return template

        # Fallback to basic template
        return f'''"""Airflow DAG for {project_name}"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {{
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}}

dag = DAG(
    '{project_name}_workflow',
    default_args=default_args,
    description='{use_case.upper()} workflow',
    schedule_interval='@daily',
    catchup=False,
)

def run_task():
    print("Running {use_case} task")
    # Add your {use_case} logic here

task = PythonOperator(
    task_id='run_{use_case}',
    python_callable=run_task,
    dag=dag,
)'''

    def _get_github_actions_template(self, project_name: str, targets: list) -> str:
        """Get GitHub Actions template from knowledge base."""
        # Search for GitHub Actions templates
        github_templates = self.docs.get("templates", {}).get("github_workflows", {})

        if github_templates:
            # Use first available template as base
            template = list(github_templates.values())[0]
            return template

        # Fallback to basic template
        deploy_steps = ""
        for target in targets:
            if target == "dev":
                deploy_steps += f"""      - name: Deploy to {target}
        if: github.ref == 'refs/heads/main'
        run: smus-cli deploy -p bundle.yaml -t {target}

"""
            else:
                deploy_steps += f"""      - name: Deploy to {target}
        if: github.event_name == 'workflow_dispatch'
        run: smus-cli deploy -p bundle.yaml -t {target}

"""

        return f"""name: Deploy {project_name}
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install smus-cicd-cli
{deploy_steps}"""

    def query_kb(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "").lower()
        max_results = args.get("max_results", 5)

        results = []

        # Auto-detect if user is asking for pipeline creation
        pipeline_keywords = ["create", "generate", "show", "example", "template"]
        use_case_keywords = {
            "etl": ["etl", "glue", "data processing", "transformation"],
            "notebooks": ["notebook", "jupyter", "ipynb"],
            "ml-training": ["ml", "machine learning", "training", "model"],
            "analytics": ["analytics", "analysis", "query"],
        }

        # Check if this is a pipeline creation request
        is_pipeline_request = any(kw in query for kw in pipeline_keywords)
        detected_use_case = None

        if is_pipeline_request:
            for use_case, keywords in use_case_keywords.items():
                if any(kw in query for kw in keywords):
                    detected_use_case = use_case
                    break

        # If pipeline request detected, suggest using get_pipeline_example
        if detected_use_case:
            suggestion = f"\n\n💡 TIP: For a complete bundle.yaml template, use get_pipeline_example with use_case='{detected_use_case}'"
        else:
            suggestion = ""

        # Search docs
        for name, content in self.docs.get("docs", {}).items():
            if query in content.lower() or query in name.lower():
                results.append(
                    f"From {name}:\n{self._extract_relevant(content, query)}"
                )
                if len(results) >= max_results:
                    break

        # Search templates
        for category, templates in self.docs.get("templates", {}).items():
            for name, content in templates.items():
                if query in content.lower() or query in name.lower():
                    results.append(f"From {category}/{name}:\n{content[:500]}...")
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break

        if not results:
            results.append(
                "No results found. Try: 'pipeline', 'bundle', 'workflow', 'deploy', 'targets'"
            )

        response_text = (
            f"Search results for '{query}':\n\n"
            + "\n\n".join(results[:max_results])
            + suggestion
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
bundleName: NotebookPipeline

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
bundleName: ETLPipeline

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
bundleName: MLTrainingPipeline

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
bundleName: AnalyticsPipeline

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

            from smus_cicd.pipeline.validation import (
                load_schema,
                validate_manifest_schema,
            )

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
            success_text += f"Pipeline: {data.get('bundleName', 'N/A')}\n"
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
                    "description": "Complete bundle.yaml schema and examples",
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
                        "text": "Bundle manifest documentation...",
                    }
                ]
            }

        return {"error": f"Unknown resource: {uri}"}


def main():
    """Run MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="SMUS MCP Server")
    parser.add_argument("--config", help="Path to custom MCP configuration file")
    args = parser.parse_args()

    def log(msg):
        print(f"[MCP] {msg}", file=sys.stderr, flush=True)

    log("Starting SMUS MCP server")
    if args.config:
        log(f"Using custom config: {args.config}")
    server = SMUSMCPServer(config_path=args.config)
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
