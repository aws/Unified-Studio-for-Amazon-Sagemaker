"""Integration tests for new CLI commands."""
import os
import tempfile
import pytest
from typer.testing import CliRunner
from smus_cicd.cli import app
from .base import IntegrationTestBase
from ..test_helpers import parse_json_or_show_error


@pytest.mark.integration
class TestNewCommandsIntegration(IntegrationTestBase):
    """Integration tests for create and run commands."""

    def test_create_and_describe_workflow(self):
        """Test complete workflow: create manifest -> describe it."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            manifest_file = "IntegrationTestPipeline.yaml"
            
            # Step 1: Create manifest with specific output file
            create_result = runner.invoke(app, [
                "create", 
                "--output", manifest_file,
                "--name", "IntegrationTestPipeline"
            ])
            
            assert create_result.exit_code == 0
            assert "Pipeline manifest created" in create_result.stdout
            assert os.path.exists(manifest_file)
            
            # Step 2: Describe the created manifest
            describe_result = runner.invoke(app, ["describe", "--pipeline", manifest_file])
            
            assert describe_result.exit_code == 0
            assert "Pipeline: IntegrationTestPipeline" in describe_result.stdout
            assert "Domain: your-domain-name" in describe_result.stdout
            assert "Targets:" in describe_result.stdout
            
            # Step 3: Test JSON output
            json_result = runner.invoke(app, ["describe", "--pipeline", manifest_file, "--output", "JSON"])
            
            assert json_result.exit_code == 0
            import json
            output_data = json.loads(json_result.stdout)
            assert output_data["pipeline"] == "IntegrationTestPipeline"

    def test_create_with_different_names(self):
        """Test creating manifests with different pipeline names."""
        runner = CliRunner()
        
        test_names = [
            "SimplePipeline",
            "Complex-Pipeline-Name",
            "Pipeline_With_Underscores",
            "Pipeline123"
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            
            for name in test_names:
                manifest_file = f"{name}.yaml"
                
                # Create manifest with specific output file
                result = runner.invoke(app, [
                    "create",
                    "--output", manifest_file,
                    "--name", name
                ])
                
                assert result.exit_code == 0
                assert f"Pipeline name: {name}" in result.stdout
                
                # Verify content
                with open(manifest_file, 'r') as f:
                    content = f.read()
                    assert f"pipelineName: {name}" in content
                
                # Verify it can be described
                describe_result = runner.invoke(app, ["describe", "--pipeline", manifest_file])
                assert describe_result.exit_code == 0
                assert f"Pipeline: {name}" in describe_result.stdout

    def test_describe_target_filtering_comprehensive(self):
        """Test comprehensive target filtering scenarios."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            manifest_file = "TargetTestPipeline.yaml"
            
            # Create manifest with specific output file
            create_result = runner.invoke(app, [
                "create",
                "--output", manifest_file,
                "--name", "TargetTestPipeline"
            ])
            assert create_result.exit_code == 0
            
            # Test each target individually
            targets = ["dev", "test", "prod"]
            
            for target in targets:
                result = runner.invoke(app, [
                    "describe", "--pipeline", manifest_file,
                    "--targets", target
                ])
                
                assert result.exit_code == 0
                assert f"{target}:" in result.stdout
                
                # Verify other targets are not shown
                other_targets = [t for t in targets if t != target]
                for other in other_targets:
                    assert f"{other}:" not in result.stdout

    def test_run_command_parameter_validation(self):
        """Test run command parameter validation."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            
            manifest_file = "RunTestPipeline.yaml"
            
            # Create manifest with specific output file
            create_result = runner.invoke(app, [
                "create",
                "--output", manifest_file,
                "--name", "RunTestPipeline"
            ])
            assert create_result.exit_code == 0
            
            # Test missing workflow parameter
            result = runner.invoke(app, [
                "run", "--pipeline", manifest_file,
                "--command", "dags list"
            ])
            assert result.exit_code == 1
            assert "Error: --workflow parameter is required" in result.output
            
            # Test missing command parameter
            result = runner.invoke(app, [
                "run", "--pipeline", manifest_file,
                "--workflow", "test_workflow"
            ])
            assert result.exit_code == 1
            assert "Error: --command parameter is required" in result.output
            
            # Test invalid target
            result = runner.invoke(app, [
                "run", "--pipeline", manifest_file,
                "--workflow", "test_workflow",
                "--command", "dags list",
                "--targets", "invalid"
            ])
            assert result.exit_code == 1
            assert "Target 'invalid' not found" in result.output

    @pytest.mark.slow
    def test_airflow_commands_variety(self):
        """Test various Airflow commands with run command."""
        runner = CliRunner()
        
        # Common Airflow commands to test
        airflow_commands = [
            "dags list",
            "dags show test_dag",
            "tasks list test_dag",
            "dags state test_dag",
            "version"
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            
            # Create manifest
            create_result = runner.invoke(app, [
                "create",
                "--name", "AirflowTestPipeline"
            ])
            assert create_result.exit_code == 0
            
            manifest_file = "AirflowTestPipeline.yaml"
            
            for command in airflow_commands:
                # Test TEXT output
                result = runner.invoke(app, [
                    "run", "--pipeline", manifest_file,
                    "--workflow", "test_workflow",
                    "--command", command,
                    "--targets", "dev"
                ])
                
                # Command should fail because no real AWS resources exist
                # This is expected behavior - the test validates the command structure works
                assert result.exit_code == 1, f"Airflow command {command} should fail without AWS resources"
                
                # Test JSON output - should be valid JSON even on failure
                json_result = runner.invoke(app, [
                    "run", "--pipeline", manifest_file,
                    "--workflow", "test_workflow", 
                    "--command", command,
                    "--targets", "dev",
                    "--output", "JSON"
                ])
                
                # JSON command should also fail but return valid JSON
                assert json_result.exit_code == 1
                
                # Verify JSON output is valid even on failure
                if json_result.stdout.strip():
                    try:
                        import json
                        json.loads(json_result.stdout)
                    except json.JSONDecodeError:
                        pytest.fail(f"Invalid JSON output for command: {command}")

    def test_output_format_consistency(self):
        """Test output format consistency across commands."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            
            manifest_file = "FormatTestPipeline.yaml"
            
            # Create manifest with specific output file
            create_result = runner.invoke(app, [
                "create",
                "--output", manifest_file,
                "--name", "FormatTestPipeline"
            ])
            assert create_result.exit_code == 0
            
            # Test describe JSON format
            describe_json = runner.invoke(app, [
                "describe", "--pipeline", manifest_file,
                "--output", "JSON"
            ])
            assert describe_json.exit_code == 0
            
            import json
            describe_data = json.loads(describe_json.stdout)
            
            # Verify JSON structure
            required_keys = ["pipeline", "domain", "targets"]
            for key in required_keys:
                assert key in describe_data
            
            # Test run JSON format (will fail but should return valid JSON error)
            run_json = runner.invoke(app, [
                "run", "--pipeline", manifest_file,
                "--workflow", "test_workflow",
                "--command", "dags list",
                "--output", "JSON"
            ])
            
            # Should return valid JSON even on failure
            if run_json.stdout.strip():
                parse_json_or_show_error(run_json.stdout, "Run command")
