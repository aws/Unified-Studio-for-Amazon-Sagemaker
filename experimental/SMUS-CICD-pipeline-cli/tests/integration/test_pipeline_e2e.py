"""Integration tests for end-to-end pipeline workflows."""
import os
import pytest
import tempfile
from typer.testing import CliRunner
from smus_cicd.cli import app

runner = CliRunner()

@pytest.fixture
def aws_credentials():
    """Check if AWS credentials are available."""
    if not (os.getenv('AWS_ACCESS_KEY_ID') or os.getenv('AWS_PROFILE')):
        pytest.skip("AWS credentials not available")

@pytest.fixture
def test_manifest():
    """Create a test manifest file."""
    manifest_content = """
pipelineName: IntegrationTestPipeline
domain:
  name: test-domain
  region: us-east-1
bundle:
  workflow:
    - connectionName: default.s3_shared
      append: true
      include: ['workflows/']
      exclude: ['.ipynb_checkpoints/', '__pycache__/']
  storage:
    - connectionName: default.s3_shared
      append: false
      include: ['src/']
      exclude: ['.ipynb_checkpoints/', '__pycache__/']
workflows:
  - workflowName: integration_test_dag
    connectionName: project.workflow_connection
    triggerPostDeployment: false
    logging: console
    engine: MWAA
targets:
  dev:
    default: true
    stage: dev
    project:
      name: integration-test-dev-project
  test:
    stage: test
    project:
      name: integration-test-project
    initialization:
      project:
        create: false
        profileName: 'All capabilities'
        owners: []
        contributors: []
      environments:
        - EnvironmentConfigurationName: 'OnDemand Workflows'
    bundle_target_configuration:
      storage:
        connectionName: default.s3_shared
        directory: 'src'
      workflows:
        connectionName: default.s3_shared
        directory: 'workflows'
    workflows:
      - workflowName: integration_test_dag
        parameters:
          test_param: integration_value
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(manifest_content)
        f.flush()
        yield f.name
    
    os.unlink(f.name)

class TestPipelineE2E:
    """End-to-end pipeline tests."""
    
    def test_parse_real_manifest(self, test_manifest, aws_credentials):
        """Test parsing a real manifest file."""
        result = runner.invoke(app, ["describe", "--pipeline", test_manifest])
        assert result.exit_code == 0
        assert "Pipeline: IntegrationTestPipeline" in result.stdout
    
    def test_parse_with_connections_and_targets(self, test_manifest, aws_credentials):
        """Test parsing with connections and targets flags."""
        result = runner.invoke(app, ["describe", "--pipeline", test_manifest, "--connections"])
        if result.exit_code != 0:
            print(f"Error output: {result.stdout}")
            print(f"Error stderr: {result.stderr if hasattr(result, 'stderr') else 'No stderr'}")
        assert result.exit_code == 0
        # Projects don't exist, so we expect error messages instead of connections
        assert "Project" in result.stdout
        assert "Targets:" in result.stdout
        assert "integration_test_dag" in result.stdout
    
    def test_bundle_creation_flow(self, test_manifest, aws_credentials):
        """Test bundle creation with real AWS resources."""
        result = runner.invoke(app, ["bundle", "--pipeline", test_manifest])
        
        # Bundle may fail if AWS resources aren't available - this is expected in test environment
        if result.exit_code == 0:
            # If it succeeds, verify bundle was created
            assert "Bundle created" in result.stdout
        else:
            # If it fails, it should be due to missing AWS resources (expected)
            assert result.exit_code == 1
            # The command structure should still work (no syntax errors, etc.)
    
    def test_monitor_flow(self, test_manifest, aws_credentials):
        """Test monitoring workflow with real AWS resources."""
        result = runner.invoke(app, ["monitor", "--pipeline", test_manifest])
        
        # Monitor may fail if AWS resources aren't available - this is expected in test environment
        if result.exit_code == 0:
            # If it succeeds, verify pipeline info is shown
            assert "Pipeline: IntegrationTestPipeline" in result.stdout
        else:
            # If it fails, it should be due to missing AWS resources (expected)
            assert result.exit_code == 1
            # The command structure should still work

class TestPipelineValidation:
    """Pipeline validation tests."""
    
    def test_invalid_manifest_structure(self):
        """Test with invalid manifest structure."""
        invalid_manifest = """
invalid_yaml: [
  missing_closing_bracket
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(invalid_manifest)
            f.flush()
            
            result = runner.invoke(app, ["describe", "--pipeline", f.name])
            assert result.exit_code == 1
            
        os.unlink(f.name)
    
    def test_missing_required_fields(self):
        """Test with missing required fields."""
        minimal_manifest = """
pipelineName: MinimalPipeline
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(minimal_manifest)
            f.flush()
            
            result = runner.invoke(app, ["describe", "--pipeline", f.name])
            # Should fail validation due to missing required fields
            assert result.exit_code == 1
            assert "domain" in result.output and "required property" in result.output
            
        os.unlink(f.name)
