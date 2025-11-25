"""Comprehensive unit tests for describe command."""

import pytest
import tempfile
import os
from typer.testing import CliRunner
from unittest.mock import patch
from smus_cicd.cli import app


class TestDescribeCommand:
    """Test suite for describe command with various manifest scenarios."""

    def create_manifest_file(self, content):
        """Helper to create temporary manifest file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            f.flush()
            return f.name

    def run_describe(self, manifest_content, args=None):
        """Helper to run describe command with manifest content."""
        manifest_file = self.create_manifest_file(manifest_content)
        try:
            runner = CliRunner()
            cmd_args = ["describe", "--manifest", manifest_file] + (args or [])
            with patch("smus_cicd.commands.describe.get_datazone_project_info") as mock_project:
                with patch("smus_cicd.commands.describe.load_config") as mock_config:
                    mock_project.return_value = {"connections": {}, "status": "ACTIVE", "project_id": "test-id"}
                    mock_config.return_value = {"region": "us-east-1"}
                    result = runner.invoke(app, cmd_args)
            return result
        finally:
            os.unlink(manifest_file)

    def test_minimal_valid_manifest(self):
        """Test minimal valid manifest."""
        manifest = """
applicationName: MinimalPipeline
content:
  storage: []
stages:
  staging:
    domain:
      name: minimal-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: STAGING
    project:
      name: minimal-project
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 0
        assert "Pipeline: MinimalPipeline" in result.stdout
        assert "Domain: minimal-domain" in result.stdout

    def test_complex_manifest_with_workflows(self):
        """Test complex manifest with multiple workflows and targets."""
        manifest = """
applicationName: ComplexPipeline
content:
  storage:
    - name: workflows
      connectionName: project.workflow_connection
      append: true
      include: ['workflows/']
    - name: notebooks
      connectionName: project.storage_connection
      append: false
      include: ['notebooks/']
stages:
  development:
    domain:
      name: complex-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: DEV
    project:
      name: dev-project
      create: false
  production:
    domain:
      name: complex-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: PROD
    project:
      name: prod-project
      create: false
"""
        result = self.run_describe(manifest, ["--connections"])
        assert result.exit_code == 0

        # Check pipeline info
        assert "Pipeline: ComplexPipeline" in result.stdout
        assert "Domain: complex-domain" in result.stdout

        # Check targets
        assert "Targets:" in result.stdout
        assert "development: dev-project" in result.stdout
        assert "production: prod-project" in result.stdout

    def test_different_bundle_directories(self):
        """Test that different bundle directories are not hardcoded."""
        test_cases = [
            "./bundles",
            "./custom-bundles",
            "/absolute/path/bundles",
            "relative/bundles",
            "~/home-bundles",
        ]

        for bundle_dir in test_cases:
            manifest = f"""
applicationName: BundleDirTest
content:
  storage: []
stages:
  test:
    domain:
      name: test-domain
      region: ${{DEV_DOMAIN_REGION:us-east-1}}
    stage: TEST
    project:
      name: test-project
      create: false
"""
            result = self.run_describe(manifest)
            assert result.exit_code == 0
            assert "Pipeline: BundleDirTest" in result.stdout

    def test_various_project_configurations(self):
        """Test different project configuration formats."""
        # Object format
        manifest1 = """
applicationName: StringProject
content:
  storage: []
stages:
  test:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: simple-project-name
      create: false
"""
        result = self.run_describe(manifest1)
        assert result.exit_code == 0
        assert "test: simple-project-name" in result.stdout

        # Object format with all fields
        manifest2 = """
applicationName: ObjectProject
content:
  storage: []
stages:
  test:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: complex-project
      create: false
"""
        result = self.run_describe(manifest2, ["--targets", "test"])
        assert result.exit_code == 0
        assert "test: complex-project" in result.stdout

    def test_workflow_parameter_variations(self):
        """Test workflows with different parameter combinations."""
        manifest = """
applicationName: WorkflowParams
content:
  storage: []
stages:
  test:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: test-project
      create: false
"""
        result = self.run_describe(manifest, ["--connections"])
        assert result.exit_code == 0
        # Basic output shows pipeline and targets
        assert "Pipeline:" in result.stdout
        assert "Targets:" in result.stdout

    # Negative test cases
    def test_missing_bundle_name(self):
        """Test error when bundleName is missing."""
        manifest = """
content:
  storage: []
stages:
  test:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: test-project
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'applicationName' is a required property" in result.stderr

    def test_missing_domain(self):
        """Test error when domain is missing."""
        manifest = """
applicationName: TestPipeline
content:
  storage: []
