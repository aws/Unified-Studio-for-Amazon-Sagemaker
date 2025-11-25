"""
Unit tests for manifest validation functionality.
"""

import pytest
import tempfile
import os
from pathlib import Path
from smus_cicd.application.validation import (
    validate_yaml_syntax,
    validate_manifest_schema,
    validate_manifest_file,
    load_schema,
)
from smus_cicd.application import ApplicationManifest


class TestManifestValidation:
    """Test manifest validation functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.schema = load_schema()

    def create_temp_manifest(self, content: str) -> str:
        """Create a temporary manifest file with given content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            return f.name

    def teardown_method(self):
        """Clean up temporary files."""
        # Clean up any temp files created during tests
        pass

    def test_valid_manifest(self):
        """Test validation of a valid manifest."""
        valid_manifest = """
applicationName: TestPipeline
stages:
  dev:
    domain:
      name: test-domain
      region: us-east-1
    stage: DEV
    project:
      name: dev-project
"""
        manifest_file = self.create_temp_manifest(valid_manifest)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert is_valid
            assert len(errors) == 0
            assert data["applicationName"] == "TestPipeline"
        finally:
            os.unlink(manifest_file)

    def test_invalid_yaml_syntax(self):
        """Test validation with invalid YAML syntax."""
        invalid_yaml = """
applicationName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
stages:
  dev:
    stage: DEV
    project:
      name: dev-project
    invalid_indent
"""
        manifest_file = self.create_temp_manifest(invalid_yaml)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert len(errors) == 1
            assert "YAML syntax error" in errors[0]
        finally:
            os.unlink(manifest_file)

    def test_missing_required_field_bundle_name(self):
        """Test validation with missing required bundleName."""
        missing_bundle_name = """
domain:
  name: test-domain
  region: us-east-1
stages:
  dev:
    stage: DEV
    project:
      name: dev-project
"""
        manifest_file = self.create_temp_manifest(missing_bundle_name)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any(
                "'applicationName' is a required property" in error for error in errors
            )
        finally:
            os.unlink(manifest_file)

    def test_missing_required_field_domain(self):
        """Test validation with missing required domain in target."""
        missing_domain = """
applicationName: TestPipeline
stages:
  dev:
    stage: DEV
    project:
      name: dev-project
"""
        manifest_file = self.create_temp_manifest(missing_domain)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any("'domain' is a required property" in error for error in errors)
        finally:
            os.unlink(manifest_file)

    def test_missing_required_field_targets(self):
        """Test validation with missing required targets."""
        missing_targets = """
applicationName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
"""
        manifest_file = self.create_temp_manifest(missing_targets)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any("'stages' is a required property" in error for error in errors)
        finally:
            os.unlink(manifest_file)

    def test_invalid_bundle_name_pattern(self):
        """Test validation with invalid bundleName pattern."""
        invalid_name = """
applicationName: -InvalidName
stages:
  dev:
    domain:
      name: test-domain
      region: us-east-1
    stage: DEV
    project:
      name: dev-project
"""
        manifest_file = self.create_temp_manifest(invalid_name)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any("does not match" in error for error in errors)
        finally:
            os.unlink(manifest_file)

    def test_invalid_region_pattern(self):
        """Test validation with invalid region pattern."""
        invalid_region = """
applicationName: TestPipeline
stages:
  dev:
    domain:
      name: test-domain
      region: INVALID_REGION
    stage: DEV
    project:
      name: dev-project
"""
        manifest_file = self.create_temp_manifest(invalid_region)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any("does not match" in error for error in errors)
        finally:
            os.unlink(manifest_file)

    def test_invalid_engine_enum(self):
        """Test validation with invalid workflow engine."""
        invalid_engine = """
applicationName: TestPipeline
content:
  storage: []
stages:
  dev:
    domain:
      name: test-domain
      region: us-east-1
    stage: DEV
    project:
      name: dev-project
bootstrap:
  actions:
    - type: mwaaserverless.start_workflow_run
      workflowArn: arn:aws:airflow-serverless:us-east-1:123456789012:workflow/test
      engine: InvalidEngine
"""
        manifest_file = self.create_temp_manifest(invalid_engine)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any("is not one of" in error or "InvalidEngine" in error for error in errors)
        finally:
            os.unlink(manifest_file)

    def test_missing_project_name_in_target(self):
        """Test validation with missing project name in target."""
        missing_project_name = """
applicationName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
stages:
  dev:
    stage: DEV
    project: {}
"""
        manifest_file = self.create_temp_manifest(missing_project_name)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any("'name' is a required property" in error for error in errors)
        finally:
            os.unlink(manifest_file)

    def test_empty_targets_object(self):
        """Test validation with empty targets object."""
        empty_targets = """
applicationName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
stages: {}
"""
        manifest_file = self.create_temp_manifest(empty_targets)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            # Check for empty targets validation error
            assert any("should be non-empty" in error for error in errors)
        finally:
            os.unlink(manifest_file)

    def test_top_level_domain_not_allowed(self):
        """Test validation rejects top-level domain configuration."""
        top_level_domain = """
applicationName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
stages:
  dev:
    domain:
      name: test-domain
      region: us-east-1
    stage: DEV
    project:
      name: dev-project
"""
        manifest_file = self.create_temp_manifest(top_level_domain)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any("Additional properties are not allowed" in error and "'domain'" in error for error in errors)
        finally:
            os.unlink(manifest_file)

    def test_missing_bundle_target_config_required_fields(self):
        """Test validation with missing required fields in bundle_target_configuration."""
        missing_fields = """
applicationName: TestPipeline
stages:
  dev:
    domain:
      name: test-domain
      region: us-east-1
    stage: DEV
    project:
      name: dev-project
    deployment_configuration:
      storage:
        - connectionName: default.s3_shared
          # missing name field
"""
        manifest_file = self.create_temp_manifest(missing_fields)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any(
                "deployment_configuration" in error and "storage" in error
                for error in errors
            )
        finally:
            os.unlink(manifest_file)


