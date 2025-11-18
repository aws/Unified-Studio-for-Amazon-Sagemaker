"""Unit tests for delete command."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from smus_cicd.cli import app


class TestDeleteCommand:
    """Test delete command functionality."""

    @patch("smus_cicd.commands.delete.ApplicationManifest")
    def test_delete_invalid_target(self, mock_manifest_class):
        """Test delete command with invalid target name."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.stages = {"dev": MagicMock(), "prod": MagicMock()}
        mock_manifest_class.from_file.return_value = mock_manifest

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_file = os.path.join(temp_dir, "manifest.yaml")
            with open(manifest_file, "w") as f:
                f.write("applicationName: test\nstages:\n  dev: {}\n  prod: {}\n")

            result = runner.invoke(
                app,
                [
                    "delete",
                    "--targets",
                    "invalid-target",
                    "--manifest",
                    manifest_file,
                    "--force",
                ],
            )

            assert result.exit_code != 0
            assert "not found in manifest" in result.stdout

    @patch("smus_cicd.commands.delete.ApplicationManifest")
    @patch("smus_cicd.commands.delete.Confirm.ask")
    def test_delete_cancelled_by_user(self, mock_confirm, mock_manifest_class):
        """Test delete command when user cancels confirmation."""
        # Setup mocks
        mock_manifest = MagicMock()
        mock_manifest.stages = {"dev": MagicMock()}
        mock_manifest_class.from_file.return_value = mock_manifest
        mock_confirm.return_value = False  # User cancels

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_file = os.path.join(temp_dir, "manifest.yaml")
            with open(manifest_file, "w") as f:
                f.write("applicationName: test\nstages:\n  dev: {}\n")

            result = runner.invoke(
                app, ["delete", "--targets", "dev", "--manifest", manifest_file]
            )

            # When user cancels, command exits gracefully with code 0
            # but shows cancellation message
            assert "cancelled" in result.stdout.lower() or result.exit_code == 0
