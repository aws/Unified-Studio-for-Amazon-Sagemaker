"""Unit tests for run command."""
import tempfile
import pytest
import re
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from smus_cicd.cli import app


def strip_ansi_codes(text):
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


class TestRunCommand:
    """Test cases for run command functionality."""

    def create_test_manifest(self):
        """Create a test manifest file."""
        manifest_content = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets:
  dev:
    stage: DEV
    project:
      name: test-project
      create: false
workflows:
  - workflowName: test_workflow
    connectionName: project.workflow_mwaa
"""
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        f.write(manifest_content)
        f.flush()
        return f.name

    def test_run_missing_workflow_parameter(self):
        """Test run command fails when --workflow is missing."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()
        
        try:
            result = runner.invoke(app, ["run", "--pipeline", manifest_file, "--command", "dags list"])
            assert result.exit_code == 1
            # Error messages go to stderr in typer
            assert "Error: --workflow parameter is required" in result.stderr or "workflow" in result.stderr
        finally:
            import os
            os.unlink(manifest_file)

    def test_run_missing_command_parameter(self):
        """Test run command fails when --command is missing."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()
        
        try:
            result = runner.invoke(app, ["run", "--pipeline", manifest_file, "--workflow", "test_workflow"])
            assert result.exit_code == 1
            # Error messages go to stderr in typer
            assert "Error: --command parameter is required" in result.stderr or "command" in result.stderr
        finally:
            import os
            os.unlink(manifest_file)

    def test_run_invalid_target(self):
        """Test run command fails with invalid target."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()
        
        try:
            result = runner.invoke(app, [
                "run", "--pipeline", manifest_file, 
                "--workflow", "test_workflow", 
                "--command", "dags list",
                "--targets", "invalid_target"
            ])
            assert result.exit_code == 1
            # Error messages go to stderr in typer
            assert "Target 'invalid_target' not found" in result.stderr or "invalid_target" in result.stderr
        finally:
            import os
            os.unlink(manifest_file)

    @patch('smus_cicd.commands.run.get_datazone_project_info')
    @patch('smus_cicd.helpers.mwaa.run_airflow_command')
    def test_run_successful_command(self, mock_run_airflow, mock_get_project):
        """Test successful run command execution."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()
        
        # Mock responses
        mock_get_project.return_value = {
            'project_id': 'test-project-id',
            'connections': {
                'project.workflow_mwaa': {
                    'type': 'WORKFLOWS_MWAA',
                    'environmentName': 'test-env'
                }
            }
        }
        mock_run_airflow.return_value = {
            'success': True,
            'stdout': 'dag1\ndag2\ndag3',
            'stderr': '',
            'status_code': 200
        }
        
        try:
            result = runner.invoke(app, [
                "run", "--pipeline", manifest_file,
                "--workflow", "test_workflow",
                "--command", "dags list",
                "--targets", "dev"
            ])
            
            assert result.exit_code == 0
            assert "Command executed successfully" in result.stdout
            assert "dag1" in result.stdout
            mock_run_airflow.assert_called_once()
        finally:
            import os
            os.unlink(manifest_file)

    @patch('smus_cicd.commands.run.get_datazone_project_info')
    @patch('smus_cicd.helpers.mwaa.run_airflow_command')
    def test_run_json_output(self, mock_run_airflow, mock_get_project):
        """Test run command with JSON output."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()
        
        # Mock responses
        mock_get_project.return_value = {
            'project_id': 'test-project-id',
            'connections': {
                'project.workflow_mwaa': {
                    'type': 'WORKFLOWS_MWAA',
                    'environmentName': 'test-env'
                }
            }
        }
        mock_run_airflow.return_value = {
            'success': True,
            'stdout': 'test output',
            'stderr': '',
            'status_code': 200
        }
        
        try:
            result = runner.invoke(app, [
                "run", "--pipeline", manifest_file,
                "--workflow", "test_workflow",
                "--command", "dags list",
                "--targets", "dev",
                "--output", "JSON"
            ])
            
            assert result.exit_code == 0
            # Should be valid JSON
            import json
            output_data = json.loads(result.stdout)
            assert "workflow" in output_data
            assert "command" in output_data
            assert "results" in output_data
        finally:
            import os
            os.unlink(manifest_file)

    @patch('smus_cicd.commands.run.get_datazone_project_info')
    def test_run_project_info_failure(self, mock_get_project):
        """Test run command when project info fails."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()
        
        mock_get_project.return_value = {
            'success': False,
            'error': 'Project not found'
        }
        
        try:
            result = runner.invoke(app, [
                "run", "--pipeline", manifest_file,
                "--workflow", "test_workflow",
                "--command", "dags list",
                "--targets", "dev"
            ])
            
            assert result.exit_code == 1  # Command fails with project info error
            assert "Failed to get project info" in result.stdout
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
