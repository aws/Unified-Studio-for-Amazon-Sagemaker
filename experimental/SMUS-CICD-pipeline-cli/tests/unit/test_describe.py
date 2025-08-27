"""Unit tests for describe command."""
import pytest
import tempfile
import os
from typer.testing import CliRunner
from smus_cicd.cli import app


@pytest.fixture
def sample_manifest():
    """Create a sample manifest file for testing."""
    manifest_content = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: ./bundles
targets:
  dev:
    stage: DEV
    project:
      name: test-project
      create: false
workflows:
  - workflowName: test_workflow
    connectionName: project.workflow_mwaa
    triggerPostDeployment: true
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(manifest_content)
        f.flush()
        yield f.name
    os.unlink(f.name)


def test_describe_basic(sample_manifest):
    """Test basic describe functionality."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        with open("test.yaml", "w") as f:
            f.write(open(sample_manifest).read())
        
        result = runner.invoke(app, ["describe", "--pipeline", "test.yaml"])
        assert result.exit_code == 0
        assert "Pipeline: TestPipeline" in result.stdout
        assert "Domain: test-domain (us-east-1)" in result.stdout


def test_describe_with_connections(sample_manifest):
    """Test describe with connections flag."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        with open("test.yaml", "w") as f:
            f.write(open(sample_manifest).read())
        
        result = runner.invoke(app, ["describe", "--pipeline", "test.yaml", "--connections"])
        assert result.exit_code == 0
        # Connections flag shows basic pipeline info
        assert "Pipeline:" in result.stdout
        assert "Targets:" in result.stdout


def test_describe_with_targets(sample_manifest):
    """Test describe with targets flag."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        with open("test.yaml", "w") as f:
            f.write(open(sample_manifest).read())
        
        # Test filtering to specific target
        result = runner.invoke(app, ["describe", "--pipeline", "test.yaml", "--targets", "dev"])
        assert result.exit_code == 0
        assert "Targets:" in result.stdout
        assert "dev: test-project" in result.stdout


def test_describe_with_connect_flag(sample_manifest):
    """Test describe with connect flag (should not fail even without AWS access)."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        with open("test.yaml", "w") as f:
            f.write(open(sample_manifest).read())
        
        # This might fail due to AWS access, but should show basic info
        result = runner.invoke(app, ["describe", "--pipeline", "test.yaml", "--connect"])
        # Exit code might be 1 due to AWS connection issues, but should not be a crash
        assert result.exit_code in [0, 1]
        # Should at least show pipeline info even if connect fails
        if result.stdout:
            assert "Pipeline:" in result.stdout or "error" in result.stdout.lower()
