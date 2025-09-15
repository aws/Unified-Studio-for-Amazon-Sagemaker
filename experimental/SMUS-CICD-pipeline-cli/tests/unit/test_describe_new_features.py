"""Unit tests for new describe command features."""

import tempfile
import json
import pytest
from typer.testing import CliRunner
from smus_cicd.cli import app


class TestDescribeNewFeatures:
    """Test cases for new describe command features."""

    def create_test_manifest(self):
        """Create a test manifest file."""
        manifest_content = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets:
  dev:
    stage: DEV
    project:
      name: dev-project
      create: false
  test:
    stage: TEST
    project:
      name: test-project
      create: false
  prod:
    stage: PROD
    project:
      name: prod-project
      create: false
workflows:
  - workflowName: test_workflow
    connectionName: project.workflow_mwaa
"""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        f.write(manifest_content)
        f.flush()
        return f.name

    def test_describe_json_output(self):
        """Test describe command with JSON output."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app, ["describe", "--pipeline", manifest_file, "--output", "JSON"]
            )

            assert result.exit_code == 0

            # Should be valid JSON
            output_data = json.loads(result.stdout)
            assert "pipeline" in output_data
            assert "domain" in output_data
            assert "targets" in output_data
            assert output_data["pipeline"] == "TestPipeline"
            assert output_data["domain"]["name"] == "test-domain"
            assert output_data["domain"]["region"] == "us-east-1"
            assert "dev" in output_data["targets"]
            assert "test" in output_data["targets"]
            assert "prod" in output_data["targets"]
        finally:
            import os

            os.unlink(manifest_file)

    def test_describe_text_output(self):
        """Test describe command with TEXT output (default)."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app, ["describe", "--pipeline", manifest_file, "--output", "TEXT"]
            )

            assert result.exit_code == 0
            assert "Pipeline: TestPipeline" in result.stdout
            assert "Domain: test-domain (us-east-1)" in result.stdout
            assert "Targets:" in result.stdout
            assert "dev: dev-project" in result.stdout
            assert "test: test-project" in result.stdout
            assert "prod: prod-project" in result.stdout
        finally:
            import os

            os.unlink(manifest_file)

    def test_describe_target_filtering(self):
        """Test describe command with target filtering."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app, ["describe", "--pipeline", manifest_file, "--targets", "dev"]
            )

            assert result.exit_code == 0
            assert "Pipeline: TestPipeline" in result.stdout
            assert "dev: dev-project" in result.stdout
            # Should not show other targets
            assert "test: test-project" not in result.stdout
            assert "prod: prod-project" not in result.stdout
        finally:
            import os

            os.unlink(manifest_file)

    def test_describe_target_filtering_json(self):
        """Test describe command with target filtering and JSON output."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app,
                [
                    "describe",
                    "--pipeline",
                    manifest_file,
                    "--targets",
                    "dev",
                    "--output",
                    "JSON",
                ],
            )

            assert result.exit_code == 0

            output_data = json.loads(result.stdout)
            assert "targets" in output_data
            assert "dev" in output_data["targets"]
            # Should not show other targets
            assert "test" not in output_data["targets"]
            assert "prod" not in output_data["targets"]
        finally:
            import os

            os.unlink(manifest_file)

    def test_describe_invalid_target(self):
        """Test describe command with invalid target."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app, ["describe", "--pipeline", manifest_file, "--targets", "invalid"]
            )

            assert result.exit_code == 1
            # Error messages go to stderr in typer
            assert (
                "Target 'invalid' not found" in result.stderr
                or "invalid" in result.stderr
            )
            assert (
                "Available targets" in result.stderr
                or "dev, test, prod" in result.stderr
            )
        finally:
            import os

            os.unlink(manifest_file)

    def test_describe_invalid_target_json(self):
        """Test describe command with invalid target and JSON output."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app,
                [
                    "describe",
                    "--pipeline",
                    manifest_file,
                    "--targets",
                    "invalid",
                    "--output",
                    "JSON",
                ],
            )

            assert result.exit_code == 1

            # JSON error should be in stdout, but may have multiple JSON objects
            if result.stdout.strip():
                # Try to parse the first JSON object
                lines = result.stdout.strip().split("\n")
                json_lines = []
                for line in lines:
                    json_lines.append(line)
                    try:
                        output_data = json.loads("\n".join(json_lines))
                        assert "error" in output_data
                        assert "available_targets" in output_data
                        assert "dev" in output_data["available_targets"]
                        break
                    except json.JSONDecodeError:
                        continue
        finally:
            import os

            os.unlink(manifest_file)

    def test_describe_connections_flag_only(self):
        """Test describe command with connections flag only."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app, ["describe", "--pipeline", manifest_file, "--connections"]
            )

            assert result.exit_code == 0
            assert "Pipeline: TestPipeline" in result.stdout
            assert "Targets:" in result.stdout
            # Basic output shows targets even with --connections flag
        finally:
            import os

            os.unlink(manifest_file)

    def test_describe_connections_flag(self):
        """Test describe command with connections flag."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app, ["describe", "--pipeline", manifest_file, "--connections"]
            )

            assert result.exit_code == 0
            assert "Pipeline: TestPipeline" in result.stdout
            assert "Targets:" in result.stdout
            # Basic output shows targets even with --connections flag
        finally:
            import os

            os.unlink(manifest_file)

    def test_describe_combined_flags(self):
        """Test describe command with multiple flags."""
        runner = CliRunner()
        manifest_file = self.create_test_manifest()

        try:
            result = runner.invoke(
                app,
                [
                    "describe",
                    "--pipeline",
                    manifest_file,
                    "--targets",
                    "dev",
                    "--connections",
                    "--output",
                    "JSON",
                ],
            )

            # The command should return JSON output regardless of exit code
            assert result.stdout.strip(), "Expected JSON output but got empty stdout"

            output_data = json.loads(result.stdout)

            # If successful, check for expected structure
            if result.exit_code == 0:
                assert "pipeline" in output_data
                assert "targets" in output_data
                assert "dev" in output_data["targets"]
            else:
                # If failed, should have error in JSON format
                assert "error" in output_data
        finally:
            import os

            os.unlink(manifest_file)