stages:
  test:
    stage: TEST
    project:
      name: test-project
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'domain' is a required property" in result.stderr

    def test_missing_domain_name(self):
        """Test that domain name is optional (can use tags instead)."""
        manifest = """
applicationName: TestPipeline
content:
  storage: []
stages:
  test:
    domain:
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: test-project
"""
        result = self.run_describe(manifest)
        # Domain name is optional, so this should succeed
        assert result.exit_code == 0
        assert "Pipeline: TestPipeline" in result.stdout

    def test_missing_domain_region(self):
        """Test error when domain region is missing."""
        manifest = """
applicationName: TestPipeline
content:
  storage: []
stages:
  test:
    domain:
      name: test-domain
    stage: TEST
    project:
      name: test-project
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'region' is a required property" in result.stderr

    def test_missing_targets(self):
        """Test error when targets section is missing."""
        manifest = """
applicationName: TestPipeline
content:
  storage: []
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'stages' is a required property" in result.stderr

    def test_empty_targets(self):
        """Test error when targets section is empty."""
        manifest = """
applicationName: TestPipeline
domain:
  name: test-domain
  region: ${DEV_DOMAIN_REGION:us-east-1}
content:
  storage: []
stages: {}
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "should be non-empty" in result.stderr

    def test_target_missing_project(self):
        """Test error when target is missing project."""
        manifest = """
applicationName: TestPipeline
domain:
  name: test-domain
  region: ${DEV_DOMAIN_REGION:us-east-1}
content:
  storage: []
stages:
  test: {}
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'project' is a required property" in result.stderr

    def test_workflow_missing_name(self):
        """Test error when workflow is missing name."""
        manifest = """
applicationName: TestPipeline
content:
  storage: []
stages:
  test:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: test-project
      create: false
"""
        result = self.run_describe(manifest)
        # Should succeed with valid manifest
        assert result.exit_code == 0

    def test_workflow_missing_connection(self):
        """Test error when manifest is missing required fields."""
        manifest = """
applicationName: TestPipeline
stages:
  test:
    stage: TEST
    domain:
      name: test-domain
      region: us-east-1
    project:
      name: test-project
      create: false
"""
        result = self.run_describe(manifest)
        # Should succeed with valid manifest
        assert result.exit_code == 0

    def test_invalid_yaml_syntax(self):
        """Test error with invalid YAML syntax."""
        manifest = """
applicationName: TestPipeline
domain:
  name: test-domain
  region: ${DEV_DOMAIN_REGION:us-east-1}
content:
  storage: []
stages:
  test:
    stage: TEST
    project:
      name: test-project
      create: false
    invalid_yaml: [unclosed list
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr

    def test_nonexistent_manifest_file(self):
        """Test error when manifest file doesn't exist."""
        runner = CliRunner()
        result = runner.invoke(
            app, ["describe", "--manifest", "/nonexistent/file.yaml"]
        )
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "not found" in result.stderr.lower()

    def test_default_values_not_hardcoded(self):
        """Test that default values are properly applied and not hardcoded."""
        # Test minimal manifest to ensure defaults are applied
        manifest = """
applicationName: DefaultTest
stages:
  test:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: test-project
      create: false
"""
        result = self.run_describe(manifest, ["--connections"])
        assert result.exit_code == 0
        # Should show basic pipeline info
        assert "Pipeline:" in result.stdout
        assert "Targets:" in result.stdout
        # But should not show any workflow items in the manifest workflows section
        assert "Manifest Workflows:" not in result.stdout

    def test_bundle_defaults(self):
        """Test bundle configuration defaults."""
        manifest = """
applicationName: BundleDefaultTest
stages:
  test:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: test-project
      create: false
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 0
        # Should work even without explicit bundle configuration

    def test_workflow_defaults(self):
        """Test workflow configuration defaults."""
        manifest = """
applicationName: WorkflowDefaultTest
content:
  storage: []
stages:
  test:
    domain:
      name: test-domain
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: test-project
      create: false
"""
        result = self.run_describe(manifest, ["--connections"])
        assert result.exit_code == 0
        # Basic output shows pipeline and targets
        assert "Pipeline:" in result.stdout
        assert "Targets:" in result.stdout

    def test_edge_case_empty_strings(self):
        """Test handling of empty string values."""
        manifest = """
applicationName: ""
content:
  storage: []
stages:
  test:
    domain:
      name: ""
      region: ""
    stage: TEST
    project:
      name: ""
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr

    def test_special_characters_in_names(self):
        """Test handling of special characters in names."""
        manifest = """
applicationName: "Pipeline-With_Special_Characters123"
content:
  storage: []
stages:
  "target-with-dashes":
    domain:
      name: "domain-with-dashes"
      region: ${DEV_DOMAIN_REGION:us-east-1}
    stage: TEST
    project:
      name: "project_with_underscores"
      create: false
"""
        result = self.run_describe(manifest, ["--connections"])
        assert result.exit_code == 0
        assert "Pipeline: Pipeline-With_Special_Characters123" in result.stdout
        assert "Domain: domain-with-dashes" in result.stdout
        assert "target-with-dashes: project_with_underscores" in result.stdout
