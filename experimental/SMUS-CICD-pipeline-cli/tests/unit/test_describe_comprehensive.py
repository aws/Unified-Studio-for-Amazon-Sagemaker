"""Comprehensive unit tests for describe command."""
import pytest
import tempfile
import os
from typer.testing import CliRunner
from smus_cicd.cli import app


class TestDescribeCommand:
    """Test suite for describe command with various manifest scenarios."""

    def create_manifest_file(self, content):
        """Helper to create temporary manifest file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            f.flush()
            return f.name

    def run_describe(self, manifest_content, args=None):
        """Helper to run describe command with manifest content."""
        manifest_file = self.create_manifest_file(manifest_content)
        try:
            runner = CliRunner()
            cmd_args = ["describe", "--pipeline", manifest_file] + (args or [])
            result = runner.invoke(app, cmd_args)
            return result
        finally:
            os.unlink(manifest_file)

    def test_minimal_valid_manifest(self):
        """Test minimal valid manifest."""
        manifest = """
pipelineName: MinimalPipeline
domain:
  name: minimal-domain
  region: us-west-2
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  staging:
    stage: STAGING
    project:
      name: minimal-project
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 0
        assert "Pipeline: MinimalPipeline" in result.stdout
        assert "Domain: minimal-domain (us-west-2)" in result.stdout

    def test_complex_manifest_with_workflows(self):
        """Test complex manifest with multiple workflows and targets."""
        manifest = """
pipelineName: ComplexPipeline
domain:
  name: complex-domain
  region: eu-central-1
bundle:
  bundlesDirectory: /tmp/bundles
  workflow:
    - connectionName: project.workflow_connection
      append: true
      include: ['workflows/']
  storage:
    - connectionName: project.storage_connection
      append: false
      include: ['notebooks/']
targets:
  development:
    stage: DEVELOPMENT
    project:
      name: dev-project
      create: false
    default: true
  production:
    stage: PRODUCTION
    project:
      name: prod-project
      create: false
workflows:
  - workflowName: data_pipeline
    connectionName: project.mwaa_connection
    logging: console
    engine: MWAA
    parameters:
      env: production
      timeout: 3600
  - workflowName: ml_training
    connectionName: project.spark_connection
    logging: none
    engine: MWAA
"""
        result = self.run_describe(manifest, ["--connections"])
        assert result.exit_code == 0
        
        # Check pipeline info
        assert "Pipeline: ComplexPipeline" in result.stdout
        assert "Domain: complex-domain (eu-central-1)" in result.stdout
        
        # Check workflows
        assert "Workflows:" in result.stdout
        assert "data_pipeline" in result.stdout
        assert "ml_training" in result.stdout
        assert "Connection: project.mwaa_connection" in result.stdout
        assert "Connection: project.spark_connection" in result.stdout
        assert "Engine: MWAA" in result.stdout
        assert "'env': 'production'" in result.stdout
        assert "'timeout': 3600" in result.stdout
        
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
            "~/home-bundles"
        ]
        
        for bundle_dir in test_cases:
            manifest = f"""
pipelineName: BundleDirTest
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: {bundle_dir}
targets:
  test:
    stage: TEST
    project:
      name: test-project
      create: false
"""
            result = self.run_describe(manifest)
            assert result.exit_code == 0
            assert "Pipeline: BundleDirTest" in result.stdout

    def test_different_regions(self):
        """Test that different AWS regions are not hardcoded."""
        regions = [
            "us-east-1", "us-west-2", "eu-west-1", "eu-central-1",
            "ap-southeast-1", "ap-northeast-1", "ca-central-1"
        ]
        
        for region in regions:
            manifest = f"""
pipelineName: RegionTest
domain:
  name: test-domain
  region: {region}
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test:
    stage: TEST
    project:
      name: test-project
      create: false
"""
            result = self.run_describe(manifest)
            assert result.exit_code == 0
            assert f"Domain: test-domain ({region})" in result.stdout

    def test_various_project_configurations(self):
        """Test different project configuration formats."""
        # Object format
        manifest1 = """
pipelineName: StringProject
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test:
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
pipelineName: ObjectProject
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test:
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
pipelineName: WorkflowParams
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test:
    stage: TEST
    project:
      name: test-project
      create: false
workflows:
  - workflowName: no_params
    connectionName: conn1
  - workflowName: simple_params
    connectionName: conn2
    parameters:
      key1: value1
  - workflowName: complex_params
    connectionName: conn3
    parameters:
      string_param: "test string"
      number_param: 42
      boolean_param: true
"""
        result = self.run_describe(manifest, ["--connections"])
        assert result.exit_code == 0
        # Basic output shows pipeline and targets
        assert "Pipeline:" in result.stdout
        assert "Targets:" in result.stdout
        assert "Parameters: {'key1': 'value1'}" in result.stdout
        assert "Parameters: {'string_param': 'test string', 'number_param': 42, 'boolean_param': True}" in result.stdout

    # Negative test cases
    def test_missing_pipeline_name(self):
        """Test error when pipelineName is missing."""
        manifest = """
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test:
    stage: TEST
    project:
      name: test-project
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'pipelineName' is a required property" in result.stderr

    def test_missing_domain(self):
        """Test error when domain is missing."""
        manifest = """
