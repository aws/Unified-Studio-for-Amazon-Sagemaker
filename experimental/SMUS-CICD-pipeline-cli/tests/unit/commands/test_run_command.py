"""Unit tests for run command exit codes."""

import pytest
import typer
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from smus_cicd.cli import app


class TestRunCommandExitCodes:
    """Test exit codes for run command failure scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
    @patch("smus_cicd.commands.run.load_config")
    @patch("smus_cicd.commands.run.get_datazone_project_info")
    @patch("smus_cicd.commands.run.PipelineManifest.from_file")
    def test_no_workflow_connections_returns_exit_code_1(
        self, mock_manifest, mock_project_info, mock_config, mock_mwaa_health
    ):
        """Test that run command returns exit code 1 when no workflow connections found."""
        # Mock manifest
        mock_target = MagicMock()
        mock_target.project.name = "test-project"

        mock_manifest_obj = MagicMock()
        mock_manifest_obj.targets = {"test": mock_target}
        mock_manifest_obj.domain.region = "us-east-1"
        mock_manifest_obj.domain.name = "test-domain"
        mock_manifest_obj.pipeline_name = "test-pipeline"
        mock_manifest_obj.get_target_config.return_value = mock_target

        mock_manifest.return_value = mock_manifest_obj

        # Mock config and MWAA health check to fail
        mock_config.return_value = {}
        mock_mwaa_health.return_value = False

        # Mock project info with no workflow connections
        mock_project_info.return_value = {
            "project_id": "project-123",
            "connections": {},  # No connections
        }

        # Run command
        result = self.runner.invoke(
            app,
            [
                "run",
                "--pipeline",
                "test.yaml",
                "--targets",
                "test",
                "--workflow",
                "test_dag",
                "--command",
                "dags list",
            ],
        )

        # Verify exit code 1
        assert result.exit_code == 1
        assert "No healthy MWAA environments found" in result.stdout

    @patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
    @patch("smus_cicd.commands.run.load_config")
    @patch("smus_cicd.commands.run.get_datazone_project_info")
    @patch("smus_cicd.commands.run.PipelineManifest.from_file")
    def test_project_info_error_returns_exit_code_1(
        self, mock_manifest, mock_project_info, mock_config, mock_mwaa_health
    ):
        """Test that run command returns exit code 1 when project info has error."""
        # Mock manifest
        mock_target = MagicMock()
        mock_target.project.name = "test-project"

        mock_manifest_obj = MagicMock()
        mock_manifest_obj.targets = {"test": mock_target}
        mock_manifest_obj.domain.region = "us-east-1"
        mock_manifest_obj.domain.name = "test-domain"
        mock_manifest_obj.pipeline_name = "test-pipeline"
        mock_manifest_obj.get_target_config.return_value = mock_target

        mock_manifest.return_value = mock_manifest_obj

        # Mock config and MWAA health check to fail
        mock_config.return_value = {}
        mock_mwaa_health.return_value = False

        # Mock project info with error
        mock_project_info.return_value = {"error": "Project not found"}

        # Run command
        result = self.runner.invoke(
            app,
            [
                "run",
                "--pipeline",
                "test.yaml",
                "--targets",
                "test",
                "--workflow",
                "test_dag",
                "--command",
                "dags list",
            ],
        )

        # Verify exit code 1
        assert result.exit_code == 1
        assert "No healthy MWAA environments found" in result.stdout

    def test_missing_workflow_parameter_returns_exit_code_1(self):
        """Test that run command returns exit code 1 when workflow parameter is missing."""
        result = self.runner.invoke(
            app,
            [
                "run",
                "--pipeline",
                "test.yaml",
                "--targets",
                "test",
                "--command",
                "dags list",
                # Missing --workflow parameter
            ],
        )

        # Verify exit code 1
        assert result.exit_code == 1
        assert "--workflow parameter is required" in result.stderr

    def test_missing_command_parameter_returns_exit_code_1(self):
        """Test that run command succeeds when command parameter is missing (uses default)."""
        result = self.runner.invoke(
            app,
            [
                "run",
                "--pipeline",
                "test.yaml",
                "--targets",
                "test",
                "--workflow",
                "test_dag",
                # Missing --command parameter is OK, will use default
            ],
        )

        # Verify error is about manifest file not found, not about missing command
        assert result.exit_code == 1
        assert "File not found: test.yaml" in result.stderr
