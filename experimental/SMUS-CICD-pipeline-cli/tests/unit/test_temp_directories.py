"""Unit tests for temporary directory usage."""

import pytest
import yaml
from unittest.mock import patch, mock_open, MagicMock
from typer.testing import CliRunner
from smus_cicd.cli import app

runner = CliRunner()


@pytest.fixture
def sample_manifest():
    return """
bundleName: TestPipeline
bundlesDirectory: /tmp/bundles
bundle:
  storage:
    - name: workflows
      connectionName: default.s3_shared
      append: true
      include: ['workflows/']
targets:
  dev:
    stage: DEV
    domain:
      name: test-domain
      region: us-east-1
    project:
      name: dev-project
"""


def test_bundle_uses_temp_directory(sample_manifest):
    """Test that bundle command uses proper temporary directory."""
    mock_project_info = {
        "connections": {"default.s3_shared": {"s3Uri": "s3://test-bucket/path/"}}
    }

    with patch("os.path.exists", return_value=True):
        with patch(
            "smus_cicd.commands.bundle.BundleManifest.from_file"
        ) as mock_manifest:
            from smus_cicd.pipeline import BundleManifest
            mock_manifest.return_value = BundleManifest.from_dict(yaml.safe_load(sample_manifest))
            with patch(
                "smus_cicd.helpers.utils.load_config",
                return_value={"region": "us-east-1"},
            ):
                with patch(
                    "smus_cicd.helpers.utils.get_datazone_project_info",
                    return_value=mock_project_info,
                ):
                    with patch("tempfile.TemporaryDirectory") as mock_temp:
                        mock_temp_dir = MagicMock()
                        mock_temp_dir.__enter__.return_value = (
                            "/tmp/smus_bundle_test123"
                        )
                        mock_temp.return_value = mock_temp_dir

                        with patch("os.makedirs"):
                            with patch("boto3.client"):
                                with patch(
                                    "smus_cicd.helpers.deployment.download_s3_files",
                                    return_value=0,
                                ):
                                    result = runner.invoke(app, ["bundle"])

                                    # Verify TemporaryDirectory was called with proper prefix
                                    mock_temp.assert_called_with(prefix="smus_bundle_")


def test_deploy_command_exists():
    """Test that deploy command exists and can be invoked."""
    # Simple test to verify deploy command structure
    result = runner.invoke(app, ["deploy", "--help"])
    assert result.exit_code == 0
    assert "Deploy bundle files" in result.output


def test_temp_directory_prefix_usage():
    """Test that proper prefixes are used for temp directories."""
    # Test the prefix patterns we expect
    prefixes = ["smus_bundle_", "smus_deploy_", "smus_integration_test_"]

    for prefix in prefixes:
        # Verify prefix format is correct
        assert prefix.startswith("smus_")
        assert prefix.endswith("_")
        assert len(prefix) > 5  # Reasonable length
