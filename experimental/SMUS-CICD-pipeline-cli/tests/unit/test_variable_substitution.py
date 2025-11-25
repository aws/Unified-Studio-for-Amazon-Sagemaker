"""Unit tests for environment variable substitution."""
import os
import pytest
from unittest.mock import patch, MagicMock
from smus_cicd.helpers.utils import substitute_env_vars


class TestVariableSubstitution:
    """Test environment variable substitution functionality."""

    def test_substitute_simple_env_var(self):
        """Test substitution of a simple environment variable."""
        os.environ["TEST_VAR"] = "test_value"
        try:
            result = substitute_env_vars("${TEST_VAR}")
            assert result == "test_value"
        finally:
            del os.environ["TEST_VAR"]

    def test_substitute_env_var_in_string(self):
        """Test substitution within a larger string."""
        os.environ["TEST_VAR"] = "world"
        try:
            result = substitute_env_vars("Hello ${TEST_VAR}!")
            assert result == "Hello world!"
        finally:
            del os.environ["TEST_VAR"]

    def test_substitute_multiple_vars(self):
        """Test substitution of multiple variables."""
        os.environ["VAR1"] = "foo"
        os.environ["VAR2"] = "bar"
        try:
            result = substitute_env_vars("${VAR1} and ${VAR2}")
            assert result == "foo and bar"
        finally:
            del os.environ["VAR1"]
            del os.environ["VAR2"]

    def test_substitute_with_default_value(self):
        """Test substitution with default value when var not set."""
        result = substitute_env_vars("${NONEXISTENT_VAR:default_value}")
        assert result == "default_value"

    def test_substitute_with_empty_default(self):
        """Test substitution with empty default value."""
        result = substitute_env_vars("${NONEXISTENT_VAR:}")
        assert result == ""

    def test_substitute_missing_var_without_default_raises_error(self):
        """Test that missing variable without default raises ValueError."""
        with pytest.raises(ValueError, match="Variable.*MISSING_VAR.*is not set"):
            substitute_env_vars("${MISSING_VAR}")

    def test_substitute_in_dict(self):
        """Test substitution in dictionary values."""
        os.environ["TEST_VAR"] = "test_value"
        try:
            data = {"key1": "${TEST_VAR}", "key2": "static"}
            result = substitute_env_vars(data)
            assert result == {"key1": "test_value", "key2": "static"}
        finally:
            del os.environ["TEST_VAR"]

    def test_substitute_in_list(self):
        """Test substitution in list items."""
        os.environ["TEST_VAR"] = "test_value"
        try:
            data = ["${TEST_VAR}", "static", "${TEST_VAR}"]
            result = substitute_env_vars(data)
            assert result == ["test_value", "static", "test_value"]
        finally:
            del os.environ["TEST_VAR"]

    def test_substitute_in_nested_structure(self):
        """Test substitution in nested dict/list structure."""
        os.environ["TEST_VAR"] = "test_value"
        try:
            data = {
                "owners": ["${TEST_VAR}", "static_owner"],
                "config": {"key": "${TEST_VAR}"},
            }
            result = substitute_env_vars(data)
            assert result == {
                "owners": ["test_value", "static_owner"],
                "config": {"key": "test_value"},
            }
        finally:
            del os.environ["TEST_VAR"]

    @patch("boto3.client")
    def test_substitute_aws_account_id(self, mock_boto_client):
        """Test AWS_ACCOUNT_ID pseudo variable."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_boto_client.return_value = mock_sts

        result = substitute_env_vars("arn:aws:iam::${AWS_ACCOUNT_ID}:role/Admin")
        assert result == "arn:aws:iam::123456789012:role/Admin"

    @patch("boto3.client")
    def test_substitute_sts_account_id(self, mock_boto_client):
        """Test STS_ACCOUNT_ID pseudo variable (alias for AWS_ACCOUNT_ID)."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_boto_client.return_value = mock_sts

        result = substitute_env_vars("${STS_ACCOUNT_ID}")
        assert result == "123456789012"

    @patch("boto3.Session")
    def test_substitute_sts_region(self, mock_session_class):
        """Test STS_REGION pseudo variable."""
        mock_session = MagicMock()
        mock_session.region_name = "us-east-1"
        mock_session_class.return_value = mock_session

        result = substitute_env_vars("${STS_REGION}")
        assert result == "us-east-1"

    @patch("boto3.Session")
    def test_substitute_sts_region_with_default(self, mock_session_class):
        """Test STS_REGION with default when region not configured."""
        mock_session = MagicMock()
        mock_session.region_name = None
        mock_session_class.return_value = mock_session

        result = substitute_env_vars("${STS_REGION:us-west-2}")
        assert result == "us-west-2"

    @patch("boto3.Session")
    def test_substitute_sts_region_no_default_raises_error(self, mock_session_class):
        """Test STS_REGION without default raises error when not configured."""
        mock_session = MagicMock()
        mock_session.region_name = None
        mock_session_class.return_value = mock_session

        with pytest.raises(ValueError, match="Variable.*STS_REGION.*could not be resolved"):
            substitute_env_vars("${STS_REGION}")

    @patch("boto3.client")
    def test_manifest_owners_with_aws_account_id(self, mock_boto_client):
        """Test realistic manifest scenario with owners list."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "198737698272"}
        mock_boto_client.return_value = mock_sts

        manifest = {
            "project": {
                "owners": [
                    "Eng1",
                    "arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole",
                    "arn:aws:iam::${AWS_ACCOUNT_ID}:role/Admin",
                ]
            }
        }

        result = substitute_env_vars(manifest)
        assert result["project"]["owners"] == [
            "Eng1",
            "arn:aws:iam::198737698272:role/GitHubActionsRole",
            "arn:aws:iam::198737698272:role/Admin",
        ]

    def test_unresolved_variable_in_owners_raises_error(self):
        """Test that unresolved variable in owners list raises error."""
        manifest = {
            "project": {
                "owners": [
                    "Eng1",
                    "arn:aws:iam::${UNSET_ACCOUNT_ID}:role/Admin",
                ]
            }
        }

        with pytest.raises(ValueError, match="Variable.*UNSET_ACCOUNT_ID.*is not set"):
            substitute_env_vars(manifest)

    def test_non_string_values_unchanged(self):
        """Test that non-string values are not modified."""
        data = {"number": 123, "boolean": True, "none": None}
        result = substitute_env_vars(data)
        assert result == data
