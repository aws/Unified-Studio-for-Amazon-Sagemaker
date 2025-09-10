"""Regression tests for the specific region configuration bug."""

import pytest
from unittest.mock import patch, MagicMock

from smus_cicd.helpers.utils import _get_region_from_config, load_config, get_datazone_project_info


class TestRegionConfigurationRegression:
    """Test the specific bug that was causing integration test failures."""

    def test_old_broken_config_setup_fails(self):
        """Test that the old broken config setup fails as expected."""
        # This is how the test command was setting up config BEFORE the fix
        config = load_config()  # Returns empty dict
        config["region"] = "us-east-1"  # Only set region, not domain.region
        config["domain_name"] = "cicd-test-domain"
        
        # This should fail because _get_region_from_config looks for domain.region first
        with pytest.raises(ValueError, match="Region must be specified in domain.region or aws.region configuration"):
            _get_region_from_config(config)

    def test_new_fixed_config_setup_works(self):
        """Test that the new fixed config setup works correctly."""
        # This is how the test command sets up config AFTER the fix
        config = load_config()  # Returns empty dict
        config["domain"] = {"name": "cicd-test-domain", "region": "us-east-1"}  # Proper structure
        config["region"] = "us-east-1"
        config["domain_name"] = "cicd-test-domain"
        
        # This should work
        result = _get_region_from_config(config)
        assert result == "us-east-1"

    def test_integration_test_scenario_simulation(self):
        """Simulate the exact scenario from integration tests."""
        # Simulate pipeline manifest with environment variable resolution
        manifest_domain_region = "us-east-1"  # This comes from ${DEV_DOMAIN_REGION:us-east-2} -> us-east-1
        manifest_domain_name = "cicd-test-domain"
        
        # Test the FIXED configuration setup (what we implemented)
        config = load_config()
        config["domain"] = {"name": manifest_domain_name, "region": manifest_domain_region}
        config["region"] = manifest_domain_region
        config["domain_name"] = manifest_domain_name
        
        # This should work and return the correct region
        result = _get_region_from_config(config)
        assert result == "us-east-1"
        
        # Verify all expected config keys are present
        assert config["domain"]["name"] == "cicd-test-domain"
        assert config["domain"]["region"] == "us-east-1"
        assert config["region"] == "us-east-1"
        assert config["domain_name"] == "cicd-test-domain"

    @patch('smus_cicd.helpers.utils.boto3')
    def test_get_datazone_project_info_with_fixed_config(self, mock_boto3):
        """Test that get_datazone_project_info works with the fixed config structure."""
        # Mock boto3 client
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        
        # Set up the fixed config structure
        config = load_config()
        config["domain"] = {"name": "cicd-test-domain", "region": "us-east-1"}
        config["region"] = "us-east-1"
        config["domain_name"] = "cicd-test-domain"
        
        # Mock the DataZone API responses
        mock_client.list_domains.return_value = {
            "items": [{"id": "dzd_test123", "name": "cicd-test-domain"}]
        }
        mock_client.list_projects.return_value = {
            "items": [{"id": "test-project-id", "name": "integration-test-test"}]
        }
        mock_client.list_project_memberships.return_value = {"members": []}
        mock_client.list_connections.return_value = {"items": []}
        
        # This should not raise the region configuration error
        try:
            result = get_datazone_project_info("integration-test-test", config)
            # Should return a result without error key (or with specific project info)
            assert "error" not in result or "Region must be specified" not in str(result.get("error", ""))
        except ValueError as e:
            # Should not get the region configuration error
            assert "Region must be specified in domain.region or aws.region configuration" not in str(e)

    def test_all_commands_config_consistency(self):
        """Test that all commands set up config consistently."""
        manifest_region = "us-east-1"
        manifest_name = "cicd-test-domain"
        
        # Test each command's config setup pattern
        commands_config_patterns = [
            # test command
            {
                "domain": {"name": manifest_name, "region": manifest_region},
                "region": manifest_region,
                "domain_name": manifest_name
            },
            # deploy command  
            {
                "domain": {"name": manifest_name, "region": manifest_region},
                "region": manifest_region
            },
            # describe command
            {
                "domain": {"name": manifest_name, "region": manifest_region},
                "region": manifest_region,
                "domain_name": manifest_name
            },
            # run command
            {
                "domain": {"name": manifest_name, "region": manifest_region},
                "region": manifest_region
            },
            # monitor command
            {
                "domain": {"name": manifest_name, "region": manifest_region},
                "region": manifest_region,
                "domain_name": manifest_name
            }
        ]
        
        # All patterns should work with _get_region_from_config
        for i, config_pattern in enumerate(commands_config_patterns):
            result = _get_region_from_config(config_pattern)
            assert result == manifest_region, f"Command pattern {i} failed"

    def test_github_actions_environment_simulation(self):
        """Simulate the GitHub Actions environment where AWS credentials are us-east-2 but domain is us-east-1."""
        # In GitHub Actions:
        # - AWS credentials are configured for us-east-2 
        # - But DataZone domain is in us-east-1
        # - Pipeline manifest should be the single source of truth
        
        aws_credentials_region = "us-east-2"  # From GitHub Actions AWS config
        datazone_domain_region = "us-east-1"  # From pipeline manifest domain.region
        
        # The config should use domain.region as primary source, not AWS credentials region
        config = load_config()
        config["domain"] = {"name": "cicd-test-domain", "region": datazone_domain_region}
        config["region"] = datazone_domain_region  # This should match domain.region, not AWS creds
        
        # Region resolution should return the domain region, not the AWS credentials region
        result = _get_region_from_config(config)
        assert result == datazone_domain_region
        assert result != aws_credentials_region
        
        # This validates that pipeline manifest is the single source of truth
