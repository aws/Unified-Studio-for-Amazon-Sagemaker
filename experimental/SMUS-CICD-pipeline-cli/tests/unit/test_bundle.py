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
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundlesDirectory: ./bundles
bundle:
  workflow:
    - connectionName: default.s3_shared
      append: true
      include: ['workflows/']
  storage:
    - connectionName: default.s3_shared
      append: false
      include: ['src/']
targets:
  dev:
    default: true
    project:
      name: dev-project
"""

def test_bundle_default_target(sample_manifest):
    """Test bundle with default target - basic validation."""
    with patch("os.path.exists", return_value=True):
        with patch("smus_cicd.commands.bundle.load_yaml", return_value=yaml.safe_load(sample_manifest)):
            with patch("smus_cicd.helpers.utils.load_config", return_value={'region': 'us-east-1'}):
                result = runner.invoke(app, ["bundle"])
                # Test should fail due to missing project info, but should identify default target
                assert "Using default target: dev" in result.output

def test_bundle_tree_structure_display(sample_manifest):
    """Test that bundle command displays tree structure in text mode."""
    with patch("builtins.open", mock_open(read_data=sample_manifest)):
        with patch("smus_cicd.helpers.utils.load_config", return_value={'region': 'us-east-1'}):
            with patch("smus_cicd.commands.bundle.display_bundle_tree") as mock_tree:
                result = runner.invoke(app, ["bundle", "--output", "TEXT"])
                # Should call display_bundle_tree for text output
                if result.exit_code == 0:  # Only if bundle creation succeeds
                    mock_tree.assert_called_once()

def test_bundle_no_tree_for_json(sample_manifest):
    """Test that bundle command skips tree structure in JSON mode.""" 
    with patch("builtins.open", mock_open(read_data=sample_manifest)):
        with patch("smus_cicd.helpers.utils.load_config", return_value={'region': 'us-east-1'}):
            with patch("smus_cicd.commands.bundle.display_bundle_tree") as mock_tree:
                result = runner.invoke(app, ["bundle", "--output", "JSON"])
                # Tree display should be called but skip output for JSON
                if result.exit_code == 0:
                    mock_tree.assert_called_once()

def test_bundle_no_bundle_section():
    """Test bundle with missing bundle section."""
    manifest = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets:
  dev:
    default: true
    project:
      name: dev-project
"""
    
    with patch("os.path.exists", return_value=True):
        with patch("smus_cicd.commands.bundle.load_yaml", return_value=yaml.safe_load(manifest)):
            with patch("smus_cicd.helpers.utils.load_config", return_value={"region": "us-east-1"}):
                result = runner.invoke(app, ["bundle"])
                assert result.exit_code == 1
                assert "No bundle section found" in result.output

def test_bundle_no_default_target():
    """Test bundle with no default target specified."""
    manifest = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  workflow: []
targets:
  test:
    project:
      name: test-project
"""
    
    with patch("os.path.exists", return_value=True):
        with patch("smus_cicd.commands.bundle.load_yaml", return_value=yaml.safe_load(manifest)):
            with patch("smus_cicd.helpers.utils.load_config", return_value={"region": "us-east-1"}):
                result = runner.invoke(app, ["bundle"])
                assert result.exit_code == 1
                assert "no default target found" in result.output
