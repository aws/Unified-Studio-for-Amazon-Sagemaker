"""Unit tests for test command."""
import os
import tempfile
import pytest
from typer.testing import CliRunner
from smus_cicd.cli import app


class TestTestCommand:
    """Test cases for test command."""
    
    def create_test_manifest_with_tests(self):
        """Create a test manifest with tests configuration."""
        manifest_content = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  storage:
    - connectionName: default.s3_shared
      include: ["src/"]
targets:
  dev:
    project:
      name: test-project-dev
    stage: dev
    tests:
      folder: tests/
workflows:
  - workflowName: test_dag
    connectionName: project.workflow_mwaa
    engine: MWAA
"""
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            f.write(manifest_content)
        return path
    
    def create_test_manifest_without_tests(self):
        """Create a test manifest without tests configuration."""
        manifest_content = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  storage:
    - connectionName: default.s3_shared
      include: ["src/"]
targets:
  dev:
    project:
      name: test-project-dev
    stage: dev
workflows:
  - workflowName: test_dag
    connectionName: project.workflow_mwaa
    engine: MWAA
"""
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            f.write(manifest_content)
        return path
    
    def test_test_command_no_tests_configured(self):
        """Test test command with no tests configured."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest_without_tests()
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                os.chdir(temp_dir)
                
                result = runner.invoke(app, ["test", "--pipeline", manifest_file])
                
                assert result.exit_code == 1  # Should fail when no tests configured
                assert "No tests configured" in result.stdout
                assert "TestPipeline" in result.stdout
        finally:
            os.unlink(manifest_file)
    
    def test_test_command_missing_test_folder(self):
        """Test test command with missing test folder."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest_with_tests()
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                os.chdir(temp_dir)
                
                result = runner.invoke(app, ["test", "--pipeline", manifest_file, "--targets", "dev"])
                
                assert result.exit_code == 1
                assert "Test folder not found" in result.stdout
        finally:
            os.unlink(manifest_file)
    
    def test_test_command_with_test_folder(self):
        """Test test command with existing test folder."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest_with_tests()
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                os.chdir(temp_dir)
                
                # Create test folder and a simple test
                os.makedirs("tests")
                with open("tests/test_example.py", "w") as f:
                    f.write("""
import os

def test_environment_variables():
    assert os.getenv('SMUS_TARGET_NAME') is not None
    assert os.getenv('SMUS_PROJECT_NAME') is not None
    
def test_simple():
    assert True
""")
                
                result = runner.invoke(app, ["test", "--pipeline", manifest_file, "--targets", "dev"])
                
                # Should show test folder found (even if AWS connection fails)
                # The test folder check happens before AWS calls
                assert "Test folder: tests/" in result.stdout or "Error getting project info" in result.stdout
                assert "TestPipeline" in result.stdout
        finally:
            os.unlink(manifest_file)
    
    def test_test_command_json_output(self):
        """Test test command with JSON output."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest_without_tests()
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                os.chdir(temp_dir)
                
                result = runner.invoke(app, ["test", "--pipeline", manifest_file, "--output", "JSON"])
                
                assert result.exit_code == 1  # Should fail when no tests configured
                assert '"pipeline": "TestPipeline"' in result.stdout
                assert '"status": "error"' in result.stdout
        finally:
            os.unlink(manifest_file)
    
    def test_test_command_specific_target(self):
        """Test test command with specific target."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest_without_tests()
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                os.chdir(temp_dir)
                
                result = runner.invoke(app, ["test", "--pipeline", manifest_file, "--targets", "dev"])
                
                assert result.exit_code == 1  # Should fail when no tests configured
                assert "Target: dev" in result.stdout
        finally:
            os.unlink(manifest_file)
    
    def test_test_command_invalid_target(self):
        """Test test command with invalid target."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest_without_tests()
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                os.chdir(temp_dir)
                
                result = runner.invoke(app, ["test", "--pipeline", manifest_file, "--targets", "invalid"])
                
                assert result.exit_code == 1
                assert "Target 'invalid' not found" in result.stdout
        finally:
            os.unlink(manifest_file)
    
    def test_test_command_verbose_output(self):
        """Test test command with verbose output."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest_without_tests()
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                os.chdir(temp_dir)
                
                result = runner.invoke(app, ["test", "--pipeline", manifest_file, "--verbose"])
                
                assert result.exit_code == 1  # Should fail when no tests configured
                assert "TestPipeline" in result.stdout
        finally:
            os.unlink(manifest_file)