class TestBundleManifestValidation:
    """Test ApplicationManifest class validation integration."""

    def create_temp_manifest(self, content: str) -> str:
        """Create a temporary manifest file with given content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            return f.name

    def test_valid_manifest_loads_successfully(self):
        """Test that a valid manifest loads without errors."""
        valid_manifest = """
applicationName: TestPipeline
stages:
  dev:
    domain:
      name: test-domain
      region: us-east-1
    stage: DEV
    project:
      name: dev-project
"""
        manifest_file = self.create_temp_manifest(valid_manifest)
        try:
            manifest = ApplicationManifest.from_file(manifest_file)
            assert manifest.application_name == "TestPipeline"
            assert manifest.stages["dev"].domain.name == "test-domain"
        finally:
            os.unlink(manifest_file)

    def test_invalid_manifest_raises_value_error(self):
        """Test that an invalid manifest raises ValueError with validation details."""
        invalid_manifest = """
applicationName: -InvalidName
domain:
  name: test-domain
  region: INVALID_REGION
stages: {}
"""
        manifest_file = self.create_temp_manifest(invalid_manifest)
        try:
            with pytest.raises(ValueError) as exc_info:
                ApplicationManifest.from_file(manifest_file)

            error_message = str(exc_info.value)
            assert "Manifest validation failed" in error_message
            # Check for either pattern error or other validation errors
            assert ("does not match" in error_message or 
                    "should be non-empty" in error_message or
                    "Additional properties" in error_message)
        finally:
            os.unlink(manifest_file)

    def test_yaml_syntax_error_raises_value_error(self):
        """Test that YAML syntax errors raise ValueError."""
        invalid_yaml = """
applicationName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
stages:
  dev:
    stage: DEV
    project:
      name: dev-project
    invalid_indent
"""
        manifest_file = self.create_temp_manifest(invalid_yaml)
        try:
            with pytest.raises(ValueError) as exc_info:
                ApplicationManifest.from_file(manifest_file)

            error_message = str(exc_info.value)
            assert "Manifest validation failed" in error_message
            assert "YAML syntax error" in error_message
        finally:
            os.unlink(manifest_file)

