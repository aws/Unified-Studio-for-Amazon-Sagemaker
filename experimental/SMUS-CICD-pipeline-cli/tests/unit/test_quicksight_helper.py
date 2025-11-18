"""Unit tests for QuickSight helper."""

import unittest
from unittest.mock import MagicMock, patch

from smus_cicd.helpers.quicksight import (
    QuickSightDeploymentError,
    export_dashboard,
    grant_dashboard_permissions,
    import_dashboard,
    poll_export_job,
    poll_import_job,
)


class TestQuickSightHelper(unittest.TestCase):
    """Test QuickSight helper functions."""

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    def test_export_dashboard_success(self, mock_boto_client):
        """Test successful dashboard export."""
        mock_qs = MagicMock()
        mock_qs.start_asset_bundle_export_job.return_value = {
            "AssetBundleExportJobId": "export-123"
        }
        mock_boto_client.return_value = mock_qs

        job_id = export_dashboard("dash-1", "123456789012", "us-east-1")

        self.assertEqual(job_id, "export-123")
        mock_qs.start_asset_bundle_export_job.assert_called_once()

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    def test_export_dashboard_failure(self, mock_boto_client):
        """Test dashboard export failure."""
        mock_qs = MagicMock()
        mock_qs.start_asset_bundle_export_job.side_effect = Exception("API error")
        mock_boto_client.return_value = mock_qs

        with self.assertRaises(QuickSightDeploymentError):
            export_dashboard("dash-1", "123456789012", "us-east-1")

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    @patch("smus_cicd.helpers.quicksight.time.sleep")
    def test_poll_export_job_success(self, mock_sleep, mock_boto_client):
        """Test successful export job polling."""
        mock_qs = MagicMock()
        mock_qs.describe_asset_bundle_export_job.return_value = {
            "JobStatus": "SUCCESSFUL",
            "DownloadUrl": "https://example.com/bundle.zip",
        }
        mock_boto_client.return_value = mock_qs

        url = poll_export_job("export-123", "123456789012", "us-east-1")

        self.assertEqual(url, "https://example.com/bundle.zip")

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    @patch("smus_cicd.helpers.quicksight.time.sleep")
    def test_poll_export_job_failure(self, mock_sleep, mock_boto_client):
        """Test export job polling with failure."""
        mock_qs = MagicMock()
        mock_qs.describe_asset_bundle_export_job.return_value = {
            "JobStatus": "FAILED",
            "Errors": ["Export error"],
        }
        mock_boto_client.return_value = mock_qs

        with self.assertRaises(QuickSightDeploymentError):
            poll_export_job("export-123", "123456789012", "us-east-1")

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    @patch("smus_cicd.helpers.quicksight._download_bundle")
    def test_import_dashboard_success(self, mock_download, mock_boto_client):
        """Test successful dashboard import."""
        mock_download.return_value = b"bundle-content"
        mock_qs = MagicMock()
        mock_qs.start_asset_bundle_import_job.return_value = {
            "AssetBundleImportJobId": "import-456"
        }
        mock_boto_client.return_value = mock_qs

        job_id = import_dashboard(
            "https://example.com/bundle.zip", "123456789012", "us-east-1"
        )

        self.assertEqual(job_id, "import-456")
        mock_qs.start_asset_bundle_import_job.assert_called_once()

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    @patch("smus_cicd.helpers.quicksight.time.sleep")
    def test_poll_import_job_success(self, mock_sleep, mock_boto_client):
        """Test successful import job polling."""
        mock_qs = MagicMock()
        mock_qs.describe_asset_bundle_import_job.return_value = {
            "JobStatus": "SUCCESSFUL",
            "AssetBundleImportJobId": "import-456",
        }
        mock_boto_client.return_value = mock_qs

        result = poll_import_job("import-456", "123456789012", "us-east-1")

        self.assertEqual(result["JobStatus"], "SUCCESSFUL")

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    def test_grant_permissions_success(self, mock_boto_client):
        """Test successful permission grant."""
        mock_qs = MagicMock()
        mock_boto_client.return_value = mock_qs

        permissions = [{"principal": "user1", "actions": ["READ"]}]
        result = grant_dashboard_permissions(
            "dash-1", "123456789012", "us-east-1", permissions
        )

        self.assertTrue(result)
        mock_qs.update_dashboard_permissions.assert_called_once()

    @patch("smus_cicd.helpers.quicksight.boto3.client")
    def test_grant_permissions_empty(self, mock_boto_client):
        """Test permission grant with empty list."""
        result = grant_dashboard_permissions(
            "dash-1", "123456789012", "us-east-1", []
        )

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
