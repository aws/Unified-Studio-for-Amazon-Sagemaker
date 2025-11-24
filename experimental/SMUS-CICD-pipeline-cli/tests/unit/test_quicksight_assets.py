"""Unit tests for QuickSight assets configuration."""

import unittest


class TestQuickSightAssetsConfig(unittest.TestCase):
    """Test QuickSight assets configuration parsing."""

    def test_assets_field_dict(self):
        """Test parsing assets from dict config."""
        qs_config = {
            "assets": [
                {
                    "name": "TotalDeathByCountry",
                    "owners": ["arn:aws:quicksight:us-east-1:123:user/default/Admin/*"],
                    "viewers": ["arn:aws:quicksight:us-east-1:123:user/default/User/*"],
                }
            ]
        }

        assets = qs_config.get("assets", [])
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["name"], "TotalDeathByCountry")
        self.assertEqual(len(assets[0]["owners"]), 1)
        self.assertEqual(len(assets[0]["viewers"]), 1)

    def test_assets_field_object(self):
        """Test parsing assets from object config."""

        class MockAsset:
            def __init__(self, name, owners, viewers):
                self.name = name
                self.owners = owners
                self.viewers = viewers

        class MockConfig:
            def __init__(self):
                self.assets = [
                    MockAsset(
                        "TotalDeathByCountry",
                        ["arn:aws:quicksight:us-east-1:123:user/default/Admin/*"],
                        ["arn:aws:quicksight:us-east-1:123:user/default/User/*"],
                    )
                ]

        qs_config = MockConfig()
        assets = getattr(qs_config, "assets", [])
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].name, "TotalDeathByCountry")
        self.assertEqual(len(assets[0].owners), 1)
        self.assertEqual(len(assets[0].viewers), 1)

    def test_assets_field_empty(self):
        """Test handling empty assets config."""
        qs_config = {"assets": []}
        assets = qs_config.get("assets", [])
        self.assertEqual(len(assets), 0)

    def test_assets_field_missing(self):
        """Test handling missing assets field."""
        qs_config = {}
        assets = qs_config.get("assets", [])
        self.assertEqual(len(assets), 0)

    def test_find_matching_asset_by_name(self):
        """Test finding asset by dashboard name."""
        qs_config = {
            "assets": [
                {"name": "Dashboard1", "owners": ["user1"], "viewers": []},
                {"name": "TotalDeathByCountry", "owners": ["user2"], "viewers": ["user3"]},
                {"name": "Dashboard3", "owners": ["user4"], "viewers": []},
            ]
        }

        dashboard_name = "TotalDeathByCountry"
        assets = qs_config.get("assets", [])
        matching_asset = None

        for asset in assets:
            if asset.get("name") == dashboard_name:
                matching_asset = asset
                break

        self.assertIsNotNone(matching_asset)
        self.assertEqual(matching_asset["name"], "TotalDeathByCountry")
        self.assertEqual(matching_asset["owners"], ["user2"])
        self.assertEqual(matching_asset["viewers"], ["user3"])


if __name__ == "__main__":
    unittest.main()
