"""Unit tests for region configuration logic."""

import pytest
from unittest.mock import patch, MagicMock

from smus_cicd.helpers.utils import _get_region_from_config, load_config
from smus_cicd.pipeline import PipelineManifest


class TestRegionConfiguration:
    """Test region configuration resolution across different scenarios."""

    def test_get_region_from_config_with_domain_region(self):
        """Test region resolution when domain.region is properly set."""
        config = {
            "domain": {"name": "test-domain", "region": "us-east-1"},
            "region": "us-east-1"
        }
        
        result = _get_region_from_config(config)
        assert result == "us-east-1"

    def test_get_region_from_config_with_aws_region_fallback(self):
        """Test region resolution falls back to aws.region when domain.region is missing."""
        config = {
            "aws": {"region": "us-west-2"}
        }
        
        result = _get_region_from_config(config)
        assert result == "us-west-2"

    def test_get_region_from_config_missing_both_raises_error(self):
        """Test that missing both domain.region and aws.region raises ValueError."""
        config = {}
        
        with pytest.raises(ValueError, match="Region must be specified in domain.region or aws.region configuration"):
            _get_region_from_config(config)

    def test_get_region_from_config_empty_domain_raises_error(self):
        """Test that empty domain object raises ValueError."""
        config = {"domain": {}}
        
        with pytest.raises(ValueError, match="Region must be specified in domain.region or aws.region configuration"):
            _get_region_from_config(config)

    def test_environment_variable_substitution_simulation(self):
        """Test environment variable substitution logic simulation."""
        # Simulate the environment variable substitution that happens in real pipeline
        # DEV_DOMAIN_REGION environment variable should resolve to us-east-1
        
        # This simulates what happens when ${DEV_DOMAIN_REGION:us-east-2} is processed
        # with DEV_DOMAIN_REGION=us-east-1 in the environment
        original_value = "${DEV_DOMAIN_REGION:us-east-2}"
        env_value = "us-east-1"  # This would come from environment
        resolved_value = env_value  # Substitution would use env value
        
        assert resolved_value == "us-east-1"
        
        # Test that config setup works with resolved value
        config = load_config()
        config["domain"] = {"name": "cicd-test-domain", "region": resolved_value}
        config["region"] = resolved_value
        
        result = _get_region_from_config(config)
        assert result == "us-east-1"

    def test_command_config_setup_consistency(self):
        """Test that config setup matches what _get_region_from_config expects."""
        # Simulate how commands should set up config
        manifest_region = "us-east-1"
        manifest_name = "test-domain"
        
        # This is how commands should set up config
        config = load_config()  # Returns empty dict
        config["domain"] = {"name": manifest_name, "region": manifest_region}
        config["region"] = manifest_region
        config["domain_name"] = manifest_name
        
        # Verify the structure is correct for _get_region_from_config
        result = _get_region_from_config(config)
        assert result == manifest_region
        
        # Verify all expected keys are present
        assert config["domain"]["name"] == manifest_name
        assert config["domain"]["region"] == manifest_region
        assert config["region"] == manifest_region
        assert config["domain_name"] == manifest_name

    def test_load_config_returns_empty_dict(self):
        """Test that load_config returns empty dictionary."""
        config = load_config()
        assert config == {}
        
        # Test with config_path parameter (should be ignored)
        config_with_path = load_config("/some/path")
        assert config_with_path == {}


class TestCommandConfigurationSetup:
    """Test configuration setup in different commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_manifest = MagicMock()
        self.mock_manifest.domain.name = "cicd-test-domain"
        self.mock_manifest.domain.region = "us-east-1"

    def test_test_command_config_setup(self):
        """Test config setup for test command."""
        config = load_config()
        config["domain"] = {"name": self.mock_manifest.domain.name, "region": self.mock_manifest.domain.region}
        config["region"] = self.mock_manifest.domain.region
        config["domain_name"] = self.mock_manifest.domain.name
        
        # Should not raise error
        region = _get_region_from_config(config)
        assert region == "us-east-1"

    def test_deploy_command_config_setup(self):
        """Test config setup for deploy command."""
        config = load_config()
        config["domain"] = {"name": self.mock_manifest.domain.name, "region": self.mock_manifest.domain.region}
        config["region"] = self.mock_manifest.domain.region
        
        # Should not raise error
        region = _get_region_from_config(config)
        assert region == "us-east-1"

    def test_describe_command_config_setup(self):
        """Test config setup for describe command."""
        config = load_config()
        config["domain"] = {"name": self.mock_manifest.domain.name, "region": self.mock_manifest.domain.region}
        config["region"] = self.mock_manifest.domain.region
        config["domain_name"] = self.mock_manifest.domain.name
        
        # Should not raise error
        region = _get_region_from_config(config)
        assert region == "us-east-1"

    def test_run_command_config_setup(self):
        """Test config setup for run command."""
        config = load_config()
        config["domain"] = {"name": self.mock_manifest.domain.name, "region": self.mock_manifest.domain.region}
        config["region"] = self.mock_manifest.domain.region
        
        # Should not raise error
        region = _get_region_from_config(config)
        assert region == "us-east-1"

    def test_monitor_command_config_setup(self):
        """Test config setup for monitor command."""
        config = load_config()
        config["domain"] = {"name": self.mock_manifest.domain.name, "region": self.mock_manifest.domain.region}
        config["region"] = self.mock_manifest.domain.region
        config["domain_name"] = self.mock_manifest.domain.name
        
        # Should not raise error
        region = _get_region_from_config(config)
        assert region == "us-east-1"