pipelineName: TestPipeline
bundle:
  bundlesDirectory: /tmp/bundles
targets:
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
        """Test error when domain name is missing."""
        manifest = """
pipelineName: TestPipeline
domain:
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test:
    stage: TEST
    project:
      name: test-project
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'name' is a required property" in result.stderr

    def test_missing_domain_region(self):
        """Test error when domain region is missing."""
        manifest = """
pipelineName: TestPipeline
domain:
  name: test-domain
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test:
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
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'targets' is a required property" in result.stderr

    def test_empty_targets(self):
        """Test error when targets section is empty."""
        manifest = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets: {}
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "should be non-empty" in result.stderr

    def test_target_missing_project(self):
        """Test error when target is missing project."""
        manifest = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test: {}
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'project' is a required property" in result.stderr

    def test_workflow_missing_name(self):
        """Test error when workflow is missing name."""
        manifest = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test:
    stage: TEST
    project:
      name: test-project
      create: false
workflows:
  - connectionName: test-connection
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'workflowName' is a required property" in result.stderr

    def test_workflow_missing_connection(self):
        """Test error when workflow is missing connection."""
        manifest = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test:
    stage: TEST
    project:
      name: test-project
      create: false
workflows:
  - workflowName: test-workflow
"""
        result = self.run_describe(manifest)
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "'connectionName' is a required property" in result.stderr

    def test_invalid_yaml_syntax(self):
        """Test error with invalid YAML syntax."""
        manifest = """
pipelineName: TestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets:
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
        result = runner.invoke(app, ["describe", "--pipeline", "/nonexistent/file.yaml"])
        assert result.exit_code == 1
        assert "Error describing manifest" in result.stderr
        assert "not found" in result.stderr.lower()

    def test_default_values_not_hardcoded(self):
        """Test that default values are properly applied and not hardcoded."""
        # Test minimal manifest to ensure defaults are applied
        manifest = """
pipelineName: DefaultTest
domain:
  name: test-domain
  region: us-east-1
targets:
  test:
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
pipelineName: BundleDefaultTest
domain:
  name: test-domain
  region: us-east-1
targets:
  test:
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
pipelineName: WorkflowDefaultTest
domain:
  name: test-domain
  region: us-east-1
bundle:
  bundlesDirectory: /tmp/bundles
targets:
  test:
    stage: TEST
    project:
      name: test-project
      create: false
workflows:
  - workflowName: minimal_workflow
    connectionName: test-connection
"""
        result = self.run_describe(manifest, ["--connections"])
        assert result.exit_code == 0
        # Basic output shows pipeline and targets
        assert "Pipeline:" in result.stdout
        assert "Targets:" in result.stdout
        assert "Connection: test-connection" in result.stdout
        assert "Engine: Workflows" in result.stdout  # Default value

    def test_edge_case_empty_strings(self):
        """Test handling of empty string values."""
        manifest = """
pipelineName: ""
domain:
  name: ""
  region: ""
bundle:
  bundlesDirectory: "/tmp/bundles"
targets:
  test:
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
pipelineName: "Pipeline-With_Special_Characters123"
domain:
  name: "domain-with-dashes"
  region: us-east-1
bundle:
  bundlesDirectory: "/tmp/bundles-with-dashes"
targets:
  "target-with-dashes":
    stage: TEST
    project:
      name: "project_with_underscores"
      create: false
workflows:
  - workflowName: "workflow_with_underscores"
    connectionName: "connection_with_underscores"
"""
        result = self.run_describe(manifest, ["--connections"])
        assert result.exit_code == 0
        assert "Pipeline: Pipeline-With_Special_Characters123" in result.stdout
        assert "Domain: domain-with-dashes (us-east-1)" in result.stdout
        assert "target-with-dashes: project_with_underscores" in result.stdout
        assert "workflow_with_underscores" in result.stdout
        assert "Connection: connection_with_underscores" in result.stdout
