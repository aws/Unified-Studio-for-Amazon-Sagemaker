"""Unit tests for StorageConfig dataclass."""

import os
import tempfile

import pytest
import yaml

from smus_cicd.application import ApplicationManifest


class TestStorageConfig:
    """Test StorageConfig parsing and attributes."""

    def create_temp_manifest(self, content: str) -> str:
        """Create a temporary manifest file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            return f.name

    def test_storage_config_has_target_directory_attribute(self):
        """Test that StorageConfig includes targetDirectory field."""
        manifest_dict = {
            "applicationName": "TestApp",
            "content": {
                "storage": [
                    {
                        "name": "notebooks",
                        "connectionName": "default.s3_shared",
                        "include": ["notebooks/"],
                    }
                ]
            },
            "stages": {
                "test": {
                    "domain": {"region": "us-east-1"},
                    "project": {"name": "test-project"},
                    "deployment_configuration": {
                        "storage": [
                            {
                                "name": "notebooks",
                                "connectionName": "default.s3_shared",
                                "targetDirectory": "notebooks/bundle/notebooks",
                            }
                        ]
                    },
                }
            },
        }

        manifest = ApplicationManifest.from_dict(manifest_dict)

        # Verify manifest loaded
        assert manifest is not None
        assert manifest.application_name == "TestApp"

        # Get the storage config
        stage = manifest.stages["test"]
        assert hasattr(stage, "deployment_configuration")
        assert hasattr(stage.deployment_configuration, "storage")

        storage_items = stage.deployment_configuration.storage
        assert len(storage_items) == 1

        storage_config = storage_items[0]

        # Critical assertions
        assert hasattr(
            storage_config, "name"
        ), "StorageConfig missing 'name' attribute"
        assert storage_config.name == "notebooks"

        assert hasattr(
            storage_config, "connectionName"
        ), "StorageConfig missing 'connectionName' attribute"
        assert storage_config.connectionName == "default.s3_shared"

        assert hasattr(
            storage_config, "targetDirectory"
        ), "StorageConfig missing 'targetDirectory' attribute"
        assert storage_config.targetDirectory == "notebooks/bundle/notebooks"

    def test_storage_config_target_directory_optional(self):
        """Test that targetDirectory is optional in StorageConfig."""
        manifest_dict = {
            "applicationName": "TestApp",
            "content": {
                "storage": [
                    {
                        "name": "data",
                        "connectionName": "default.s3_shared",
                        "include": ["data/"],
                    }
                ]
            },
            "stages": {
                "test": {
                    "domain": {"region": "us-east-1"},
                    "project": {"name": "test-project"},
                    "deployment_configuration": {
                        "storage": [
                            {"name": "data", "connectionName": "default.s3_shared"}
                        ]
                    },
                }
            },
        }

        manifest = ApplicationManifest.from_dict(manifest_dict)

        storage_config = manifest.stages["test"].deployment_configuration.storage[0]

        # Should have the attribute but it can be None
        assert hasattr(
            storage_config, "targetDirectory"
        ), "StorageConfig missing 'targetDirectory' attribute"
