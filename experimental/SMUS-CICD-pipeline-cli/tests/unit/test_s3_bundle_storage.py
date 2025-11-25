"""Unit tests for S3 bundle storage functionality."""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.smus_cicd.helpers.bundle_storage import (
    is_s3_url,
    parse_s3_url,
    get_bundle_path,
    ensure_bundle_directory_exists,
    upload_bundle,
    ensure_bundle_local,
    find_bundle_file,
)


class TestS3BundleStorage:
    """Test S3 bundle storage functionality."""

    def test_is_s3_url(self):
        """Test S3 URL detection."""
        assert is_s3_url("s3://my-bucket/path")
        assert is_s3_url("s3://bucket")
        assert not is_s3_url("./local/path")
        assert not is_s3_url("/absolute/path")
        assert not is_s3_url("https://example.com")

    def test_parse_s3_url(self):
        """Test S3 URL parsing."""
        bucket, key = parse_s3_url("s3://my-bucket/path/to/file")
        assert bucket == "my-bucket"
        assert key == "path/to/file"

        bucket, key = parse_s3_url("s3://bucket-only")
        assert bucket == "bucket-only"
        assert key == ""

        bucket, key = parse_s3_url("s3://bucket/")
        assert bucket == "bucket"
        assert key == ""

    def test_get_bundle_path_local(self):
        """Test bundle path generation for local storage."""
        path = get_bundle_path("./bundles", "TestPipeline")
        expected = os.path.join("./bundles", "TestPipeline.zip")
        assert path == expected

    def test_get_bundle_path_s3(self):
        """Test bundle path generation for S3 storage."""
        path = get_bundle_path("s3://my-bucket/bundles", "TestPipeline")
        assert path == "s3://my-bucket/bundles/TestPipeline.zip"

        path = get_bundle_path("s3://my-bucket/bundles/", "TestPipeline")
        assert path == "s3://my-bucket/bundles/TestPipeline.zip"

    def test_ensure_bundle_directory_exists_local(self):
        """Test local directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_dir = os.path.join(temp_dir, "test_bundles")
            ensure_bundle_directory_exists(bundle_dir)
            assert os.path.exists(bundle_dir)

    @patch("src.smus_cicd.helpers.bundle_storage.create_s3_client")
    def test_ensure_bundle_directory_exists_s3(self, mock_create_client):
        """Test S3 bucket validation."""
        mock_s3 = Mock()
        mock_create_client.return_value = mock_s3

        # Test successful validation
        mock_s3.head_bucket.return_value = {}
        ensure_bundle_directory_exists("s3://test-bucket/bundles", "us-east-1")
        mock_s3.head_bucket.assert_called_once_with(Bucket="test-bucket")

        # Test bucket not accessible
        mock_s3.head_bucket.side_effect = Exception("Access denied")
        with pytest.raises(ValueError, match="S3 bucket 'test-bucket' not accessible"):
            ensure_bundle_directory_exists("s3://test-bucket/bundles", "us-east-1")

    def test_upload_bundle_local(self):
        """Test local bundle upload (move)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source bundle
            source_path = os.path.join(temp_dir, "source.zip")
            with open(source_path, "w") as f:
                f.write("test content")

            # Create destination directory
            dest_dir = os.path.join(temp_dir, "bundles")
            os.makedirs(dest_dir)

            # Upload bundle
            result_path = upload_bundle(source_path, dest_dir, "TestPipeline")

            expected_path = os.path.join(dest_dir, "TestPipeline.zip")
            assert result_path == expected_path
            assert os.path.exists(expected_path)
            assert not os.path.exists(source_path)  # Should be moved

    @patch("src.smus_cicd.helpers.bundle_storage.create_s3_client")
    def test_upload_bundle_s3(self, mock_create_client):
        """Test S3 bundle upload."""
        mock_s3 = Mock()
        mock_create_client.return_value = mock_s3

        with tempfile.NamedTemporaryFile(suffix=".zip") as temp_file:
            temp_file.write(b"test content")
            temp_file.flush()

            result_path = upload_bundle(
                temp_file.name, "s3://test-bucket/bundles", "TestPipeline", "us-east-1"
            )

            assert result_path == "s3://test-bucket/bundles/TestPipeline.zip"
            mock_s3.upload_file.assert_called_once_with(
                temp_file.name, "test-bucket", "bundles/TestPipeline.zip"
            )

    def test_ensure_bundle_local_local(self):
        """Test local bundle (no-op)."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file.flush()

            try:
                result_path = ensure_bundle_local(temp_file.name)
                assert result_path == temp_file.name
            finally:
                os.unlink(temp_file.name)

    @patch("src.smus_cicd.helpers.bundle_storage.create_s3_client")
    @patch("tempfile.mkstemp")
    def test_ensure_bundle_local_s3(self, mock_mkstemp, mock_create_client):
        """Test S3 bundle download."""
        mock_s3 = Mock()
        mock_create_client.return_value = mock_s3

        # Mock temporary file creation
        temp_fd = 123
        temp_path = "/tmp/test_bundle.zip"
        mock_mkstemp.return_value = (temp_fd, temp_path)

        with patch("os.close") as mock_close:
            result_path = ensure_bundle_local(
                "s3://test-bucket/bundles/TestPipeline.zip", "us-east-1"
            )

            assert result_path == temp_path
            mock_close.assert_called_once_with(temp_fd)
            mock_s3.download_file.assert_called_once_with(
                "test-bucket", "bundles/TestPipeline.zip", temp_path
            )

    def test_find_bundle_file_local(self):
        """Test finding bundle file locally."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            bundle_file = os.path.join(temp_dir, "TestPipeline.zip")
            other_file = os.path.join(temp_dir, "other.zip")
            non_zip = os.path.join(temp_dir, "readme.txt")

            with open(bundle_file, "w") as f:
                f.write("bundle")
            with open(other_file, "w") as f:
                f.write("other")
            with open(non_zip, "w") as f:
                f.write("readme")

            # Should find exact match
            result = find_bundle_file(temp_dir, "TestPipeline")
            assert result == bundle_file

            # Should find any zip if no exact match
            result = find_bundle_file(temp_dir, "NonExistent")
            assert result in [bundle_file, other_file]

    @patch("src.smus_cicd.helpers.bundle_storage.create_s3_client")
    def test_find_bundle_file_s3(self, mock_create_client):
        """Test finding bundle file in S3."""
        mock_s3 = Mock()
        mock_create_client.return_value = mock_s3

        # Mock S3 response
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "bundles/TestPipeline.zip"},
                {"Key": "bundles/other.zip"},
                {"Key": "bundles/readme.txt"},
            ]
        }

        result = find_bundle_file(
            "s3://test-bucket/bundles", "TestPipeline", "us-east-1"
        )
        assert result == "s3://test-bucket/bundles/TestPipeline.zip"

        mock_s3.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket", Prefix="bundles/", MaxKeys=100
        )

    @patch("src.smus_cicd.helpers.bundle_storage.create_s3_client")
    def test_find_bundle_file_s3_fallback(self, mock_create_client):
        """Test S3 bundle file fallback to any zip."""
        mock_s3 = Mock()
        mock_create_client.return_value = mock_s3

        # Mock S3 response with no exact match
        mock_s3.list_objects_v2.return_value = {
            "Contents": [{"Key": "bundles/other.zip"}, {"Key": "bundles/readme.txt"}]
        }

        result = find_bundle_file(
            "s3://test-bucket/bundles", "NonExistent", "us-east-1"
        )
        assert result == "s3://test-bucket/bundles/other.zip"


