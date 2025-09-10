"""Unit tests for test command exit codes."""

import pytest
import typer
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from smus_cicd.cli import app


class TestTestCommandExitCodes:
    """Test exit codes for test command failure scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
    
    @patch('smus_cicd.commands.test.PipelineManifest.from_file')
    def test_no_tests_configured_returns_exit_code_1(self, mock_manifest):
        """Test that test command returns exit code 1 when no tests are configured."""
        # Mock manifest with target that has no tests
        mock_target = MagicMock()
        mock_target.tests = None
        
        mock_manifest_obj = MagicMock()
        mock_manifest_obj.targets = {'test': mock_target}
        mock_manifest_obj.domain.region = 'us-east-1'
        mock_manifest_obj.domain.name = 'test-domain'
        mock_manifest_obj.pipeline_name = 'test-pipeline'
        
        mock_manifest.return_value = mock_manifest_obj
        
        # Run test command
        result = self.runner.invoke(app, [
            "test", 
            "--pipeline", "test.yaml", 
            "--targets", "test"
        ])
        
        # Verify exit code 1
        assert result.exit_code == 1
        assert "No tests configured" in result.stdout
        assert "Failed (no tests configured)" in result.stdout
    
    @patch('smus_cicd.commands.test.PipelineManifest.from_file')
    def test_missing_test_folder_returns_exit_code_1(self, mock_manifest):
        """Test that test command returns exit code 1 when test folder is missing."""
        # Mock manifest with target that has tests but folder doesn't exist
        mock_tests = MagicMock()
        mock_tests.folder = '/nonexistent/folder'
        
        mock_target = MagicMock()
        mock_target.tests = mock_tests
        mock_target.project.name = 'test-project'
        
        mock_manifest_obj = MagicMock()
        mock_manifest_obj.targets = {'test': mock_target}
        mock_manifest_obj.domain.region = 'us-east-1'
        mock_manifest_obj.domain.name = 'test-domain'
        mock_manifest_obj.pipeline_name = 'test-pipeline'
        
        mock_manifest.return_value = mock_manifest_obj
        
        # Run test command
        result = self.runner.invoke(app, [
            "test", 
            "--pipeline", "test.yaml", 
            "--targets", "test"
        ])
        
        # Verify exit code 1
        assert result.exit_code == 1
        assert "Test folder not found" in result.stdout
