"""Unit tests for pipeline file validation."""

import os
import tempfile
import pytest
from src.smus_cicd.helpers.utils import load_yaml


class TestPipelineFileValidation:
    """Test pipeline file validation and error handling."""

    def test_load_yaml_file_exists(self):
        """Test loading YAML file when it exists."""
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
            f.flush()

            try:
                result = load_yaml(f.name)
                assert result["pipelineName"] == "TestPipeline"
                assert result["domain"]["name"] == "test-domain"
                assert result["targets"]["dev"]["project"]["name"] == "test-project"
            finally:
                os.unlink(f.name)

    def test_load_yaml_file_not_exists(self):
        """Test loading YAML file when it doesn't exist."""
        non_existent_file = "non-existent-pipeline.yaml"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_yaml(non_existent_file)

        error_message = str(exc_info.value)
        assert "Pipeline manifest file not found" in error_message
        assert non_existent_file in error_message
        assert "--pipeline/-p option" in error_message

    def test_load_yaml_default_pipeline_file_not_exists(self):
        """Test loading default pipeline.yaml when it doesn't exist."""
        # Use a temporary directory that we know doesn't have pipeline.yaml
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory and ensure no pipeline.yaml exists
            original_dir = None
            try:
                original_dir = os.getcwd()
            except FileNotFoundError:
                # If we can't get current directory, just use the temp dir
                pass

            try:
                os.chdir(temp_dir)

                with pytest.raises(FileNotFoundError) as exc_info:
                    load_yaml("pipeline.yaml")

                error_message = str(exc_info.value)
                assert (
                    "Pipeline manifest file not found: pipeline.yaml" in error_message
                )
                assert "--pipeline/-p option" in error_message
            finally:
                if original_dir:
                    os.chdir(original_dir)

    def test_load_yaml_empty_file(self):
        """Test loading empty YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")  # Empty file
            f.flush()

            try:
                result = load_yaml(f.name)
                assert result is None  # Empty YAML file returns None
            finally:
                os.unlink(f.name)

    def test_load_yaml_invalid_yaml(self):
        """Test loading invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")  # Invalid YAML
            f.flush()

            try:
                with pytest.raises(Exception):  # Should raise YAML parsing error
                    load_yaml(f.name)
            finally:
                os.unlink(f.name)
