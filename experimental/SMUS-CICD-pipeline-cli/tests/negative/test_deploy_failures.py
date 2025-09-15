"""Negative tests for deploy command - testing expected failure scenarios."""

import pytest
import tempfile
import os
from typer.testing import CliRunner
from smus_cicd.cli import app


class TestDeployFailures:
    """Test cases for deploy command failure scenarios."""

    def test_deploy_nonexistent_manifest(self):
        """Test deploy fails with nonexistent manifest file."""
        runner = CliRunner()
        result = runner.invoke(
            app, ["deploy", "--pipeline", "nonexistent.yaml", "--targets", "test"]
        )

        assert result.exit_code != 0
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_deploy_invalid_manifest(self):
        """Test deploy fails with invalid manifest file."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            invalid_manifest = f.name

        try:
            result = runner.invoke(
                app, ["deploy", "--pipeline", invalid_manifest, "--targets", "test"]
            )
            assert result.exit_code != 0
            assert (
                "error" in result.stderr.lower() or "invalid" in result.stderr.lower()
            )
        finally:
            os.unlink(invalid_manifest)

    def test_deploy_missing_target(self):
        """Test deploy fails when target doesn't exist in manifest."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets:
  dev:
    project:
      name: test-project
"""
            )
            manifest_file = f.name

        try:
            result = runner.invoke(
                app, ["deploy", "--pipeline", manifest_file, "--targets", "nonexistent"]
            )
            assert result.exit_code != 0
            assert (
                "not found" in result.stderr.lower() or "error" in result.stderr.lower()
            )
        finally:
            os.unlink(manifest_file)

    def test_deploy_project_create_false_nonexistent_project(self):
        """Test deploy fails when project doesn't exist and create=false."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets:
  test:
    stage: TEST
    project:
      name: nonexistent-project-12345
      create: false
    bundle_target_configuration:
      storage:
        connectionName: default.s3_shared
        directory: 'src'
"""
            )
            manifest_file = f.name

        try:
            result = runner.invoke(
                app, ["deploy", "--pipeline", manifest_file, "--targets", "test"]
            )
            assert result.exit_code != 0
            assert (
                "not found" in result.stderr.lower()
                and "create=false" in result.stderr.lower()
            )
        finally:
            os.unlink(manifest_file)
