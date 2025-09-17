"""Unit tests for run command."""

import tempfile
import pytest
import re
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from smus_cicd.cli import app


def strip_ansi_codes(text):
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class TestRunCommand:
    """Test cases for run command functionality."""

    def create_test_manifest(self):
        """Create a test manifest file."""
        manifest_content = """
pipelineName: TestPipeline
targets:
  dev:
    domain:
      name: test-domain
      region: us-east-1
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

    def test_run_missing_workflow_parameter(self):
        """Test run command fails when --workflow is missing."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app, ["run", "--pipeline", manifest_file, "--command", "dags list"]
            )
            assert result.exit_code == 1
            # Error messages go to stderr in typer
            assert (
                "Error: --workflow parameter is required" in result.stderr
                or "workflow" in result.stderr
            )
        finally:
            import os

            os.unlink(manifest_file)

    def test_run_missing_command_parameter(self):
        """Test run command fails when --command is missing."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app, ["run", "--pipeline", manifest_file, "--workflow", "test_workflow"]
            )
            assert result.exit_code == 1
            # Error messages go to stderr in typer
            assert (
                "Error: --command parameter is required" in result.stderr
                or "command" in result.stderr
            )
        finally:
            import os

            os.unlink(manifest_file)

    def test_run_invalid_target(self):
        """Test run command fails with invalid target."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app,
                [
                    "run",
                    "--pipeline",
                    manifest_file,
                    "--workflow",
                    "test_workflow",
                    "--command",
                    "dags list",
                    "--targets",
                    "invalid_target",
                ],
            )
            assert result.exit_code == 1
            # Error messages go to stderr in typer
            assert (
                "Target 'invalid_target' not found" in result.stderr
                or "invalid_target" in result.stderr
            )
        finally:
            import os

            os.unlink(manifest_file)

    @patch("smus_cicd.commands.run.PipelineManifest.from_file")
    @patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
    @patch("smus_cicd.commands.run.load_config")
    @patch("smus_cicd.commands.run.get_datazone_project_info")
    @patch("smus_cicd.helpers.mwaa.run_airflow_command")
    def test_run_successful_command(
        self,
        mock_run_airflow,
        mock_get_project,
        mock_config,
        mock_mwaa_health,
        mock_manifest,
    ):
        """Test successful run command execution."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        # Mock responses
        mock_config.return_value = {}
        mock_mwaa_health.return_value = True  # Mock MWAA as healthy

        # Mock manifest
        mock_target = MagicMock()
        mock_target.project.name = "test-project"
        mock_manifest_obj = MagicMock()
        mock_manifest_obj.targets = {"dev": mock_target}
        mock_manifest_obj.get_target_config.return_value = mock_target
        mock_manifest.return_value = mock_manifest_obj

        mock_get_project.return_value = {
            "project_id": "test-project-id",
            "connections": {
                "project.workflow_mwaa": {
                    "type": "WORKFLOWS_MWAA",
                    "environmentName": "test-env",
                }
            },
        }
        mock_run_airflow.return_value = {
            "success": True,
            "stdout": "dag1\ndag2\ndag3",
            "stderr": "",
            "status_code": 200,
        }

        try:
            result = runner.invoke(
                app,
                [
                    "run",
                    "--pipeline",
                    manifest_file,
                    "--workflow",
                    "test_workflow",
                    "--command",
                    "dags list",
                    "--targets",
                    "dev",
                ],
            )

            assert result.exit_code == 0
            assert "Command executed successfully" in result.stdout
            assert "dag1" in result.stdout
            mock_run_airflow.assert_called_once()
        finally:
            import os

            os.unlink(manifest_file)

    @patch("smus_cicd.commands.run.PipelineManifest.from_file")
    @patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
    @patch("smus_cicd.commands.run.load_config")
    @patch("smus_cicd.commands.run.get_datazone_project_info")
    @patch("smus_cicd.helpers.mwaa.run_airflow_command")
    def test_run_json_output(
        self,
        mock_run_airflow,
        mock_get_project,
        mock_config,
        mock_mwaa_health,
        mock_manifest,
    ):
        """Test run command with JSON output."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        # Mock responses
        mock_config.return_value = {}
        mock_mwaa_health.return_value = True  # Mock MWAA as healthy

        # Mock manifest
        mock_target = MagicMock()
        mock_target.project.name = "test-project"
        mock_manifest_obj = MagicMock()
        mock_manifest_obj.targets = {"dev": mock_target}
        mock_manifest_obj.get_target_config.return_value = mock_target
        mock_manifest.return_value = mock_manifest_obj

        mock_get_project.return_value = {
            "project_id": "test-project-id",
            "connections": {
                "project.workflow_mwaa": {
                    "type": "WORKFLOWS_MWAA",
                    "environmentName": "test-env",
                }
            },
        }
        mock_run_airflow.return_value = {
            "success": True,
            "stdout": "test output",
            "stderr": "",
            "status_code": 200,
        }

        try:
            result = runner.invoke(
                app,
                [
                    "run",
                    "--pipeline",
                    manifest_file,
                    "--workflow",
                    "test_workflow",
                    "--command",
                    "dags list",
                    "--targets",
                    "dev",
                    "--output",
                    "JSON",
                ],
            )

            assert result.exit_code == 0
            # Should be valid JSON - extract JSON part from stdout
            import json

            stdout_lines = result.stdout.strip().split("\n")
            # Find the JSON part (starts with '{')
            json_start = None
            for i, line in enumerate(stdout_lines):
                if line.strip().startswith("{"):
                    json_start = i
                    break

            assert json_start is not None, "No JSON found in output"
            json_text = "\n".join(stdout_lines[json_start:])
            output_data = json.loads(json_text)
            assert "workflow" in output_data
            assert "command" in output_data
            assert "results" in output_data
        finally:
            import os

            os.unlink(manifest_file)

    @patch("smus_cicd.commands.run.PipelineManifest.from_file")
    @patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
    @patch("smus_cicd.commands.run.load_config")
    @patch("smus_cicd.commands.run.get_datazone_project_info")
    def test_run_project_info_failure(
        self, mock_get_project, mock_config, mock_mwaa_health, mock_manifest
    ):
        """Test run command when project info fails."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        mock_config.return_value = {}
        mock_mwaa_health.return_value = False  # Mock MWAA as unhealthy

        # Mock manifest
        mock_target = MagicMock()
        mock_target.project.name = "test-project"
        mock_manifest_obj = MagicMock()
        mock_manifest_obj.targets = {"dev": mock_target}
        mock_manifest_obj.get_target_config.return_value = mock_target
        mock_manifest.return_value = mock_manifest_obj

        mock_get_project.return_value = {"success": False, "error": "Project not found"}

        try:
            result = runner.invoke(
                app,
                [
                    "run",
                    "--pipeline",
                    manifest_file,
                    "--workflow",
                    "test_workflow",
                    "--command",
                    "dags list",
                    "--targets",
                    "dev",
                ],
            )

            assert result.exit_code == 1  # Command fails with MWAA health check
            assert "No healthy MWAA environments found" in result.stdout
        finally:
            import os

            os.unlink(manifest_file)

    def test_run_help_message(self):
        """Test run command help message."""
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--help"])

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "Run Airflow CLI commands" in clean_output
        assert "--workflow" in clean_output
        assert "--command" in clean_output
        assert "--targets" in clean_output
        assert "--output" in clean_output
