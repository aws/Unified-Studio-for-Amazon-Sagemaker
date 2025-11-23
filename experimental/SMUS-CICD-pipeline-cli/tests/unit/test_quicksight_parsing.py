"""Unit tests for QuickSight manifest parsing."""

import unittest

from smus_cicd.application.application_manifest import ApplicationManifest


class TestQuickSightParsing(unittest.TestCase):
    """Test QuickSight manifest parsing."""

    def test_parse_quicksight_in_content(self):
        """Test parsing QuickSight in content section."""
        manifest_data = {
            "applicationName": "test-app",
            "content": {
                "quicksight": [
                    {
                        "name": "dashboard-123",
                        "type": "dashboard",
                        "assetBundle": "export",
                        "overrideParameters": {"param1": "value1"},
                        "permissions": [
                            {"principal": "user1", "actions": ["READ"]}
                        ],
                    }
                ]
            },
            "stages": {
                "dev": {
                    "domain": {"region": "us-east-1"},
                    "project": {"name": "test-project"},
                }
            },
        }

        manifest = ApplicationManifest.from_dict(manifest_data)
        self.assertEqual(len(manifest.content.quicksight), 1)
        qs = manifest.content.quicksight[0]
        self.assertEqual(qs.name, "dashboard-123")
        self.assertEqual(qs.assetBundle, "export")
        self.assertEqual(qs.overrideParameters, {"param1": "value1"})
        self.assertEqual(len(qs.permissions), 1)

    def test_parse_quicksight_in_stage(self):
        """Test parsing QuickSight in stage section."""
        manifest_data = {
            "applicationName": "test-app",
            "content": {},
            "stages": {
                "dev": {
                    "domain": {"region": "us-east-1"},
                    "project": {"name": "test-project"},
                    "quicksight": [
                        {
                            "name": "dashboard-456",
                            "type": "dashboard",
                            "assetBundle": "quicksight/bundle.qs",
                            "overrideParameters": {"env": "dev"},
                        }
                    ],
                }
            },
        }

        manifest = ApplicationManifest.from_dict(manifest_data)
        stage = manifest.get_stage("dev")
        self.assertEqual(len(stage.quicksight), 1)
        qs = stage.quicksight[0]
        self.assertEqual(qs.name, "dashboard-456")
        self.assertEqual(qs.assetBundle, "quicksight/bundle.qs")
        self.assertEqual(qs.overrideParameters, {"env": "dev"})

    def test_parse_multiple_quicksight_dashboards(self):
        """Test parsing multiple QuickSight dashboards."""
        manifest_data = {
            "applicationName": "test-app",
            "content": {
                "quicksight": [
                    {"name": "dash-1", "type": "dashboard", "assetBundle": "export"},
                    {"name": "dash-2", "type": "dashboard", "assetBundle": "quicksight/dash2.qs"},
                ]
            },
            "stages": {
                "dev": {
                    "domain": {"region": "us-east-1"},
                    "project": {"name": "test-project"},
                }
            },
        }

        manifest = ApplicationManifest.from_dict(manifest_data)
        self.assertEqual(len(manifest.content.quicksight), 2)
        self.assertEqual(manifest.content.quicksight[0].name, "dash-1")
        self.assertEqual(manifest.content.quicksight[1].name, "dash-2")

    def test_parse_quicksight_defaults(self):
        """Test QuickSight default values."""
        manifest_data = {
            "applicationName": "test-app",
            "content": {
                "quicksight": [
                    {"name": "dashboard-789", "type": "dashboard"}  # Minimal config
                ]
            },
            "stages": {
                "dev": {
                    "domain": {"region": "us-east-1"},
                    "project": {"name": "test-project"},
                }
            },
        }

        manifest = ApplicationManifest.from_dict(manifest_data)
        qs = manifest.content.quicksight[0]
        self.assertEqual(qs.assetBundle, "export")  # Default
        self.assertEqual(qs.overrideParameters, {})  # Default
        self.assertEqual(qs.permissions, [])  # Default


if __name__ == "__main__":
    unittest.main()
