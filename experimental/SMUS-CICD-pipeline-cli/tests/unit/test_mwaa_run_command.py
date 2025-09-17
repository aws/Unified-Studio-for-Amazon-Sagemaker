"""Unit tests for MWAA run_airflow_command function."""

import pytest
from unittest.mock import patch, MagicMock
from smus_cicd.helpers import mwaa


class TestMWAARunCommand:
    """Test cases for MWAA run_airflow_command function."""

    @patch("smus_cicd.helpers.mwaa.boto3_client.create_client")
    @patch("requests.post")
    def test_run_airflow_command_success(self, mock_post, mock_create_client):
        """Test successful Airflow command execution."""
        # Mock MWAA client
        mock_client = MagicMock()
        mock_client.create_cli_token.return_value = {
            "CliToken": "test-token",
            "WebServerHostname": "test-hostname",
        }
        mock_create_client.return_value = mock_client

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stdout": "dGVzdCBvdXRwdXQ=",  # base64 encoded "test output"
            "stderr": "",
        }
        mock_post.return_value = mock_response

        # Execute function
        result = mwaa.run_airflow_command("test-env", "dags list", "us-east-1")

        # Verify result
        assert result["success"] is True
        assert result["command"] == "dags list"
        assert result["environment"] == "test-env"
        assert result["status_code"] == 200
        assert result["stdout"] == "test output"
        assert result["stderr"] == ""

        # Verify API calls
        mock_client.create_cli_token.assert_called_once_with(Name="test-env")
        mock_post.assert_called_once()

    @patch("smus_cicd.helpers.mwaa.boto3_client.create_client")
    @patch("requests.post")
    def test_run_airflow_command_with_stderr(self, mock_post, mock_create_client):
        """Test Airflow command execution with stderr output."""
        # Mock MWAA client
        mock_client = MagicMock()
        mock_client.create_cli_token.return_value = {
            "CliToken": "test-token",
            "WebServerHostname": "test-hostname",
        }
        mock_create_client.return_value = mock_client

        # Mock response with stderr
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stdout": "dGVzdCBvdXRwdXQ=",  # base64 encoded "test output"
            "stderr": "dGVzdCBlcnJvcg==",  # base64 encoded "test error"
        }
        mock_post.return_value = mock_response

        # Execute function
        result = mwaa.run_airflow_command("test-env", "invalid command", "us-east-1")

        # Verify result
        assert result["success"] is True
        assert result["stdout"] == "test output"
        assert result["stderr"] == "test error"

    @patch("smus_cicd.helpers.mwaa.boto3_client.create_client")
    @patch("requests.post")
    def test_run_airflow_command_http_error(self, mock_post, mock_create_client):
        """Test Airflow command execution with HTTP error."""
        # Mock MWAA client
        mock_client = MagicMock()
        mock_client.create_cli_token.return_value = {
            "CliToken": "test-token",
            "WebServerHostname": "test-hostname",
        }
        mock_create_client.return_value = mock_client

        # Mock HTTP error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        # Execute function
        result = mwaa.run_airflow_command("test-env", "dags list", "us-east-1")

        # Verify result
        assert result["success"] is False
        assert result["status_code"] == 500
        assert "HTTP 500" in result["stderr"]
        assert result["stdout"] == ""

    @patch("smus_cicd.helpers.mwaa.boto3_client.create_client")
    def test_run_airflow_command_token_error(self, mock_create_client):
        """Test Airflow command execution with token creation error."""
        # Mock MWAA client that raises exception
        mock_client = MagicMock()
        mock_client.create_cli_token.side_effect = Exception("Token creation failed")
        mock_create_client.return_value = mock_client

        # Execute function
        result = mwaa.run_airflow_command("test-env", "dags list", "us-east-1")

        # Verify result
        assert result["success"] is False
        assert result["status_code"] is None
        assert "Token creation failed" in result["stderr"]
        assert result["stdout"] == ""

    @patch("smus_cicd.helpers.mwaa.boto3_client.create_client")
    @patch("requests.post")
    def test_run_airflow_command_timeout(self, mock_post, mock_create_client):
        """Test Airflow command execution with timeout."""
        # Mock MWAA client
        mock_client = MagicMock()
        mock_client.create_cli_token.return_value = {
            "CliToken": "test-token",
            "WebServerHostname": "test-hostname",
        }
        mock_create_client.return_value = mock_client

        # Mock timeout exception
        import requests

        mock_post.side_effect = requests.Timeout("Request timed out")

        # Execute function
        result = mwaa.run_airflow_command("test-env", "dags list", "us-east-1")

        # Verify result
        assert result["success"] is False
        assert "Request timed out" in result["stderr"]

    @patch("smus_cicd.helpers.mwaa.boto3_client.create_client")
    @patch("requests.post")
    def test_run_airflow_command_various_commands(self, mock_post, mock_create_client):
        """Test various Airflow commands."""
        # Mock MWAA client
        mock_client = MagicMock()
        mock_client.create_cli_token.return_value = {
            "CliToken": "test-token",
            "WebServerHostname": "test-hostname",
        }
        mock_create_client.return_value = mock_client

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stdout": "c3VjY2Vzcw==",  # base64 encoded "success"
            "stderr": "",
        }
        mock_post.return_value = mock_response

        # Test various commands
        commands = [
            "dags list",
            "dags state test_dag",
            "tasks list test_dag",
            "dags trigger test_dag",
            "version",
            "dags show test_dag",
        ]

        for command in commands:
            result = mwaa.run_airflow_command("test-env", command, "us-east-1")

            assert result["success"] is True
            assert result["command"] == command
            assert result["stdout"] == "success"

    def test_run_airflow_command_result_structure(self):
        """Test that run_airflow_command returns correct result structure."""
        with patch(
            "smus_cicd.helpers.mwaa.boto3_client.create_client"
        ) as mock_create_client:
            mock_client = MagicMock()
            mock_client.create_cli_token.side_effect = Exception("Test error")
            mock_create_client.return_value = mock_client

            result = mwaa.run_airflow_command("test-env", "test command", "us-east-1")

            # Verify all required keys are present
            required_keys = [
                "command",
                "environment",
                "status_code",
                "stdout",
                "stderr",
                "success",
            ]
            for key in required_keys:
                assert key in result

            # Verify types
            assert isinstance(result["command"], str)
            assert isinstance(result["environment"], str)
            assert isinstance(result["stdout"], str)
            assert isinstance(result["stderr"], str)
            assert isinstance(result["success"], bool)
