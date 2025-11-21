"""Test that YAML files are resolved during deploy before S3 upload."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from smus_cicd.commands.deploy import _copy_and_resolve_yaml


def test_copy_and_resolve_yaml_with_proj_variables():
    """Test that {proj.*} variables are resolved in YAML files."""
    # Create a temporary source YAML file with placeholders
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as src:
        src.write(
            """
tasks:
  - name: test_task
    iam_role_name: '{proj.iam_role_name}'
    project_name: '{proj.name}'
"""
        )
        src_path = src.name

    try:
        # Create a temporary destination path
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as dest:
            dest_path = dest.name

        try:
            # Mock config
            config = {
                "domain_id": "test-domain-id",
                "region": "us-east-1",
                "domain_name": "test-domain",
                "stage_name": "test",
            }

            # Mock ContextResolver to avoid AWS calls
            with patch(
                "smus_cicd.helpers.context_resolver.ContextResolver"
            ) as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve.return_value = """
tasks:
  - name: test_task
    iam_role_name: 'AmazonSageMakerUserIAMExecutionRole'
    project_name: 'test-project'
"""
                mock_resolver_class.return_value = mock_resolver

                # Call the function
                _copy_and_resolve_yaml(src_path, dest_path, "test-project", config)

                # Verify resolver was called
                mock_resolver_class.assert_called_once_with(
                    project_name="test-project",
                    domain_id="test-domain-id",
                    region="us-east-1",
                    domain_name="test-domain",
                    stage_name="test",
                    env_vars={},
                )
                mock_resolver.resolve.assert_called_once()

            # Verify the destination file has resolved content
            with open(dest_path, "r") as f:
                content = f.read()
                assert "AmazonSageMakerUserIAMExecutionRole" in content
                assert "{proj.iam_role_name}" not in content

        finally:
            if os.path.exists(dest_path):
                os.unlink(dest_path)
    finally:
        if os.path.exists(src_path):
            os.unlink(src_path)


def test_copy_and_resolve_yaml_without_variables():
    """Test that YAML files without variables are copied as-is."""
    # Create a temporary source YAML file without placeholders
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as src:
        src.write(
            """
tasks:
  - name: test_task
    iam_role_name: 'StaticRole'
"""
        )
        src_path = src.name

    try:
        # Create a temporary destination path
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as dest:
            dest_path = dest.name

        try:
            # Mock config
            config = {
                "domain_id": "test-domain-id",
                "region": "us-east-1",
                "domain_name": "test-domain",
            }

            # Call the function - should not call ContextResolver
            with patch(
                "smus_cicd.helpers.context_resolver.ContextResolver"
            ) as mock_resolver_class:
                _copy_and_resolve_yaml(src_path, dest_path, "test-project", config)

                # Verify resolver was NOT called since no {proj. patterns
                mock_resolver_class.assert_not_called()

            # Verify the destination file has same content
            with open(dest_path, "r") as f:
                content = f.read()
                assert "StaticRole" in content

        finally:
            if os.path.exists(dest_path):
                os.unlink(dest_path)
    finally:
        if os.path.exists(src_path):
            os.unlink(src_path)
