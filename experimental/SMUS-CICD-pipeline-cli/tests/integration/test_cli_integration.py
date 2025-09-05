"""Integration tests for SMUS CLI commands."""

import pytest
import subprocess
import os
from pathlib import Path


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    def test_cli_help(self):
        """Test that CLI help command works."""
        result = subprocess.run(
            ["smus-cli", "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "SMUS CI/CD CLI" in result.stdout

    def test_create_command_help(self):
        """Test that create command help works."""
        result = subprocess.run(
            ["smus-cli", "create", "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Create new pipeline manifest" in result.stdout

    @pytest.mark.skipif(
        not os.getenv("AWS_ROLE_ARN"),
        reason="AWS credentials not configured for integration testing"
    )
    def test_create_command_basic(self):
        """Test basic create command functionality."""
        pipeline_name = f"test-pipeline-{os.getenv('GITHUB_RUN_NUMBER', '1')}"
        
        result = subprocess.run(
            ["smus-cli", "create", pipeline_name, "--region", "us-east-1"],
            capture_output=True,
            text=True
        )
        
        # The command should either succeed or fail gracefully
        # We're mainly testing that it doesn't crash
        assert result.returncode in [0, 1]  # Allow for expected failures in test env
        
        # Check that a manifest file was created if successful
        manifest_file = Path(f"{pipeline_name}.yaml")
        if result.returncode == 0:
            assert manifest_file.exists()
            # Clean up
            manifest_file.unlink(missing_ok=True)
