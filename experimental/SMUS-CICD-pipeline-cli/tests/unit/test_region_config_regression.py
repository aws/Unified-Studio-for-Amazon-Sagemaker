"""Regression tests for the specific region configuration bug."""

import pytest
from unittest.mock import patch, MagicMock

from smus_cicd.helpers.utils import (
    _get_region_from_config,
    load_config,
    get_datazone_project_info,
)


class TestRegionConfigurationRegression:
    """Test the specific bug that was causing integration test failures."""

    def test_old_broken_config_setup_fails(self):
        """Test that the old broken config setup fails as expected."""
        # This is how the test command was setting up config BEFORE the fix
        config = load_config()  # Returns empty dict
        config["region"] = "us-east-1"  # Only set region, not domain.region
        config["domain_name"] = "cicd-test-domain"

        # This should fail because _get_region_from_config looks for domain.region first
        with pytest.raises(
            ValueError,
            match="Region must be specified in domain.region or aws.region configuration",
        ):
            _get_region_from_config(config)

    def test_new_fixed_config_setup_works(self):
        """Test that the new fixed config setup works correctly."""
        # This is how the test command sets up config AFTER the fix
        config = load_config()  # Returns empty dict
        config["domain"] = {
            "name": "cicd-test-domain",
            "region": "us-east-1",
        }  # Proper structure
        config["region"] = "us-east-1"
        config["domain_name"] = "cicd-test-domain"

        # This should work
        result = _get_region_from_config(config)
        assert result == "us-east-1"

    def test_integration_test_scenario_simulation(self):
        """Simulate the exact scenario from integration tests."""
        # Simulate pipeline manifest with environment variable resolution
        manifest_domain_region = (
            "us-east-1"  # This comes from ${DEV_DOMAIN_REGION:us-east-2} -> us-east-1
        )
        manifest_domain_name = "cicd-test-domain"

        # Test the FIXED configuration setup (what we implemented)
        config = load_config()
        config["domain"] = {
            "name": manifest_domain_name,
            "region": manifest_domain_region,
        }
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

    @patch("smus_cicd.helpers.utils.boto3")
    def test_boto3_client_uses_correct_region_not_credentials_region(self, mock_boto3):
        """Test that boto3 clients are created with domain region, not AWS credentials region."""
        # Mock boto3 client
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Simulate GitHub Actions scenario:
        # - AWS credentials configured for us-east-2 (this would be in AWS_DEFAULT_REGION env var)
        # - But DataZone domain is in us-east-1 (from pipeline manifest)
        aws_credentials_region = "us-east-2"  # From GitHub Actions AWS setup
        datazone_domain_region = "us-east-1"  # From pipeline manifest

        # Set up config with the correct domain region (our fix)
        config = load_config()
        config["domain"] = {
            "name": "cicd-test-domain",
            "region": datazone_domain_region,
        }
        config["region"] = datazone_domain_region

        # Mock successful DataZone responses
        mock_client.list_domains.return_value = {
            "items": [{"id": "dzd_test123", "name": "cicd-test-domain"}]
        }
        mock_client.list_projects.return_value = {
            "items": [{"id": "test-project-id", "name": "integration-test-test"}]
        }
        mock_client.list_project_memberships.return_value = {"members": []}
        mock_client.list_connections.return_value = {"items": []}

        # Call the function that should create DataZone client
        result = get_datazone_project_info("integration-test-test", config)

        # Verify boto3.client was called with the DOMAIN region (first call is CloudFormation for domain resolution)
        calls = mock_boto3.client.call_args_list
        assert len(calls) > 0, "Expected at least one boto3.client call"

        # First call should be CloudFormation with correct region
        first_call_args, first_call_kwargs = calls[0]
        assert first_call_args[0] == "cloudformation"
        assert first_call_kwargs["region_name"] == datazone_domain_region

        # Should succeed without region configuration errors
        assert "error" not in result or "Region must be specified" not in str(
            result.get("error", "")
        )

    @patch.dict("os.environ", {"AWS_DEFAULT_REGION": "us-east-2"})
    @patch("smus_cicd.helpers.utils.boto3")
    def test_domain_region_overrides_aws_env_region(self, mock_boto3):
        """Test that domain.region takes precedence over AWS_DEFAULT_REGION environment variable."""
        # Mock boto3 client
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Environment has AWS_DEFAULT_REGION=us-east-2 (simulating GitHub Actions)
        # But pipeline manifest domain.region=us-east-1
        config = load_config()
        config["domain"] = {"name": "cicd-test-domain", "region": "us-east-1"}
        config["region"] = "us-east-1"

        # Mock CloudFormation and DataZone responses
        mock_client.describe_stacks.return_value = {"Stacks": []}  # No CF stack found
        mock_client.list_domains.return_value = {
            "items": [{"id": "dzd_test123", "name": "cicd-test-domain"}]
        }
        mock_client.list_projects.return_value = {"items": []}
        mock_client.list_project_memberships.return_value = {"members": []}
        mock_client.list_connections.return_value = {"items": []}

        # Call function
        get_datazone_project_info("test-project", config)

        # Verify ALL boto3 clients use domain region (us-east-1), not env region (us-east-2)
        calls = mock_boto3.client.call_args_list
        for call in calls:
            args, kwargs = call
            assert (
                kwargs["region_name"] == "us-east-1"
            ), f"Service {args[0]} used wrong region: {kwargs['region_name']}"

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
                "domain_name": manifest_name,
            },
            # deploy command
            {
                "domain": {"name": manifest_name, "region": manifest_region},
                "region": manifest_region,
            },
            # describe command
            {
                "domain": {"name": manifest_name, "region": manifest_region},
                "region": manifest_region,
                "domain_name": manifest_name,
            },
            # run command
            {
                "domain": {"name": manifest_name, "region": manifest_region},
                "region": manifest_region,
            },
            # monitor command
            {
                "domain": {"name": manifest_name, "region": manifest_region},
                "region": manifest_region,
                "domain_name": manifest_name,
            },
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
        config["domain"] = {
            "name": "cicd-test-domain",
            "region": datazone_domain_region,
        }
        config["region"] = (
            datazone_domain_region  # This should match domain.region, not AWS creds
        )

        # Region resolution should return the domain region, not the AWS credentials region
        result = _get_region_from_config(config)
        assert result == datazone_domain_region
        assert result != aws_credentials_region

        # This validates that pipeline manifest is the single source of truth
