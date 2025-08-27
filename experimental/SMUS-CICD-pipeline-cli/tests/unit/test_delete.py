"""Unit tests for delete command."""

import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from smus_cicd.cli import app


class TestDeleteCommand:
    """Test delete command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch('smus_cicd.commands.delete.PipelineManifest')
    @patch('smus_cicd.commands.delete.get_domain_id_by_name')
    @patch('smus_cicd.commands.delete.get_project_id_by_name')
    @patch('smus_cicd.commands.delete.delete_project')
    @patch('smus_cicd.commands.delete.get_project_status')
    @patch('smus_cicd.commands.delete.Confirm.ask')
    def test_delete_with_confirmation(self, mock_confirm, mock_get_status, mock_delete, 
                                    mock_get_project_id, mock_get_domain_id, mock_manifest_class):
        """Test delete command with user confirmation."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.pipeline_name = "TestPipeline"
        mock_manifest.domain.name = "test-domain"
        mock_manifest.domain.region = "us-east-1"
        mock_manifest.targets = {
            "test": MagicMock()
        }
        mock_manifest.targets["test"].project = MagicMock()
        mock_manifest.targets["test"].project.name = "test-project"
        
        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_get_project_id.return_value = "project-456"
        mock_confirm.return_value = True  # User confirms deletion
        mock_get_status.return_value = None  # Project deleted

        # Run command
        result = self.runner.invoke(app, [
            "delete", 
            "--targets", "test",
            "--pipeline", "tests/fixtures/test-pipeline.yaml"
        ])

        # Assertions
        assert result.exit_code == 0
        mock_confirm.assert_called_once()
        mock_delete.assert_called_once_with("test-domain", "project-456", "us-east-1")
        assert "Successfully deleted" in result.stdout

    @patch('smus_cicd.commands.delete.PipelineManifest')
    @patch('smus_cicd.commands.delete.get_domain_id_by_name')
    @patch('smus_cicd.commands.delete.get_project_id_by_name')
    @patch('smus_cicd.commands.delete.delete_project')
    @patch('smus_cicd.commands.delete.get_project_status')
    def test_delete_with_force_flag(self, mock_get_status, mock_delete, 
                                  mock_get_project_id, mock_get_domain_id, mock_manifest_class):
        """Test delete command with --force flag (no confirmation)."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.pipeline_name = "TestPipeline"
        mock_manifest.domain.name = "test-domain"
        mock_manifest.domain.region = "us-east-1"
        mock_manifest.targets = {
            "test": MagicMock()
        }
        mock_manifest.targets["test"].project = MagicMock()
        mock_manifest.targets["test"].project.name = "test-project"
        
        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_get_project_id.return_value = "project-456"
        mock_get_status.return_value = None  # Project deleted

        # Run command with --force
        result = self.runner.invoke(app, [
            "delete", 
            "--targets", "test",
            "--pipeline", "tests/fixtures/test-pipeline.yaml",
            "--force"
        ])

        # Assertions
        assert result.exit_code == 0
        mock_delete.assert_called_once_with("test-domain", "project-456", "us-east-1")
        assert "Successfully deleted" in result.stdout

    @patch('smus_cicd.commands.delete.PipelineManifest')
    @patch('smus_cicd.commands.delete.get_domain_id_by_name')
    @patch('smus_cicd.commands.delete.get_project_id_by_name')
    @patch('smus_cicd.commands.delete.delete_project')
    def test_delete_async_mode(self, mock_delete, mock_get_project_id, 
                             mock_get_domain_id, mock_manifest_class):
        """Test delete command with --async flag."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.pipeline_name = "TestPipeline"
        mock_manifest.domain.name = "test-domain"
        mock_manifest.domain.region = "us-east-1"
        mock_manifest.targets = {
            "test": MagicMock()
        }
        mock_manifest.targets["test"].project = MagicMock()
        mock_manifest.targets["test"].project.name = "test-project"
        
        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_get_project_id.return_value = "project-456"

        # Run command with --async
        result = self.runner.invoke(app, [
            "delete", 
            "--targets", "test",
            "--pipeline", "tests/fixtures/test-pipeline.yaml",
            "--force",
            "--async"
        ])

        # Assertions
        assert result.exit_code == 0
        mock_delete.assert_called_once_with("test-domain", "project-456", "us-east-1")
        assert "Deletion initiated" in result.stdout

    @patch('smus_cicd.commands.delete.PipelineManifest')
    @patch('smus_cicd.commands.delete.get_domain_id_by_name')
    @patch('smus_cicd.commands.delete.get_project_id_by_name')
    def test_delete_project_not_found(self, mock_get_project_id, 
                                    mock_get_domain_id, mock_manifest_class):
        """Test delete command when project doesn't exist."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.pipeline_name = "TestPipeline"
        mock_manifest.domain.name = "test-domain"
        mock_manifest.domain.region = "us-east-1"
        mock_manifest.targets = {
            "test": MagicMock()
        }
        mock_manifest.targets["test"].project = MagicMock()
        mock_manifest.targets["test"].project.name = "test-project"
        
        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_get_project_id.return_value = None  # Project not found

        # Run command
        result = self.runner.invoke(app, [
            "delete", 
            "--targets", "test",
            "--pipeline", "tests/fixtures/test-pipeline.yaml",
            "--force"
        ])

        # Assertions
        assert result.exit_code == 0
        assert "not found - skipping" in result.stdout

    @patch('smus_cicd.commands.delete.PipelineManifest')
    def test_delete_invalid_target(self, mock_manifest_class):
        """Test delete command with invalid target name."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.pipeline_name = "TestPipeline"
        mock_manifest.domain.name = "test-domain"
        mock_manifest.domain.region = "us-east-1"
        mock_manifest.targets = {
            "test": MagicMock()
        }
        mock_manifest.targets["test"].project = MagicMock()
        mock_manifest.targets["test"].project.name = "test-project"
        
        mock_manifest_class.from_file.return_value = mock_manifest

        # Run command with invalid target
        result = self.runner.invoke(app, [
            "delete", 
            "--targets", "invalid-target",
            "--pipeline", "tests/fixtures/test-pipeline.yaml",
            "--force"
        ])

        # Assertions
        assert result.exit_code == 1
        assert "not found in manifest" in result.stdout

    @patch('smus_cicd.commands.delete.PipelineManifest')
    @patch('smus_cicd.commands.delete.get_domain_id_by_name')
    @patch('smus_cicd.commands.delete.get_project_id_by_name')
    @patch('smus_cicd.commands.delete.delete_project')
    @patch('smus_cicd.commands.delete.get_project_status')
    def test_delete_json_output(self, mock_get_status, mock_delete, 
                              mock_get_project_id, mock_get_domain_id, mock_manifest_class):
        """Test delete command with JSON output format."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.pipeline_name = "TestPipeline"
        mock_manifest.domain.name = "test-domain"
        mock_manifest.domain.region = "us-east-1"
        mock_manifest.targets = {
            "test": MagicMock()
        }
        mock_manifest.targets["test"].project = MagicMock()
        mock_manifest.targets["test"].project.name = "test-project"
        
        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_get_project_id.return_value = "project-456"
        mock_get_status.return_value = None  # Project deleted

        # Run command with JSON output
        result = self.runner.invoke(app, [
            "delete", 
            "--targets", "test",
            "--pipeline", "tests/fixtures/test-pipeline.yaml",
            "--force",
            "--output", "JSON"
        ])

        # Assertions
        assert result.exit_code == 0
        
        # Verify JSON output
        import json
        output_data = json.loads(result.stdout)
        assert output_data["pipeline"] == "TestPipeline"
        assert output_data["domain"] == "test-domain"
        assert len(output_data["results"]) == 1
        assert output_data["results"][0]["target"] == "test"
        assert output_data["results"][0]["status"] == "deleted"

    @patch('smus_cicd.commands.delete.PipelineManifest')
    @patch('smus_cicd.commands.delete.get_domain_id_by_name')
    @patch('smus_cicd.commands.delete.get_project_id_by_name')
    @patch('smus_cicd.commands.delete.delete_project')
    def test_delete_multiple_targets(self, mock_delete, mock_get_project_id, 
                                   mock_get_domain_id, mock_manifest_class):
        """Test delete command with multiple targets."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.pipeline_name = "TestPipeline"
        mock_manifest.domain.name = "test-domain"
        mock_manifest.domain.region = "us-east-1"
        mock_manifest.targets = {
            "test1": MagicMock(project=MagicMock(name="test-project-1")),
            "test2": MagicMock(project=MagicMock(name="test-project-2"))
        }
        
        mock_manifest_class.from_file.return_value = mock_manifest
        mock_get_domain_id.return_value = "domain-123"
        mock_get_project_id.side_effect = ["project-456", "project-789"]

        # Run command with multiple targets
        result = self.runner.invoke(app, [
            "delete", 
            "--targets", "test1,test2",
            "--pipeline", "tests/fixtures/test-pipeline.yaml",
            "--force",
            "--async"
        ])

        # Assertions
        assert result.exit_code == 0
        assert mock_delete.call_count == 2
        mock_delete.assert_any_call("test-domain", "project-456", "us-east-1")
        mock_delete.assert_any_call("test-domain", "project-789", "us-east-1")

    @patch('smus_cicd.commands.delete.PipelineManifest')
    @patch('smus_cicd.commands.delete.Confirm.ask')
    def test_delete_cancelled_by_user(self, mock_confirm, mock_manifest_class):
        """Test delete command when user cancels confirmation."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.pipeline_name = "TestPipeline"
        mock_manifest.domain.name = "test-domain"
        mock_manifest.domain.region = "us-east-1"
        mock_manifest.targets = {
            "test": MagicMock()
        }
        mock_manifest.targets["test"].project = MagicMock()
        mock_manifest.targets["test"].project.name = "test-project"
        
        mock_manifest_class.from_file.return_value = mock_manifest
        mock_confirm.return_value = False  # User cancels

        # Run command
        result = self.runner.invoke(app, [
            "delete", 
            "--targets", "test",
            "--pipeline", "tests/fixtures/test-pipeline.yaml"
        ])

        # Assertions
        assert result.exit_code == 0
        assert "Deletion cancelled" in result.stdout
