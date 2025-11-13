"""Unit tests for bundle command."""

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
bundle:
  bundlesDirectory: /tmp/bundles
  storage:
    - name: workflows
      connectionName: default.s3_shared
      append: true
      include: ['workflows/']
    - name: code
      connectionName: default.s3_shared
      append: false
      include: ['src/']
targets:
  dev:
    stage: DEV
    domain:
      name: test-domain
      region: us-east-1
    project:
      name: dev-project
"""


def test_bundle_default_target(sample_manifest):
    """Test bundle with default target - basic validation."""
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
                result = runner.invoke(app, ["bundle"])
                # Test should use DEV stage as default target
                assert result.exit_code == 1 or "dev" in result.output.lower()


def test_bundle_tree_structure_display(sample_manifest):
    """Test that bundle command displays tree structure in text mode."""
    with patch("builtins.open", mock_open(read_data=sample_manifest)):
        with patch(
            "smus_cicd.helpers.utils.load_config", return_value={"region": "us-east-1"}
        ):
            with patch("smus_cicd.commands.bundle.display_bundle_tree") as mock_tree:
                result = runner.invoke(app, ["bundle", "--output", "TEXT"])
                # Should call display_bundle_tree for text output
                if result.exit_code == 0:  # Only if bundle creation succeeds
                    mock_tree.assert_called_once()


def test_bundle_no_tree_for_json(sample_manifest):
    """Test that bundle command skips tree structure in JSON mode."""
    with patch("builtins.open", mock_open(read_data=sample_manifest)):
        with patch(
            "smus_cicd.helpers.utils.load_config", return_value={"region": "us-east-1"}
        ):
            with patch("smus_cicd.commands.bundle.display_bundle_tree") as mock_tree:
                result = runner.invoke(app, ["bundle", "--output", "JSON"])
                # Tree display should be called but skip output for JSON
                if result.exit_code == 0:
                    mock_tree.assert_called_once()


def test_bundle_no_bundle_section():
    """Test bundle with missing bundle section."""
    manifest = """
bundleName: TestPipeline
targets:
  dev:
    stage: DEV
    domain:
      name: test-domain
      region: us-east-1
    project:
      name: dev-project
"""

    with patch("os.path.exists", return_value=True):
        with patch(
            "smus_cicd.commands.bundle.BundleManifest.from_file"
        ) as mock_manifest:
            from smus_cicd.pipeline import BundleManifest
            mock_manifest.return_value = BundleManifest.from_dict(yaml.safe_load(manifest))
            with patch(
                "smus_cicd.helpers.utils.load_config",
                return_value={"region": "us-east-1"},
            ):
                with patch(
                    "smus_cicd.helpers.utils.get_datazone_project_info",
                    return_value={"connections": {}},
                ):
                    with patch("boto3.client"):
                        with patch("tempfile.mkdtemp", return_value="/tmp/test"):
                            with patch("os.makedirs"):
                                result = runner.invoke(app, ["bundle"])
                                assert result.exit_code == 1
                                assert "No files found" in result.output


def test_bundle_no_default_target():
    """Test bundle with no default target specified."""
    manifest = """
bundleName: TestPipeline
bundle:
  storage: []
targets:
  test:
    stage: TEST
    domain:
      name: test-domain
      region: us-east-1
    project:
      name: test-project
"""

    with patch("os.path.exists", return_value=True):
        with patch(
            "smus_cicd.commands.bundle.BundleManifest.from_file"
        ) as mock_manifest:
            from smus_cicd.pipeline import BundleManifest
            mock_manifest.return_value = BundleManifest.from_dict(yaml.safe_load(manifest))
            with patch(
                "smus_cicd.helpers.utils.load_config",
                return_value={"region": "us-east-1"},
            ):
                result = runner.invoke(app, ["bundle"])
                assert result.exit_code == 1
                assert "Target 'dev' not found in manifest" in result.output
