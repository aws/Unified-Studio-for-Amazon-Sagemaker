"""
Unit tests for manifest validation functionality.
"""

import pytest
import tempfile
import os
from pathlib import Path
from smus_cicd.pipeline.validation import (
    validate_yaml_syntax,
    validate_manifest_schema,
    validate_manifest_file,
    load_schema,
)
from smus_cicd.pipeline import PipelineManifest


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
pipelineName: TestPipeline
targets:
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
            assert data["pipelineName"] == "TestPipeline"
        finally:
            os.unlink(manifest_file)

    def test_invalid_yaml_syntax(self):
        """Test validation with invalid YAML syntax."""
        invalid_yaml = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets:
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

    def test_missing_required_field_pipeline_name(self):
        """Test validation with missing required pipelineName."""
        missing_pipeline_name = """
domain:
  name: test-domain
  region: us-east-1
targets:
  dev:
    stage: DEV
    project:
      name: dev-project
"""
        manifest_file = self.create_temp_manifest(missing_pipeline_name)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any(
                "'pipelineName' is a required property" in error for error in errors
            )
        finally:
            os.unlink(manifest_file)

    def test_missing_required_field_domain(self):
        """Test validation with missing required domain in target."""
        missing_domain = """
pipelineName: TestPipeline
targets:
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
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
"""
        manifest_file = self.create_temp_manifest(missing_targets)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any("'targets' is a required property" in error for error in errors)
        finally:
            os.unlink(manifest_file)

    def test_invalid_pipeline_name_pattern(self):
        """Test validation with invalid pipelineName pattern."""
        invalid_name = """
pipelineName: 123InvalidName
targets:
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
pipelineName: TestPipeline
targets:
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
pipelineName: TestPipeline
targets:
  dev:
    domain:
      name: test-domain
      region: us-east-1
    stage: DEV
    project:
      name: dev-project
workflows:
  - workflowName: test_workflow
    connectionName: project.workflow_mwaa
    engine: InvalidEngine
"""
        manifest_file = self.create_temp_manifest(invalid_engine)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any("is not one of" in error for error in errors)
        finally:
            os.unlink(manifest_file)

    def test_missing_project_name_in_target(self):
        """Test validation with missing project name in target."""
        missing_project_name = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets:
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
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets: {}
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
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets:
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
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets:
  dev:
    stage: DEV
    project:
      name: dev-project
    bundle_target_configuration:
      workflows:
        connectionName: default.s3_shared
        # missing directory field
"""
        manifest_file = self.create_temp_manifest(missing_fields)
        try:
            is_valid, errors, data = validate_manifest_file(manifest_file)
            assert not is_valid
            assert any(
                "'directory' is a required property" in error for error in errors
            )
        finally:
            os.unlink(manifest_file)


class TestPipelineManifestValidation:
    """Test PipelineManifest class validation integration."""

    def create_temp_manifest(self, content: str) -> str:
        """Create a temporary manifest file with given content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            return f.name

    def test_valid_manifest_loads_successfully(self):
        """Test that a valid manifest loads without errors."""
        valid_manifest = """
pipelineName: TestPipeline
targets:
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
            manifest = PipelineManifest.from_file(manifest_file)
            assert manifest.pipeline_name == "TestPipeline"
            assert manifest.targets["dev"].domain.name == "test-domain"
        finally:
            os.unlink(manifest_file)

    def test_invalid_manifest_raises_value_error(self):
        """Test that an invalid manifest raises ValueError with validation details."""
        invalid_manifest = """
pipelineName: 123InvalidName
domain:
  name: test-domain
  region: INVALID_REGION
targets: {}
"""
        manifest_file = self.create_temp_manifest(invalid_manifest)
        try:
            with pytest.raises(ValueError) as exc_info:
                PipelineManifest.from_file(manifest_file)

            error_message = str(exc_info.value)
            assert "Manifest validation failed" in error_message
            assert "does not match" in error_message  # Pattern validation error
        finally:
            os.unlink(manifest_file)

    def test_yaml_syntax_error_raises_value_error(self):
        """Test that YAML syntax errors raise ValueError."""
        invalid_yaml = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
targets:
  dev:
    stage: DEV
    project:
      name: dev-project
    invalid_indent
"""
        manifest_file = self.create_temp_manifest(invalid_yaml)
        try:
            with pytest.raises(ValueError) as exc_info:
                PipelineManifest.from_file(manifest_file)

            error_message = str(exc_info.value)
            assert "Manifest validation failed" in error_message
            assert "YAML syntax error" in error_message
        finally:
            os.unlink(manifest_file)
