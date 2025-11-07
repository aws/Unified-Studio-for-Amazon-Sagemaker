"""Unit tests for monitoring helpers."""

from unittest.mock import MagicMock

import pytest

from smus_cicd.helpers.monitoring import (
    build_bundle_info,
    build_target_info,
    collect_metadata,
    create_event_emitter,
)
from smus_cicd.pipeline import PipelineManifest


class TestMonitoringHelpers:
    """Test monitoring helper functions."""

    def test_create_event_emitter_default(self):
        """Test creating event emitter with defaults."""
        manifest_data = {
            "pipelineName": "TestPipeline",
            "bundle": {"bundlesDirectory": "./bundles"},
            "targets": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
        }
        manifest = PipelineManifest.from_dict(manifest_data)
        
        emitter = create_event_emitter(manifest, "us-east-1")
        
        assert emitter.enabled is True
        assert emitter.event_bus_name == "default"
        assert emitter.region == "us-east-1"

    def test_create_event_emitter_from_manifest(self):
        """Test creating event emitter from manifest config."""
        manifest_data = {
            "pipelineName": "TestPipeline",
            "bundle": {"bundlesDirectory": "./bundles"},
            "targets": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
            "monitoring": {
                "eventbridge": {
                    "enabled": False,
                    "eventBusName": "custom-bus",
                    "includeMetadata": False,
                }
            },
        }
        manifest = PipelineManifest.from_dict(manifest_data)
        
        emitter = create_event_emitter(manifest, "us-east-1")
        
        assert emitter.enabled is False
        assert emitter.event_bus_name == "custom-bus"

    def test_create_event_emitter_cli_override(self):
        """Test CLI overrides for event emitter."""
        manifest_data = {
            "pipelineName": "TestPipeline",
            "bundle": {"bundlesDirectory": "./bundles"},
            "targets": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
            "monitoring": {"eventbridge": {"enabled": False}},
        }
        manifest = PipelineManifest.from_dict(manifest_data)
        
        emitter = create_event_emitter(manifest, "us-east-1", emit_events=True, event_bus_name="override-bus")
        
        assert emitter.enabled is True
        assert emitter.event_bus_name == "override-bus"

    def test_build_target_info(self):
        """Test building target info."""
        target_config = MagicMock()
        target_config.stage = "TEST"
        target_config.domain.name = "test-domain"
        target_config.domain.region = "us-east-1"
        target_config.project.name = "test-project"
        
        target_info = build_target_info("test", target_config)
        
        assert target_info["name"] == "test"
        assert target_info["stage"] == "TEST"
        assert target_info["domain"]["name"] == "test-domain"
        assert target_info["domain"]["region"] == "us-east-1"
        assert target_info["project"]["name"] == "test-project"

    def test_build_bundle_info(self):
        """Test building bundle info."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            bundle_path = f.name
        
        bundle_info = build_bundle_info(bundle_path)
        
        assert bundle_info["path"] == bundle_path
        assert "size" in bundle_info
        assert bundle_info["size"] > 0

    def test_build_bundle_info_nonexistent(self):
        """Test building bundle info for nonexistent file."""
        bundle_info = build_bundle_info("/nonexistent/bundle.zip")
        
        assert bundle_info["path"] == "/nonexistent/bundle.zip"
        assert "size" not in bundle_info

    def test_collect_metadata_enabled(self):
        """Test metadata collection when enabled."""
        manifest_data = {
            "pipelineName": "TestPipeline",
            "bundle": {"bundlesDirectory": "./bundles"},
            "targets": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
            "monitoring": {"eventbridge": {"includeMetadata": True}},
        }
        manifest = PipelineManifest.from_dict(manifest_data)
        
        metadata = collect_metadata(manifest)
        
        assert metadata is not None
        assert isinstance(metadata, dict)

    def test_collect_metadata_disabled(self):
        """Test metadata collection when disabled."""
        manifest_data = {
            "pipelineName": "TestPipeline",
            "bundle": {"bundlesDirectory": "./bundles"},
            "targets": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
            "monitoring": {"eventbridge": {"includeMetadata": False}},
        }
        manifest = PipelineManifest.from_dict(manifest_data)
        
        metadata = collect_metadata(manifest)
        
        assert metadata is None

    def test_collect_metadata_no_monitoring(self):
        """Test metadata collection when monitoring not configured."""
        manifest_data = {
            "pipelineName": "TestPipeline",
            "bundle": {"bundlesDirectory": "./bundles"},
            "targets": {"test": {"domain": {"region": "us-east-1"}, "project": "test-project"}},
        }
        manifest = PipelineManifest.from_dict(manifest_data)
        
        metadata = collect_metadata(manifest)
        
        assert metadata is None
