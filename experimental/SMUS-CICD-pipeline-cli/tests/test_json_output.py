"""Unit tests for --output JSON functionality across all commands."""

import tempfile
import json
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from smus_cicd.cli import app


class TestJSONOutput:
    """Test cases for JSON output functionality."""

    def create_test_manifest(self):
        """Create a test manifest file."""
        manifest_content = """
pipelineName: TestPipeline
stages:
  dev:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: DEV
    project:
      name: test-project
      create: false
workflows:
  - workflowName: test_workflow
    connectionName: project.workflow_mwaa
"""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        f.write(manifest_content)
        f.flush()
        return f.name

    def test_describe_json_output(self):
        """Test describe command with JSON output."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app, ["describe", "--pipeline", manifest_file, "--output", "JSON"]
            )

            assert result.exit_code == 0

            # Should be valid JSON
            output_data = json.loads(result.stdout)
            assert "bundle" in output_data
            assert "targets" in output_data
            assert output_data["bundle"] == "TestPipeline"
            assert "domain" in output_data["targets"]["dev"]
        finally:
            import os
            os.unlink(manifest_file)

    @patch("smus_cicd.commands.run.ApplicationManifest.from_file")
    @patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
    @patch("smus_cicd.commands.run.load_config")
    @patch("smus_cicd.commands.run.get_datazone_project_info")
    @patch("smus_cicd.helpers.mwaa.run_airflow_command")
    def test_run_json_output_with_parsed_data(
        self,
        mock_run_airflow,
        mock_get_project,
        mock_config,
        mock_mwaa_health,
        mock_manifest,
    ):
        """Test run command JSON output with parsed Airflow data."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        # Mock responses
        mock_config.return_value = {}
        mock_mwaa_health.return_value = True
        mock_get_project.return_value = {
            "project_id": "test-project-id",
            "connections": {
                "project.workflow_mwaa": {
                    "type": "WORKFLOWS_MWAA",
                    "environmentName": "test-env",
                }
            },
        }

        # Mock manifest
        mock_target = MagicMock()
        mock_target.project.name = "test-project"
        mock_target.domain.name = "test-domain"
        mock_target.domain.region = "us-east-1"
        mock_manifest_obj = MagicMock()
        mock_manifest_obj.stages = {"dev": mock_target}
        mock_manifest_obj.get_target_config.return_value = mock_target
        mock_manifest.return_value = mock_manifest_obj

        # Mock Airflow response
        mock_run_airflow.return_value = {
            "success": True,
            "stdout": "dag_id | fileloc | owners | is_paused\n=======+=========+========+==========\ntest_dag | /test.py | airflow | False",
        }
