"""Test GitContentConfig and GitTargetConfig separation."""
import yaml
from smus_cicd.application.application_manifest import (
    GitContentConfig,
    GitTargetConfig,
    ContentConfig,
    DeploymentConfiguration,
    ApplicationManifest,
)


def test_git_content_config():
    """Test GitContentConfig parses content.git correctly."""
    yaml_str = """
repository: covid-19-dataset
url: https://github.com/datasets/covid-19.git
branch: main
"""
    data = yaml.safe_load(yaml_str)
    config = GitContentConfig(**data)
    
    assert config.repository == "covid-19-dataset"
    assert config.url == "https://github.com/datasets/covid-19.git"
    assert config.branch == "main"


def test_git_target_config():
    """Test GitTargetConfig parses deployment_configuration.git correctly."""
    yaml_str = """
name: covid-19-dataset
connectionName: default.s3_shared
targetDirectory: repos
"""
    data = yaml.safe_load(yaml_str)
    config = GitTargetConfig(**data)
    
    assert config.name == "covid-19-dataset"
    assert config.connectionName == "default.s3_shared"
    assert config.targetDirectory == "repos"


def test_content_config_with_git():
    """Test ContentConfig uses GitContentConfig."""
    yaml_str = """
git:
  - repository: covid-19-dataset
    url: https://github.com/datasets/covid-19.git
    branch: main
"""
    data = yaml.safe_load(yaml_str)
    git_configs = [GitContentConfig(**g) for g in data["git"]]
    content = ContentConfig(git=git_configs)
    
    assert len(content.git) == 1
    assert content.git[0].repository == "covid-19-dataset"
    assert content.git[0].url == "https://github.com/datasets/covid-19.git"


def test_deployment_config_with_git():
    """Test DeploymentConfiguration uses GitTargetConfig."""
    yaml_str = """
git:
  - name: covid-19-dataset
    connectionName: default.s3_shared
    targetDirectory: repos
"""
    data = yaml.safe_load(yaml_str)
    git_configs = [GitTargetConfig(**g) for g in data["git"]]
    deployment = DeploymentConfiguration(git=git_configs)
    
    assert len(deployment.git) == 1
    assert deployment.git[0].name == "covid-19-dataset"
    assert deployment.git[0].connectionName == "default.s3_shared"
    assert deployment.git[0].targetDirectory == "repos"


def test_git_configs_are_separate():
    """Test that GitContentConfig and GitTargetConfig have different fields."""
    # Content config should NOT accept 'name' field
    try:
        GitContentConfig(name="test", url="http://test.git")
        assert False, "GitContentConfig should not accept 'name' field"
    except TypeError:
        pass  # Expected
    
    # Target config should NOT accept 'url' field
    try:
        GitTargetConfig(url="http://test.git", connectionName="default.s3")
        assert False, "GitTargetConfig should not accept 'url' field"
    except TypeError:
        pass  # Expected


def test_full_manifest_with_git_configs():
    """Test full manifest parsing with both content.git and deployment_configuration.git."""
    import tempfile
    import os
    
    manifest_yaml = """
applicationName: TestApp
content:
  git:
    - repository: covid-19-dataset
      url: https://github.com/datasets/covid-19.git
      branch: main
stages:
  test:
    stage: TEST
    domain:
      region: us-east-1
    project:
      name: test-project
    deployment_configuration:
      git:
        - name: covid-19-dataset
          connectionName: default.s3_shared
          targetDirectory: repos
"""
    
    # Write to temp file and load
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(manifest_yaml)
        temp_path = f.name
    
    try:
        manifest = ApplicationManifest.from_file(temp_path)
        
        # Check content.git
        assert len(manifest.content.git) == 1
        content_git = manifest.content.git[0]
        assert isinstance(content_git, GitContentConfig)
        assert content_git.repository == "covid-19-dataset"
        assert content_git.url == "https://github.com/datasets/covid-19.git"
        assert content_git.branch == "main"
        
        # Check deployment_configuration.git
        test_stage = manifest.stages["test"]
        assert test_stage.deployment_configuration is not None
        assert len(test_stage.deployment_configuration.git) == 1
        deploy_git = test_stage.deployment_configuration.git[0]
        assert isinstance(deploy_git, GitTargetConfig)
        assert deploy_git.name == "covid-19-dataset"
        assert deploy_git.connectionName == "default.s3_shared"
        assert deploy_git.targetDirectory == "repos"
    finally:
        os.unlink(temp_path)

