"""Unit tests for QuickSight permissions handling during import."""

import unittest
from unittest.mock import MagicMock, patch, call

from smus_cicd.helpers.quicksight import import_dashboard


class TestQuickSightPermissionsImport(unittest.TestCase):
    """Test QuickSight permissions are correctly passed during import."""

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    @patch("smus_cicd.helpers.quicksight._download_bundle")
    def test_import_with_no_permissions(self, mock_download, mock_boto_client):
        """Test import with no permissions uses empty dict."""
        mock_qs = MagicMock()
        mock_qs.start_asset_bundle_import_job.return_value = {
            "AssetBundleImportJobId": "test-job-123"
        }
        mock_boto_client.return_value = mock_qs
        mock_download.return_value = b"bundle_data"

        job_id = import_dashboard(
            "s3://bucket/bundle.qs",
            "123456789012",
            "us-east-1",
            permissions=None,
        )

        self.assertEqual(job_id, "test-job-123")
        
        # Verify OverridePermissions.Dashboards has empty Permissions
        call_args = mock_qs.start_asset_bundle_import_job.call_args
        override_perms = call_args[1]["OverridePermissions"]
        dashboard_perms = override_perms["Dashboards"][0]["Permissions"]
        self.assertEqual(dashboard_perms, {})

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    @patch("smus_cicd.helpers.quicksight._download_bundle")
    def test_import_with_single_owner(self, mock_download, mock_boto_client):
        """Test import with single owner permission."""
        mock_qs = MagicMock()
        mock_qs.start_asset_bundle_import_job.return_value = {
            "AssetBundleImportJobId": "test-job-123"
        }
        mock_boto_client.return_value = mock_qs
        mock_download.return_value = b"bundle_data"

        permissions = [
            {
                "principal": "arn:aws:quicksight:us-east-1:123:user/default/Admin/*",
                "actions": [
                    "quicksight:DescribeDashboard",
                    "quicksight:UpdateDashboard",
                ],
            }
        ]

        job_id = import_dashboard(
            "s3://bucket/bundle.qs",
            "123456789012",
            "us-east-1",
            permissions=permissions,
        )

        self.assertEqual(job_id, "test-job-123")
        
        # Verify OverridePermissions.Dashboards has correct structure
        call_args = mock_qs.start_asset_bundle_import_job.call_args
        override_perms = call_args[1]["OverridePermissions"]
        dashboard_perms = override_perms["Dashboards"][0]["Permissions"]
        
        self.assertIn("Principals", dashboard_perms)
        self.assertIn("Actions", dashboard_perms)
        self.assertEqual(len(dashboard_perms["Principals"]), 1)
        self.assertEqual(
            dashboard_perms["Principals"][0],
            "arn:aws:quicksight:us-east-1:123:user/default/Admin/*",
        )
        self.assertEqual(len(dashboard_perms["Actions"]), 2)
        self.assertIn("quicksight:DescribeDashboard", dashboard_perms["Actions"])
        self.assertIn("quicksight:UpdateDashboard", dashboard_perms["Actions"])

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    @patch("smus_cicd.helpers.quicksight._download_bundle")
    def test_import_with_multiple_principals(self, mock_download, mock_boto_client):
        """Test import with multiple principals (owners and viewers)."""
        mock_qs = MagicMock()
        mock_qs.start_asset_bundle_import_job.return_value = {
            "AssetBundleImportJobId": "test-job-123"
        }
        mock_boto_client.return_value = mock_qs
        mock_download.return_value = b"bundle_data"

        permissions = [
            {
                "principal": "arn:aws:quicksight:us-east-1:123:user/default/Admin/*",
                "actions": [
                    "quicksight:DescribeDashboard",
                    "quicksight:UpdateDashboard",
                    "quicksight:DeleteDashboard",
                ],
            },
            {
                "principal": "arn:aws:quicksight:us-east-1:123:user/default/Viewer/*",
                "actions": [
                    "quicksight:DescribeDashboard",
                    "quicksight:QueryDashboard",
                ],
            },
        ]

        job_id = import_dashboard(
            "s3://bucket/bundle.qs",
            "123456789012",
            "us-east-1",
            permissions=permissions,
        )

        self.assertEqual(job_id, "test-job-123")
        
        # Verify OverridePermissions.Dashboards has correct structure
        call_args = mock_qs.start_asset_bundle_import_job.call_args
        override_perms = call_args[1]["OverridePermissions"]
        dashboard_perms = override_perms["Dashboards"][0]["Permissions"]
        
        self.assertIn("Principals", dashboard_perms)
        self.assertIn("Actions", dashboard_perms)
        self.assertEqual(len(dashboard_perms["Principals"]), 2)
        self.assertIn(
            "arn:aws:quicksight:us-east-1:123:user/default/Admin/*",
            dashboard_perms["Principals"],
        )
        self.assertIn(
            "arn:aws:quicksight:us-east-1:123:user/default/Viewer/*",
            dashboard_perms["Principals"],
        )
        
        # Actions should be deduplicated
        self.assertIn("quicksight:DescribeDashboard", dashboard_perms["Actions"])
        self.assertIn("quicksight:UpdateDashboard", dashboard_perms["Actions"])
        self.assertIn("quicksight:DeleteDashboard", dashboard_perms["Actions"])
        self.assertIn("quicksight:QueryDashboard", dashboard_perms["Actions"])

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    @patch("smus_cicd.helpers.quicksight._download_bundle")
    def test_import_with_duplicate_actions(self, mock_download, mock_boto_client):
        """Test that duplicate actions are removed."""
        mock_qs = MagicMock()
        mock_qs.start_asset_bundle_import_job.return_value = {
            "AssetBundleImportJobId": "test-job-123"
        }
        mock_boto_client.return_value = mock_qs
        mock_download.return_value = b"bundle_data"

        permissions = [
            {
                "principal": "arn:aws:quicksight:us-east-1:123:user/default/User1/*",
                "actions": ["quicksight:DescribeDashboard", "quicksight:QueryDashboard"],
            },
            {
                "principal": "arn:aws:quicksight:us-east-1:123:user/default/User2/*",
                "actions": ["quicksight:DescribeDashboard", "quicksight:UpdateDashboard"],
            },
        ]

        import_dashboard(
            "s3://bucket/bundle.qs",
            "123456789012",
            "us-east-1",
            permissions=permissions,
        )

        # Verify actions are deduplicated
        call_args = mock_qs.start_asset_bundle_import_job.call_args
        override_perms = call_args[1]["OverridePermissions"]
        dashboard_perms = override_perms["Dashboards"][0]["Permissions"]
        actions = dashboard_perms["Actions"]
        
        # Should have 3 unique actions
        self.assertEqual(len(actions), 3)
        self.assertIn("quicksight:DescribeDashboard", actions)
        self.assertIn("quicksight:QueryDashboard", actions)
        self.assertIn("quicksight:UpdateDashboard", actions)

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    @patch("smus_cicd.helpers.quicksight._download_bundle")
    def test_import_with_empty_permissions_list(self, mock_download, mock_boto_client):
        """Test import with empty permissions list."""
        mock_qs = MagicMock()
        mock_qs.start_asset_bundle_import_job.return_value = {
            "AssetBundleImportJobId": "test-job-123"
        }
        mock_boto_client.return_value = mock_qs
        mock_download.return_value = b"bundle_data"

        job_id = import_dashboard(
            "s3://bucket/bundle.qs",
            "123456789012",
            "us-east-1",
            permissions=[],
        )

        self.assertEqual(job_id, "test-job-123")
        
        # Empty list should result in empty dict
        call_args = mock_qs.start_asset_bundle_import_job.call_args
        override_perms = call_args[1]["OverridePermissions"]
        dashboard_perms = override_perms["Dashboards"][0]["Permissions"]
        self.assertEqual(dashboard_perms, {})


if __name__ == "__main__":
    unittest.main()
