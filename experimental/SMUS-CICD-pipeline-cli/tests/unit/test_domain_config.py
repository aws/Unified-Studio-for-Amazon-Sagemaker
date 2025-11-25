"""Unit tests for DomainConfig class."""

import pytest
from unittest.mock import patch
from smus_cicd.application.application_manifest import DomainConfig


class TestDomainConfigGetName:
    """Test DomainConfig.get_name() method."""

    def test_get_name_with_explicit_name(self):
        """Test get_name returns explicit name when set."""
        config = DomainConfig(name="my-domain", region="us-east-1")
        assert config.get_name() == "my-domain"

    def test_get_name_with_tags_resolves_from_api(self):
        """Test get_name resolves domain name from tags via API."""
        config = DomainConfig(
            tags={"purpose": "smus-cicd-testing"}, region="us-east-2"
        )

        with patch("smus_cicd.helpers.datazone.resolve_domain_id") as mock_resolve:
            mock_resolve.return_value = ("dzd-123456", "resolved-domain-name")
            result = config.get_name()

        assert result == "resolved-domain-name"
        mock_resolve.assert_called_once_with(
            domain_tags={"purpose": "smus-cicd-testing"}, region="us-east-2"
        )

    def test_get_name_with_tags_returns_none_when_not_found(self):
        """Test get_name returns None when domain not found by tags."""
        config = DomainConfig(tags={"purpose": "nonexistent"}, region="us-east-1")

        with patch("smus_cicd.helpers.datazone.resolve_domain_id") as mock_resolve:
            mock_resolve.return_value = (None, None)
            result = config.get_name()

        assert result is None

    def test_get_name_prefers_explicit_name_over_tags(self):
        """Test get_name prefers explicit name even when tags are present."""
        config = DomainConfig(
            name="explicit-name",
            tags={"purpose": "test"},
            region="us-east-1",
        )

        # Should not call resolve_domain_id since name is set
        with patch("smus_cicd.helpers.datazone.resolve_domain_id") as mock_resolve:
            result = config.get_name()

        assert result == "explicit-name"
        mock_resolve.assert_not_called()

    def test_get_name_returns_none_when_no_name_or_tags(self):
        """Test get_name returns None when neither name nor tags are set."""
        config = DomainConfig(region="us-east-1")
        assert config.get_name() is None
# Trigger workflow - Fri Nov 21 16:56:07 EST 2025
