"""Unit tests for monitor command exit codes."""

import pytest
import typer
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from smus_cicd.cli import app


class TestMonitorCommandExitCodes:
    """Test exit codes for monitor command failure scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_invalid_manifest_returns_exit_code_1(self):
        """Test that monitor command returns exit code 1 when manifest file is invalid."""
        result = self.runner.invoke(app, ["monitor", "--pipeline", "nonexistent.yaml"])

        # Verify exit code 1
        assert result.exit_code == 1

    def test_invalid_target_returns_exit_code_1(self):
        """Test that monitor command returns exit code 1 when target doesn't exist."""
        # Create a temporary valid manifest file
        import tempfile
        import os

        manifest_content = """
pipelineName: test-pipeline

targets:
  dev:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: DEV
    project:
      name: dev-project
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(manifest_content)
            temp_file = f.name

        try:
            result = self.runner.invoke(
                app, ["monitor", "--pipeline", temp_file, "--targets", "nonexistent"]
            )

            # Verify exit code 1
            assert result.exit_code == 1
            assert "Target 'nonexistent' not found" in result.stderr
        finally:
            os.unlink(temp_file)
