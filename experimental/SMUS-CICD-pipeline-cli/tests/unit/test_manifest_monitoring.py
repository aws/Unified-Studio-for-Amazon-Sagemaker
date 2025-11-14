"""Unit tests for pipeline manifest monitoring configuration."""

import pytest

from smus_cicd.application import ApplicationManifest


class TestManifestMonitoring:
    """Test monitoring configuration in pipeline manifest."""

    def test_manifest_without_monitoring(self):
        """Test manifest without monitoring configuration."""
        manifest_data = {
            "applicationName": "TestPipeline",
            "content": {"bundlesDirectory": "./bundles"},
            "stages": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
        }
        
        manifest = ApplicationManifest.from_dict(manifest_data)
        
        assert manifest.monitoring is None

    def test_manifest_with_monitoring_enabled(self):
        """Test manifest with monitoring enabled."""
        manifest_data = {
            "applicationName": "TestPipeline",
            "content": {"bundlesDirectory": "./bundles"},
            "stages": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
            "monitoring": {
                "eventbridge": {
                    "enabled": True,
                    "eventBusName": "default",
                    "includeMetadata": True,
                }
            },
        }
        
        manifest = ApplicationManifest.from_dict(manifest_data)
        
        assert manifest.monitoring is not None
        assert manifest.monitoring.eventbridge is not None
        assert manifest.monitoring.eventbridge.enabled is True
        assert manifest.monitoring.eventbridge.eventBusName == "default"
        assert manifest.monitoring.eventbridge.includeMetadata is True

    def test_manifest_with_monitoring_disabled(self):
        """Test manifest with monitoring disabled."""
        manifest_data = {
            "applicationName": "TestPipeline",
            "content": {"bundlesDirectory": "./bundles"},
            "stages": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
            "monitoring": {
                "eventbridge": {
                    "enabled": False,
                }
            },
        }
        
        manifest = ApplicationManifest.from_dict(manifest_data)
        
        assert manifest.monitoring is not None
        assert manifest.monitoring.eventbridge is not None
        assert manifest.monitoring.eventbridge.enabled is False

    def test_manifest_with_custom_event_bus(self):
        """Test manifest with custom event bus."""
        manifest_data = {
            "applicationName": "TestPipeline",
            "content": {"bundlesDirectory": "./bundles"},
            "stages": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
            "monitoring": {
                "eventbridge": {
                    "enabled": True,
                    "eventBusName": "arn:aws:events:us-east-1:123456789012:event-bus/custom-bus",
                }
            },
        }
        
        manifest = ApplicationManifest.from_dict(manifest_data)
        
        assert manifest.monitoring.eventbridge.eventBusName == "arn:aws:events:us-east-1:123456789012:event-bus/custom-bus"

    def test_manifest_monitoring_defaults(self):
        """Test manifest monitoring with default values."""
        manifest_data = {
            "applicationName": "TestPipeline",
            "content": {"bundlesDirectory": "./bundles"},
            "stages": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
            "monitoring": {
                "eventbridge": {}
            },
        }
        
        manifest = ApplicationManifest.from_dict(manifest_data)
        
        assert manifest.monitoring.eventbridge.enabled is True
        assert manifest.monitoring.eventbridge.eventBusName == "default"
        assert manifest.monitoring.eventbridge.includeMetadata is True
