"""Unit tests for delete command."""

import json
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from smus_cicd.cli import app
from smus_cicd.commands.delete import delete_command


class TestDeleteCommand:
    """Test cases for delete command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("smus_cicd.commands.delete.ApplicationManifest")
    @patch("smus_cicd.commands.delete.get_domain_id_by_name")
    @patch("smus_cicd.commands.delete.delete_project_stack")
    @patch("smus_cicd.commands.delete.Confirm.ask")
    def test_delete_with_confirmation(
        self, mock_confirm, mock_delete_stack, mock_get_domain_id, mock_manifest_class
    ):
        """Test delete command with user confirmation."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.application_name = "TestPipeline"
        mock_manifest.stages = {"test": MagicMock()}
        mock_manifest.stages["test"].project = MagicMock()
        mock_manifest.stages["test"].project.name = "test-project"
        mock_manifest.stages["test"].domain = MagicMock()
        mock_manifest.stages["test"].domain.name = "test-domain"
        mock_manifest.stages["test"].domain.region = "us-east-1"

        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_confirm.return_value = True  # User confirms deletion
        mock_delete_stack.return_value = True  # Stack deletion succeeds

        # Run command
        result = self.runner.invoke(
            app,
            [
                "delete",
                "--targets",
                "test",
                "--manifest",
                "tests/fixtures/test-bundle.yaml",
            ],
        )

        # Assertions
        assert result.exit_code == 0
        mock_confirm.assert_called_once()
        mock_delete_stack.assert_called_once_with(
            "test-project", "test-domain", "us-east-1", "TestPipeline", "test", "TEXT"
        )
        assert "Successfully deleted stack for test-project" in result.stdout

    @patch("smus_cicd.commands.delete.ApplicationManifest")
    @patch("smus_cicd.commands.delete.get_domain_id_by_name")
    @patch("smus_cicd.commands.delete.delete_project_stack")
    def test_delete_with_force_flag(
        self, mock_delete_stack, mock_get_domain_id, mock_manifest_class
    ):
        """Test delete command with --force flag (skips confirmation)."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.application_name = "TestPipeline"
        mock_manifest.stages = {"test": MagicMock()}
        mock_manifest.stages["test"].project = MagicMock()
        mock_manifest.stages["test"].project.name = "test-project"
        mock_manifest.stages["test"].domain = MagicMock()
        mock_manifest.stages["test"].domain.name = "test-domain"
        mock_manifest.stages["test"].domain.region = "us-east-1"

        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_delete_stack.return_value = True  # Stack deletion succeeds

        # Run command with --force
        result = self.runner.invoke(
            app,
            [
                "delete",
                "--targets",
                "test",
                "--force",
                "--manifest",
                "tests/fixtures/test-bundle.yaml",
            ],
        )

        # Assertions
        assert result.exit_code == 0
        mock_delete_stack.assert_called_once_with(
            "test-project", "test-domain", "us-east-1", "TestPipeline", "test", "TEXT"
        )
        assert "Successfully deleted stack for test-project" in result.stdout

    @patch("smus_cicd.commands.delete.ApplicationManifest")
    @patch("smus_cicd.commands.delete.get_domain_id_by_name")
    @patch("smus_cicd.commands.delete.delete_project_stack")
    def test_delete_async_mode(
        self, mock_delete_stack, mock_get_domain_id, mock_manifest_class
    ):
        """Test delete command with --async flag."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.application_name = "TestPipeline"
        mock_manifest.stages = {"test": MagicMock()}
        mock_manifest.stages["test"].project = MagicMock()
        mock_manifest.stages["test"].project.name = "test-project"
        mock_manifest.stages["test"].domain = MagicMock()
        mock_manifest.stages["test"].domain.name = "test-domain"
        mock_manifest.stages["test"].domain.region = "us-east-1"

        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_delete_stack.return_value = True  # Stack deletion succeeds

        # Run command with --async
        result = self.runner.invoke(
            app,
            [
                "delete",
                "--targets",
                "test",
                "--force",
                "--async",
                "--manifest",
                "tests/fixtures/test-bundle.yaml",
            ],
        )

        # Assertions
        assert result.exit_code == 0
        mock_delete_stack.assert_called_once_with(
            "test-project", "test-domain", "us-east-1", "TestPipeline", "test", "TEXT"
        )
        assert "Stack deletion initiated for test-project" in result.stdout

    @patch("smus_cicd.commands.delete.ApplicationManifest")
    @patch("smus_cicd.commands.delete.get_domain_id_by_name")
    @patch("smus_cicd.commands.delete.delete_project_stack")
    def test_delete_project_not_found(
        self, mock_delete_stack, mock_get_domain_id, mock_manifest_class
    ):
        """Test delete command when stack deletion fails."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.application_name = "TestPipeline"
        mock_manifest.stages = {"test": MagicMock()}
        mock_manifest.stages["test"].project = MagicMock()
        mock_manifest.stages["test"].project.name = "test-project"
        mock_manifest.stages["test"].domain = MagicMock()
        mock_manifest.stages["test"].domain.name = "test-domain"
        mock_manifest.stages["test"].domain.region = "us-east-1"

        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_delete_stack.return_value = False  # Stack deletion fails

        # Run command
        result = self.runner.invoke(
            app,
            [
                "delete",
                "--targets",
                "test",
                "--force",
                "--manifest",
                "tests/fixtures/test-bundle.yaml",
            ],
        )

        # Assertions
        assert result.exit_code == 0  # Command doesn't fail, just reports error
        mock_delete_stack.assert_called_once()
        assert "Failed to delete CloudFormation stack" in result.stdout

    @patch("smus_cicd.commands.delete.ApplicationManifest")
    def test_delete_invalid_target(self, mock_manifest_class):
        """Test delete command with invalid target name."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.application_name = "TestPipeline"
        mock_manifest.stages = {"test": MagicMock()}

        mock_manifest_class.from_file.return_value = mock_manifest

        # Run command with invalid target
        result = self.runner.invoke(
            app,
            [
                "delete",
                "--targets",
                "invalid-target",
                "--force",
                "--manifest",
                "tests/fixtures/test-bundle.yaml",
            ],
        )

        # Assertions
        assert result.exit_code == 1
        assert "not found in manifest" in result.stdout

    @patch("smus_cicd.commands.delete.ApplicationManifest")
    @patch("smus_cicd.commands.delete.get_domain_id_by_name")
    @patch("smus_cicd.commands.delete.delete_project_stack")
    def test_delete_json_output(
        self, mock_delete_stack, mock_get_domain_id, mock_manifest_class
    ):
        """Test delete command with JSON output format."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.application_name = "TestPipeline"
        mock_manifest.stages = {"test": MagicMock()}
        mock_manifest.stages["test"].project = MagicMock()
        mock_manifest.stages["test"].project.name = "test-project"
        mock_manifest.stages["test"].domain = MagicMock()
        mock_manifest.stages["test"].domain.name = "test-domain"
        mock_manifest.stages["test"].domain.region = "us-east-1"

        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_delete_stack.return_value = True  # Stack deletion succeeds

        # Run command with JSON output
        result = self.runner.invoke(
            app,
            [
                "delete",
                "--targets",
                "test",
                "--force",
                "--output",
                "JSON",
                "--manifest",
                "tests/fixtures/test-bundle.yaml",
            ],
        )

        # Assertions
        assert result.exit_code == 0
        mock_delete_stack.assert_called_once_with(
            "test-project", "test-domain", "us-east-1", "TestPipeline", "test", "JSON"
        )

        # Parse JSON output
        output_data = json.loads(result.stdout)
        assert output_data["bundle"] == "TestPipeline"
        assert len(output_data["results"]) == 1
        assert output_data["results"][0]["target"] == "test"
        assert output_data["results"][0]["status"] == "deleted"

    @patch("smus_cicd.commands.delete.ApplicationManifest")
    @patch("smus_cicd.commands.delete.get_domain_id_by_name")
    @patch("smus_cicd.commands.delete.delete_project_stack")
    def test_delete_multiple_targets(
        self, mock_delete_stack, mock_get_domain_id, mock_manifest_class
    ):
        """Test delete command with multiple targets."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.application_name = "TestPipeline"
        mock_manifest.stages = {"test": MagicMock(), "prod": MagicMock()}
        mock_manifest.stages["test"].project = MagicMock()
        mock_manifest.stages["test"].project.name = "test-project"
        mock_manifest.stages["test"].domain = MagicMock()
        mock_manifest.stages["test"].domain.name = "test-domain"
        mock_manifest.stages["test"].domain.region = "us-east-1"
        mock_manifest.stages["prod"].project = MagicMock()
        mock_manifest.stages["prod"].project.name = "prod-project"
        mock_manifest.stages["prod"].domain = MagicMock()
        mock_manifest.stages["prod"].domain.name = "test-domain"
        mock_manifest.stages["prod"].domain.region = "us-east-1"

        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_delete_stack.return_value = True  # Stack deletion succeeds

        # Run command with multiple targets
        result = self.runner.invoke(
            app,
            [
                "delete",
                "--targets",
                "test,prod",
                "--force",
                "--manifest",
                "tests/fixtures/test-bundle.yaml",
            ],
        )

        # Assertions
        assert result.exit_code == 0
        assert mock_delete_stack.call_count == 2
        mock_delete_stack.assert_any_call(
            "test-project", "test-domain", "us-east-1", "TestPipeline", "test", "TEXT"
        )
        mock_delete_stack.assert_any_call(
            "prod-project", "test-domain", "us-east-1", "TestPipeline", "prod", "TEXT"
        )

    @patch("smus_cicd.commands.delete.ApplicationManifest")
    @patch("smus_cicd.commands.delete.Confirm.ask")
    def test_delete_cancelled_by_user(self, mock_confirm, mock_manifest_class):
        """Test delete command when user cancels confirmation."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.application_name = "TestPipeline"
        mock_manifest.stages = {"test": MagicMock()}
        mock_manifest.stages["test"].project = MagicMock()
        mock_manifest.stages["test"].project.name = "test-project"

        mock_manifest_class.from_file.return_value = mock_manifest
        mock_confirm.return_value = False  # User cancels deletion

        # Run command
        result = self.runner.invoke(
            app,
            [
                "delete",
                "--targets",
                "test",
                "--manifest",
                "tests/fixtures/test-bundle.yaml",
            ],
        )

        # Assertions
        assert result.exit_code == 0  # Command exits gracefully
        mock_confirm.assert_called_once()
