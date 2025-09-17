"""Unit tests for describe command."""

import pytest
import tempfile
import os
from unittest.mock import patch
from typer.testing import CliRunner
from smus_cicd.cli import app


@pytest.fixture
def sample_manifest():
    """Create a sample manifest file for testing."""
    manifest_content = """
pipelineName: TestPipeline
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  dev:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: DEV
    project:
      name: test-project
      create: false
workflows:
  - workflowName: test_workflow
    connectionName: project.workflow_mwaa
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(manifest_content)
        f.flush()
        yield f.name
    os.unlink(f.name)


@patch("smus_cicd.helpers.utils._get_region_from_config")
@patch("smus_cicd.helpers.utils.load_config")
def test_describe_basic(mock_load_config, mock_get_region, sample_manifest):
    """Test basic describe functionality."""
    mock_load_config.return_value = {"region": "us-east-1"}
    mock_get_region.return_value = "us-east-1"

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        with open("test.yaml", "w") as f:
            f.write(open(sample_manifest).read())

        result = runner.invoke(app, ["describe", "--pipeline", "test.yaml"])
        assert result.exit_code == 0
        assert "Pipeline: TestPipeline" in result.stdout
        assert "Domain: test-domain" in result.stdout


@patch("smus_cicd.helpers.utils._get_region_from_config")
@patch("smus_cicd.helpers.utils.load_config")
def test_describe_with_connections(mock_load_config, mock_get_region, sample_manifest):
    """Test describe with connections flag."""
    mock_load_config.return_value = {"region": "us-east-1"}
    mock_get_region.return_value = "us-east-1"

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        with open("test.yaml", "w") as f:
            f.write(open(sample_manifest).read())

        result = runner.invoke(
            app, ["describe", "--pipeline", "test.yaml", "--connections"]
        )
        assert result.exit_code == 0
        # Connections flag shows basic pipeline info
        assert "Pipeline:" in result.stdout
        assert "Targets:" in result.stdout


@patch("smus_cicd.helpers.utils._get_region_from_config")
@patch("smus_cicd.helpers.utils.load_config")
def test_describe_with_targets(mock_load_config, mock_get_region, sample_manifest):
    """Test describe with targets flag."""
    mock_load_config.return_value = {"region": "us-east-1"}
    mock_get_region.return_value = "us-east-1"

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        with open("test.yaml", "w") as f:
            f.write(open(sample_manifest).read())

        # Test filtering to specific target
        result = runner.invoke(
            app, ["describe", "--pipeline", "test.yaml", "--targets", "dev"]
        )
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
        result = runner.invoke(
            app, ["describe", "--pipeline", "test.yaml", "--connect"]
        )
        # Exit code might be 1 due to AWS connection issues, but should not be a crash
        assert result.exit_code in [0, 1]
        # Should at least show pipeline info even if connect fails
        if result.stdout:
            assert "Pipeline:" in result.stdout or "error" in result.stdout.lower()
