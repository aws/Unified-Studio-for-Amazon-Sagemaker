"""Unit tests for monitor command."""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from typer.testing import CliRunner
from smus_cicd.cli import app

runner = CliRunner()


@pytest.fixture
def sample_manifest():
    return """
bundleName: TestPipeline
targets:
  dev:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: DEV
    project:
      name: dev-project
      create: false
  test:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: test-project
      create: false
workflows:
  - workflowName: global_workflow
    connectionName: project.workflow_mwaa
"""


def create_mock_manifest():
    """Create proper mock objects with attributes."""
    from unittest.mock import MagicMock
    
    mock_domain = MagicMock()
    mock_domain.name = "test-domain"
    mock_domain.region = "${DEV_DOMAIN_REGION:us-east-1}"

    mock_project_dev = MagicMock()
    mock_project_dev.name = "dev-project"
    mock_project_dev.create = False

    mock_project_test = MagicMock()
    mock_project_test.name = "test-project"
    mock_project_test.create = False

    mock_target_dev = MagicMock()
    mock_target_dev.project = mock_project_dev
    mock_target_dev.domain = mock_domain
    mock_target_dev.stage = "DEV"

    mock_target_test = MagicMock()
    mock_target_test.project = mock_project_test
    mock_target_test.domain = mock_domain
    mock_target_test.stage = "TEST"

    mock_manifest = MagicMock()
    mock_manifest.bundle_name = "TestPipeline"
    mock_manifest.targets = {"dev": mock_target_dev, "test": mock_target_test}
    mock_manifest.workflows = []
    mock_manifest.get_target_config = lambda target_name: mock_target_dev if target_name == "dev" else mock_target_test

    return mock_manifest


@patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
@patch("smus_cicd.helpers.utils.load_config")
@patch("smus_cicd.commands.monitor.get_datazone_project_info")
@patch("smus_cicd.pipeline.BundleManifest.from_file")
def test_monitor_all_targets(
    mock_from_file,
    mock_get_project_info,
    mock_load_config,
    mock_mwaa_health,
    sample_manifest,
):
    """Test monitor all targets - basic validation."""
    mock_load_config.return_value = {"region": "us-east-1"}

    mock_manifest = create_mock_manifest()
    mock_from_file.return_value = mock_manifest

    mock_get_project_info.return_value = {
        "status": "ACTIVE",
        "connections": {},
        "project_id": "test-project-id"
    }
    mock_mwaa_health.return_value = True  # Mock MWAA as healthy

    with patch("builtins.open", mock_open(read_data=sample_manifest)):
        result = runner.invoke(app, ["monitor", "--bundle", "test.yaml"])
        # Debug output
        if result.exit_code != 0:
            print(f"\nExit code: {result.exit_code}")
            print(f"Stdout: {result.stdout}")
            print(f"Stderr: {result.stderr}")
        # The command should succeed even if projects don't have project_id
        assert result.exit_code == 0
        assert "Pipeline: TestPipeline" in result.stdout


@patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
@patch("smus_cicd.helpers.utils.load_config")
@patch("smus_cicd.commands.monitor.get_datazone_project_info")
@patch("smus_cicd.pipeline.BundleManifest.from_file")
def test_monitor_single_target(
    mock_from_file,
    mock_get_project_info,
    mock_load_config,
    mock_mwaa_health,
    sample_manifest,
):
    """Test monitor single target."""
    mock_project_info = {
        "project_id": "test-id",
        "status": "ACTIVE",
        "connections": {
            "project.workflow_connection": {
                "connectionId": "conn-123",
                "type": "MWAA",
                "environmentName": "test-env",
            }
        },
    }

    mock_load_config.return_value = {"region": "us-east-1"}

    mock_manifest = create_mock_manifest()
    mock_from_file.return_value = mock_manifest

    mock_get_project_info.return_value = mock_project_info
    mock_mwaa_health.return_value = True  # Mock MWAA as healthy

    with patch("builtins.open", mock_open(read_data=sample_manifest)):
        result = runner.invoke(
            app, ["monitor", "--bundle", "test.yaml", "--targets", "dev"]
        )
        assert result.exit_code == 0
        assert "Pipeline: TestPipeline" in result.stdout
        assert "Target: dev" in result.stdout


@patch("smus_cicd.helpers.mwaa.validate_mwaa_health")
@patch("smus_cicd.helpers.utils.load_config")
@patch("smus_cicd.commands.monitor.get_datazone_project_info")
@patch("smus_cicd.pipeline.BundleManifest.from_file")
def test_monitor_inactive_project(
    mock_from_file,
    mock_get_project_info,
    mock_load_config,
    mock_mwaa_health,
    sample_manifest,
):
    """Test monitor with inactive project."""
    mock_project_info = {
        "project_id": "test-id",
        "status": "INACTIVE",
        "connections": {},
    }

    mock_load_config.return_value = {"region": "us-east-1"}

    mock_manifest = create_mock_manifest()
    mock_from_file.return_value = mock_manifest

    mock_get_project_info.return_value = mock_project_info
    mock_mwaa_health.return_value = False  # Mock MWAA as unhealthy

    with patch("builtins.open", mock_open(read_data=sample_manifest)):
        result = runner.invoke(
            app, ["monitor", "--bundle", "test.yaml", "--targets", "dev"]
        )
        assert result.exit_code == 1  # Should fail when no healthy MWAA environments
        assert "Pipeline: TestPipeline" in result.stdout
        assert "No healthy workflow environments found" in result.stdout


@patch("smus_cicd.helpers.utils.load_config")
@patch("smus_cicd.pipeline.BundleManifest.from_file")
def test_monitor_no_domain(mock_from_file, mock_load_config, sample_manifest):
    """Test monitor command with missing domain configuration."""
    mock_load_config.return_value = {}

    # Create manifest without domain
    mock_manifest = type(
        "MockManifest",
        (),
        {
            "bundle_name": "TestPipeline",
            "targets": {},
            "workflows": [],
        },
    )()
    mock_from_file.return_value = mock_manifest

    with patch("builtins.open", mock_open(read_data=sample_manifest)):
        result = runner.invoke(app, ["monitor", "--bundle", "test.yaml"])
        assert result.exit_code == 1  # Should fail without domain
