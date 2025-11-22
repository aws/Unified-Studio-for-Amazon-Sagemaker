"""Unit tests for environment variable substitution in utils."""

import os
import pytest
from unittest.mock import patch

from smus_cicd.helpers.utils import substitute_env_vars


class TestSubstituteEnvVars:
    """Test environment variable substitution functionality."""

    def test_substitute_simple_env_var(self):
        """Test basic environment variable substitution."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = substitute_env_vars("${TEST_VAR}")
            assert result == "test_value"

    def test_substitute_env_var_with_default(self):
        """Test environment variable with default value."""
        # Test with env var set
        with patch.dict(os.environ, {"TEST_VAR": "env_value"}):
            result = substitute_env_vars("${TEST_VAR:default_value}")
            assert result == "env_value"

        # Test with env var not set
        with patch.dict(os.environ, {}, clear=True):
            result = substitute_env_vars("${TEST_VAR:default_value}")
            assert result == "default_value"

    def test_substitute_env_var_missing_no_default(self):
        """Test missing environment variable without default raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Variable.*MISSING_VAR.*is not set"):
                substitute_env_vars("${MISSING_VAR}")

    def test_substitute_in_string_context(self):
        """Test substitution within larger strings."""
        with patch.dict(os.environ, {"HOST": "localhost", "PORT": "5432"}):
            result = substitute_env_vars("postgresql://${HOST}:${PORT}/db")
            assert result == "postgresql://localhost:5432/db"

    def test_substitute_in_dict(self):
        """Test substitution in dictionary values."""
        with patch.dict(os.environ, {"DB_HOST": "localhost", "DB_PORT": "5432"}):
            data = {
                "database": {"host": "${DB_HOST}", "port": "${DB_PORT}", "name": "mydb"}
            }
            result = substitute_env_vars(data)
            expected = {
                "database": {"host": "localhost", "port": "5432", "name": "mydb"}
            }
            assert result == expected

    def test_substitute_in_list(self):
        """Test substitution in list items."""
        with patch.dict(os.environ, {"ENV": "production"}):
            data = ["${ENV}", "staging", "${ENV:dev}"]
            result = substitute_env_vars(data)
            assert result == ["production", "staging", "production"]

    def test_substitute_nested_structure(self):
        """Test substitution in nested data structures."""
        with patch.dict(os.environ, {"REGION": "us-east-1", "DOMAIN": "test-domain"}):
            data = {
                "content": {
                    "domain": {"name": "${DOMAIN}", "region": "${REGION}"},
                    "stages": ["${REGION}", "us-west-2"],
                }
            }
            result = substitute_env_vars(data)
            expected = {
                "content": {
                    "domain": {"name": "test-domain", "region": "us-east-1"},
                    "stages": ["us-east-1", "us-west-2"],
                }
            }
            assert result == expected

    def test_substitute_non_string_values(self):
        """Test that non-string values are returned unchanged."""
        data = {
            "number": 42,
            "boolean": True,
            "null": None,
            "string": "${TEST_VAR:default}",
        }
        with patch.dict(os.environ, {}, clear=True):
            result = substitute_env_vars(data)
            expected = {
                "number": 42,
                "boolean": True,
                "null": None,
                "string": "default",
            }
            assert result == expected

    def test_substitute_multiple_vars_in_string(self):
        """Test multiple variables in single string."""
        with patch.dict(os.environ, {"USER": "admin", "PASS": "secret"}):
            result = substitute_env_vars("user=${USER}&password=${PASS}")
            assert result == "user=admin&password=secret"

    def test_substitute_empty_default(self):
        """Test empty default value."""
        with patch.dict(os.environ, {}, clear=True):
            result = substitute_env_vars("${MISSING:}")
            assert result == ""

    def test_substitute_no_substitution_needed(self):
        """Test strings without environment variables."""
        data = {
            "simple": "no variables here",
            "list": ["item1", "item2"],
            "nested": {"key": "value"},
        }
        result = substitute_env_vars(data)
        assert result == data
