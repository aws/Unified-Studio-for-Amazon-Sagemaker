"""Unit tests for create command."""

import os
import tempfile
import pytest
import re
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from smus_cicd.cli import app


def strip_ansi_codes(text):
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class TestCreateCommand:
    """Test cases for create command functionality."""

    def test_create_basic_manifest(self):
        """Test creating a basic manifest with default values."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "tests/fixtures/test-manifest.yaml"

            result = runner.invoke(app, ["create", "--output", output_file])

            assert result.exit_code == 0
            assert "Pipeline manifest created" in result.stdout
            assert "YourPipelineName" in result.stdout
            assert os.path.exists(output_file)

            # Verify file content
            with open(output_file, "r") as f:
                content = f.read()
                assert "applicationName: YourPipelineName" in content
                assert "domain:" in content
                assert "stages:" in content
                assert "dev:" in content
                assert "test:" in content
                assert "prod:" in content

    def test_create_with_custom_name(self):
        """Test creating manifest with custom pipeline name."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "custom-bundle.yaml"
            bundle_name = "MyCustomPipeline"

            result = runner.invoke(
                app, ["create", "--output", output_file, "--name", bundle_name]
            )

            assert result.exit_code == 0
            assert f"Bundle name: {bundle_name}" in result.stdout
            assert os.path.exists(output_file)

            # Verify custom name in file
            with open(output_file, "r") as f:
                content = f.read()
                assert f"applicationName: {bundle_name}" in content

    def test_create_with_custom_stages(self):
        """Test creating manifest with custom stages."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "custom-stages.yaml"

            result = runner.invoke(
                app, ["create", "--output", output_file, "--stages", "dev,staging,prod"]
            )

            assert result.exit_code == 0
            assert "Stages: dev, staging, prod" in result.stdout
            assert os.path.exists(output_file)

            # Verify custom stages in file
            with open(output_file, "r") as f:
                content = f.read()
                assert "dev:" in content
                assert "staging:" in content
                assert "prod:" in content
                assert "stage: STAGING" in content

    def test_create_with_custom_region(self):
        """Test creating manifest with custom region."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "custom-region.yaml"

            result = runner.invoke(
                app, ["create", "--output", output_file, "--region", "us-west-2"]
            )

            assert result.exit_code == 0
            assert os.path.exists(output_file)

            # Verify custom region in file
            with open(output_file, "r") as f:
                content = f.read()
                assert "region: ${DEV_DOMAIN_REGION:us-west-2}" in content

    @patch("smus_cicd.commands.create.boto3.client")
    def test_create_with_aws_resources(self, mock_boto3_client):
        """Test creating manifest with AWS domain and project validation."""
        # Mock DataZone client responses
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        mock_client.get_domain.return_value = {"name": "test-domain"}
        mock_client.get_project.return_value = {"name": "dev-test-project"}

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "aws-bundle.yaml"

            result = runner.invoke(
                app,
                [
                    "create",
                    "--output",
                    output_file,
                    "--name",
                    "AWSPipeline",
                    "--domain-id",
                    "<domain-id>",
                    "--dev-project-id",
                    "<project-id>",
                    "--region",
                    "us-east-1",
                ],
            )

            assert result.exit_code == 0
            assert "Found domain: test-domain" in result.stdout
            assert "Found dev project: dev-test-project" in result.stdout
            assert os.path.exists(output_file)

            # Verify AWS resources in file
            with open(output_file, "r") as f:
                content = f.read()
                assert "name: test-domain" in content
                assert "name: dev-test-project" in content
                assert (
                    "name: dev-test-project-test" in content
                )  # synthesized test project
                assert (
                    "name: dev-test-project-prod" in content
                )  # synthesized prod project

    @patch("smus_cicd.commands.create.boto3.client")
    def test_create_with_domain_and_project_no_warnings(self, mock_boto3_client):
        """Test creating manifest with domain and project IDs produces no warnings."""
        # Mock DataZone client
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        # Mock domain response
        mock_client.get_domain.return_value = {
            "name": "test-domain",
            "id": "<domain-id>",
        }

        # Mock project response
        mock_client.get_project.return_value = {
            "name": "dev-test-project",
            "id": "<project-id>",
        }

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "test-manifest.yaml"

            result = runner.invoke(
                app,
                [
                    "create",
                    "--output",
                    output_file,
                    "--name",
                    "TestPipeline",
                    "--domain-id",
                    "<domain-id>",
                    "--dev-project-id",
                    "<project-id>",
                ],
            )

            assert result.exit_code == 0
            # Verify no warnings are present
            assert "⚠️" not in result.stdout
            assert "validation failed" not in result.stdout.lower()
            # Verify successful validation
            assert "✅ Manifest validation successful!" in result.stdout
            assert os.path.exists(output_file)

            # Verify file content has target-level domain configuration
            with open(output_file, "r") as f:
                content = f.read()
                assert "stages:" in content
                # Check no top-level domain configuration
                lines = content.split("\n")
                in_targets = False
                for line in lines:
                    stripped = line.strip()
                    if stripped == "stages:":
                        in_targets = True
                    elif not line.startswith(" ") and stripped and stripped != "---":  # New top-level key
                        in_targets = False
                    if not in_targets and stripped == "domain:":  # Only check outside targets section
                        assert False, "Found top-level domain configuration"
                # Check domain configuration exists under each target
                for stage in ["dev", "test", "prod"]:
                    assert f"{stage}:" in content
                    assert f"  {stage}:\n    domain:" in content  # Domain under target

    @patch("smus_cicd.commands.create.boto3.client")
    def test_create_with_aws_domain_error(self, mock_boto3_client):
        """Test creating manifest with invalid AWS domain."""
        # Mock DataZone client to raise error
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        from botocore.exceptions import ClientError

        mock_client.get_domain.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Domain not found",
                }
            },
            "GetDomain",
        )

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "error-bundle.yaml"

            result = runner.invoke(
                app,
                [
                    "create",
                    "--output",
                    output_file,
                    "--domain-id",
                    "invalid-domain",
                    "--dev-project-id",
                    "<project-id>",
                ],
            )

            assert result.exit_code == 0  # Command succeeds but shows warning
            # Check both stdout and stderr for error message
            error_output = result.stdout + result.stderr
            assert "AWS Error:" in error_output or "Domain not found" in error_output
            assert os.path.exists(output_file)  # File is still created

    @patch("smus_cicd.commands.create.boto3.client")
    def test_create_with_aws_project_error(self, mock_boto3_client):
        """Test creating manifest with invalid AWS project."""
        # Mock DataZone client responses
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        mock_client.get_domain.return_value = {"name": "test-domain"}

        from botocore.exceptions import ClientError

        mock_client.get_project.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Project not found",
                }
            },
            "GetProject",
        )

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "error-bundle.yaml"

            result = runner.invoke(
                app,
                [
                    "create",
                    "--output",
                    output_file,
                    "--domain-id",
                    "<domain-id>",
                    "--dev-project-id",
                    "invalid-project",
                ],
            )

            assert result.exit_code == 0  # Command succeeds but shows warning
            # Check both stdout and stderr for error message
            error_output = result.stdout + result.stderr
            assert "AWS Error:" in error_output or "Project not found" in error_output
            assert os.path.exists(output_file)  # File is still created

    def test_create_with_nested_directory(self):
        """Test creating manifest in nested directory."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "nested/dir/bundle.yaml"

            result = runner.invoke(app, ["create", "--output", output_file])

            assert result.exit_code == 0
            assert os.path.exists(output_file)

    def test_create_manifest_is_valid(self):
        """Test that created manifest can be described without errors."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "valid-bundle.yaml"

            # Create manifest
            create_result = runner.invoke(app, ["create", "--output", output_file])
            assert create_result.exit_code == 0

            # Verify it can be described
            describe_result = runner.invoke(
                app, ["describe", "--manifest", output_file]
            )
            assert describe_result.exit_code == 0
            assert "Pipeline:" in describe_result.stdout

    def test_create_manifest_contains_required_fields(self):
        """Test that created manifest contains all required fields."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "required-fields.yaml"

            result = runner.invoke(app, ["create", "--output", output_file])
            assert result.exit_code == 0

            with open(output_file, "r") as f:
                content = f.read()
                # Required fields
                assert "applicationName:" in content
                assert "domain:" in content
                assert "name:" in content  # domain name
                assert "${DEV_DOMAIN_REGION:" in content  # parameterized region
                assert "stages:" in content

                # Optional fields (commented)
                assert "# Application content configuration" in content
                assert "# initialization:" in content

                # Placeholder indicators
                assert "PLACEHOLDER" in content

    def test_create_project_name_synthesis(self):
        """Test project name synthesis logic."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "synthesis-test.yaml"

            result = runner.invoke(
                app,
                ["create", "--output", output_file, "--stages", "dev,qa,production"],
            )

            assert result.exit_code == 0

            with open(output_file, "r") as f:
                content = f.read()
                assert "dev:" in content
                assert "qa:" in content
                assert "production:" in content
                assert "stage: QA" in content
                assert "stage: PRODUCTION" in content

    def test_create_help_message(self):
        """Test create command help message."""
        runner = CliRunner()
        result = runner.invoke(app, ["create", "--help"])

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "Create new pipeline manifest" in clean_output
        assert "--output" in clean_output
        assert "--name" in clean_output
        assert "--domain-id" in clean_output
        assert "--dev-project-id" in clean_output
        assert "--stages" in clean_output
        assert "--region" in clean_output

    def test_create_default_stages(self):
        """Test that default stages are dev,test,prod."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            output_file = "default-stages.yaml"

            result = runner.invoke(app, ["create", "--output", output_file])

            assert result.exit_code == 0
            assert "Stages: dev, test, prod" in result.stdout

            with open(output_file, "r") as f:
                content = f.read()
                assert "dev:" in content
                assert "test:" in content
                assert "prod:" in content
                assert "stage: DEV" in content  # DEV stage is the default target
