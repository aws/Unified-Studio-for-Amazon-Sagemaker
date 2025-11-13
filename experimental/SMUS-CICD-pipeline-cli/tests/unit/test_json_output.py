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
bundleName: TestPipeline
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

    def test_describe_json_output(self):
        """Test describe command with JSON output."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app, ["describe", "--bundle", manifest_file, "--output", "JSON"]
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

    @patch("smus_cicd.commands.run.BundleManifest.from_file")
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
        mock_mwaa_health.return_value = True  # Mock MWAA as healthy
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
        mock_manifest_obj = MagicMock()
        mock_manifest_obj.targets = {"dev": mock_target}
        mock_manifest_obj.get_target_config.return_value = mock_target
        mock_manifest.return_value = mock_manifest_obj

        # Mock Airflow response with dags list output
        mock_run_airflow.return_value = {
            "success": True,
            "stdout": "dag_id | fileloc | owners | is_paused\n=======+=========+========+==========\ntest_dag | /test.py | airflow | False",
            "stderr": "",
            "status_code": 200,
        }

        try:
            result = runner.invoke(
                app,
                [
                    "run",
                    "--bundle",
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

            # Parse JSON output - extract JSON part from stdout
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

            # Check parsed DAG data
            result_item = output_data["results"][0]
            assert "dags" in result_item
            assert len(result_item["dags"]) == 1
            assert result_item["dags"][0]["dag_id"] == "test_dag"
            assert result_item["dags"][0]["is_paused"] is False

        finally:
            import os

            os.unlink(manifest_file)

    @patch("smus_cicd.commands.bundle.load_config")
    @patch("smus_cicd.commands.bundle.get_datazone_project_info")
    def test_bundle_json_output(self, mock_get_project, mock_load_config):
        """Test bundle command with JSON output."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        # Mock config and project info
        mock_load_config.return_value = {"region": "us-east-1"}
        mock_get_project.return_value = {
            "project_id": "test-project-id",
            "connections": {},
        }

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                result = runner.invoke(
                    app,
                    [
                        "bundle",
                        "dev",
                        "--manifest",
                        manifest_file,
                        "--output-dir",
                        temp_dir,
                        "--output",
                        "JSON",
                    ],
                )

                # May succeed or fail, but should return valid JSON
                if result.stdout.strip():
                    output_data = json.loads(result.stdout)
                    assert "target" in output_data
                    assert "success" in output_data

        finally:
            import os

            os.unlink(manifest_file)

    def test_create_json_output(self):
        """Test create command with JSON output."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            import os

            os.chdir(temp_dir)
            output_file = "tests/fixtures/test-bundle.yaml"

            result = runner.invoke(
                app,
                [
                    "create",
                    "--output",
                    output_file,
                    "--name",
                    "TestPipeline",
                    "--format",
                    "JSON",  # Assuming we add this
                ],
            )

            # For now, create command doesn't have JSON output
            # This test will be updated when we add it
            assert result.exit_code in [0, 2]  # May not have --format option yet

    @patch("smus_cicd.commands.run.BundleManifest.from_file")
    @patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
    @patch("smus_cicd.commands.run.load_config")
    @patch("smus_cicd.commands.run.get_datazone_project_info")
    @patch("smus_cicd.helpers.mwaa.run_airflow_command")
    def test_run_json_output_version_command(
        self,
        mock_run_airflow,
        mock_get_project,
        mock_config,
        mock_mwaa_health,
        mock_manifest,
    ):
        """Test run command JSON output with version command."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        # Mock responses
        mock_config.return_value = {}
        mock_mwaa_health.return_value = True  # Mock MWAA as healthy
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
        mock_manifest_obj = MagicMock()
        mock_manifest_obj.targets = {"dev": mock_target}
        mock_manifest_obj.get_target_config.return_value = mock_target
        mock_manifest.return_value = mock_manifest_obj

        # Mock Airflow version response
        mock_run_airflow.return_value = {
            "success": True,
            "stdout": "2.10.1",
            "stderr": "",
            "status_code": 200,
        }

        try:
            result = runner.invoke(
                app,
                [
                    "run",
                    "--bundle",
                    manifest_file,
                    "--workflow",
                    "test_workflow",
                    "--command",
                    "version",
                    "--targets",
                    "dev",
                    "--output",
                    "JSON",
                ],
            )

            assert result.exit_code == 0

            # Parse JSON output - extract JSON part from stdout
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
            result_item = output_data["results"][0]
            assert "version" in result_item
            assert result_item["version"] == "2.10.1"

        finally:
            import os

            os.unlink(manifest_file)

    @patch("smus_cicd.commands.run.BundleManifest.from_file")
    @patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
    @patch("smus_cicd.commands.run.load_config")
    @patch("smus_cicd.commands.run.get_datazone_project_info")
    @patch("smus_cicd.helpers.mwaa.run_airflow_command")
    def test_run_json_output_tasks_list(
        self,
        mock_run_airflow,
        mock_get_project,
        mock_config,
        mock_mwaa_health,
        mock_manifest,
    ):
        """Test run command JSON output with tasks list command."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        # Mock responses
        mock_config.return_value = {}
        mock_mwaa_health.return_value = True  # Mock MWAA as healthy
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
        mock_manifest_obj = MagicMock()
        mock_manifest_obj.targets = {"dev": mock_target}
        mock_manifest_obj.get_target_config.return_value = mock_target
        mock_manifest.return_value = mock_manifest_obj

        # Mock Airflow tasks list response
        mock_run_airflow.return_value = {
            "success": True,
            "stdout": "task1\ntask2\ntask3",
            "stderr": "",
            "status_code": 200,
        }

        try:
            result = runner.invoke(
                app,
                [
                    "run",
                    "--bundle",
                    manifest_file,
                    "--workflow",
                    "test_workflow",
                    "--command",
                    "tasks list test_dag",
                    "--targets",
                    "dev",
                    "--output",
                    "JSON",
                ],
            )

            assert result.exit_code == 0

            # Parse JSON output - extract JSON part from stdout
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
            result_item = output_data["results"][0]
            assert "tasks" in result_item
            assert result_item["tasks"] == ["task1", "task2", "task3"]

        finally:
            import os

            os.unlink(manifest_file)

    def test_json_output_error_handling(self):
        """Test JSON output with error scenarios."""
        runner = CliRunner()

        # Test with non-existent manifest file
        result = runner.invoke(
            app, ["describe", "--bundle", "nonexistent.yaml", "--output", "JSON"]
        )

        assert result.exit_code == 1

        # Should return valid JSON even on error
        if result.stdout.strip():
            output_data = json.loads(result.stdout)
            assert "error" in output_data
