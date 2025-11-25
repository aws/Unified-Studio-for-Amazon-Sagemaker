"""Test missing environment variable validation."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from smus_cicd.application.application_manifest import ApplicationManifest


def test_missing_env_var_without_default():
    """Test that missing env var without default raises error."""
    manifest_content = """
applicationName: TestApp
content:
  storage:
  - name: test-storage
    connectionName: default.s3
stages:
  test:
    stage: TEST
    domain:
      region: ${MISSING_ENV_VAR}
    project:
      name: test-project
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(manifest_content)
        manifest_file = f.name

    try:
        # Ensure env var is not set
        if 'MISSING_ENV_VAR' in os.environ:
            del os.environ['MISSING_ENV_VAR']

        with pytest.raises(ValueError) as exc_info:
            ApplicationManifest.from_file(manifest_file)

        error_msg = str(exc_info.value)
        assert "Missing required environment variables" in error_msg
        assert "MISSING_ENV_VAR" in error_msg
    finally:
        Path(manifest_file).unlink()


def test_missing_multiple_env_vars():
    """Test that multiple missing env vars are all reported."""
    manifest_content = """
applicationName: TestApp
content:
  storage:
  - name: test-storage
    connectionName: default.s3
stages:
  dev:
    stage: DEV
    domain:
      region: ${MISSING_VAR_1}
    project:
      name: dev-project
  test:
    stage: TEST
    domain:
      region: ${MISSING_VAR_2}
    project:
      name: test-project
      role:
        arn: arn:aws:iam::${MISSING_VAR_3}:role/TestRole
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(manifest_content)
        manifest_file = f.name

    try:
        # Ensure env vars are not set
        for var in ['MISSING_VAR_1', 'MISSING_VAR_2', 'MISSING_VAR_3']:
            if var in os.environ:
                del os.environ[var]

        with pytest.raises(ValueError) as exc_info:
            ApplicationManifest.from_file(manifest_file)

        error_msg = str(exc_info.value)
        assert "Missing required environment variables" in error_msg
        assert "MISSING_VAR_1" in error_msg
        assert "MISSING_VAR_2" in error_msg
        assert "MISSING_VAR_3" in error_msg
    finally:
        Path(manifest_file).unlink()


def test_env_var_with_default_does_not_error():
    """Test that env var with default value does not raise error."""
    manifest_content = """
applicationName: TestApp
content:
  storage:
  - name: test-storage
    connectionName: default.s3
stages:
  test:
    stage: TEST
    domain:
      region: ${OPTIONAL_VAR:us-east-1}
    project:
      name: test-project
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(manifest_content)
        manifest_file = f.name

    try:
        # Ensure env var is not set
        if 'OPTIONAL_VAR' in os.environ:
            del os.environ['OPTIONAL_VAR']

        # Should not raise error
        manifest = ApplicationManifest.from_file(manifest_file)
        assert manifest.application_name == "TestApp"
    finally:
        Path(manifest_file).unlink()


def test_pseudo_env_vars_do_not_error():
    """Test that pseudo env vars (STS_ACCOUNT_ID, etc) do not raise error."""
    manifest_content = """
applicationName: TestApp
content:
  storage:
  - name: test-storage
    connectionName: default.s3
stages:
  test:
    stage: TEST
    domain:
      region: ${STS_REGION}
    project:
      name: test-project
      role:
        arn: arn:aws:iam::${STS_ACCOUNT_ID}:role/TestRole
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(manifest_content)
        manifest_file = f.name

    try:
        # Mock boto3 calls for pseudo env vars
        with patch('boto3.client') as mock_client:
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
            mock_client.return_value = mock_sts
            
            with patch('boto3.Session') as mock_session:
                mock_session.return_value.region_name = 'us-east-1'
                
                # Should not raise error for pseudo env vars
                manifest = ApplicationManifest.from_file(manifest_file)
                assert manifest.application_name == "TestApp"
    finally:
        Path(manifest_file).unlink()


def test_set_env_var_does_not_error():
    """Test that set env var does not raise error."""
    manifest_content = """
applicationName: TestApp
content:
  storage:
  - name: test-storage
    connectionName: default.s3
stages:
  test:
    stage: TEST
    domain:
      region: ${TEST_REGION}
    project:
      name: test-project
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(manifest_content)
        manifest_file = f.name

    try:
        # Set the env var
        os.environ['TEST_REGION'] = 'us-west-2'

        # Should not raise error
        manifest = ApplicationManifest.from_file(manifest_file)
        assert manifest.application_name == "TestApp"
    finally:
        if 'TEST_REGION' in os.environ:
            del os.environ['TEST_REGION']
        Path(manifest_file).unlink()