class TestS3BundleIntegration:
    """Integration tests using DataZone domain S3 bucket."""

    @pytest.fixture
    def datazone_s3_bucket(self):
        """Get DataZone domain S3 bucket for testing."""
        # This would be the actual DataZone domain bucket
        # Format: sagemaker-unified-studio-{account}-{region}-{domain-name}
        return "s3://sagemaker-unified-studio-<aws-account-id>-us-east-1-test-domain/bundles"

    def test_s3_bundle_workflow(self, datazone_s3_bucket):
        """Test complete S3 bundle workflow with DataZone bucket."""
        # This test would require actual AWS credentials and DataZone setup
        # For now, we'll mock it to show the expected behavior

        with patch(
            "src.smus_cicd.helpers.bundle_storage.create_s3_client"
        ) as mock_create_client:
            mock_s3 = Mock()
            mock_create_client.return_value = mock_s3

            # Test bundle directory validation
            mock_s3.head_bucket.return_value = {}
            ensure_bundle_directory_exists(datazone_s3_bucket, "us-east-1")

            # Test bundle upload
            with tempfile.NamedTemporaryFile(suffix=".zip") as temp_file:
                temp_file.write(b"test bundle content")
                temp_file.flush()

                result_path = upload_bundle(
                    temp_file.name, datazone_s3_bucket, "TestPipeline", "us-east-1"
                )

                expected_path = f"{datazone_s3_bucket}/TestPipeline.zip"
                assert result_path == expected_path

                # Verify S3 upload was called
                mock_s3.upload_file.assert_called_once()
                args = mock_s3.upload_file.call_args[0]
                assert args[0] == temp_file.name  # local file
                assert (
                    args[1]
                    == "sagemaker-unified-studio-<aws-account-id>-us-east-1-test-domain"
                )  # bucket
                assert args[2] == "bundles/TestPipeline.zip"  # key
