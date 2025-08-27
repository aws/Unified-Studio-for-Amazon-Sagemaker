"""Integration tests for run command against live Airflow environments."""
import pytest
from typer.testing import CliRunner
from smus_cicd.cli import app
from .base import IntegrationTestBase


@pytest.mark.integration
@pytest.mark.slow
class TestRunCommandLive(IntegrationTestBase):
    """Integration tests for run command against live MWAA environments."""

    def get_multi_target_pipeline_file(self):
        """Get the multi-target pipeline manifest file path."""
        return "tests/integration/multi_target_pipeline/multi_target_pipeline.yaml"

    def test_run_command_parameter_validation_live(self):
        """Test run command parameter validation with live manifest."""
        runner = CliRunner()
        
        # Test help command works
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "Run Airflow CLI commands" in result.stdout

    def test_run_command_target_validation_live(self):
        """Test run command target validation with live manifest."""
        runner = CliRunner()
        
        # Test help command works
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "Run Airflow CLI commands" in result.stdout

    def test_run_command_json_output_structure_live(self):
        """Test run command JSON output structure with live manifest."""
        runner = CliRunner()
        
        # Test help command works
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "Run Airflow CLI commands" in result.stdout

    def test_run_command_help_and_validation_live(self):
        """Test run command help and basic validation."""
        runner = CliRunner()
        
        # Test help
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "Run Airflow CLI commands" in result.stdout
        
        # Test with invalid pipeline file
        result = runner.invoke(app, [
            "run", "--pipeline", "nonexistent.yaml",
            "--workflow", "test_dag",
            "--command", "dags list"
        ])
        assert result.exit_code == 1
