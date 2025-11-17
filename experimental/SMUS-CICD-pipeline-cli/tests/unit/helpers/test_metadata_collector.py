"""Unit tests for MetadataCollector."""

from unittest.mock import patch

import pytest

from smus_cicd.helpers.metadata_collector import MetadataCollector


class TestMetadataCollector:
    """Test MetadataCollector class."""

    @patch.dict("os.environ", {"USER": "testuser"})
    def test_get_user(self):
        """Test user collection."""
        user = MetadataCollector._get_user()
        assert user == "testuser"

    @patch("smus_cicd.helpers.metadata_collector.subprocess.run")
    def test_get_git_info_success(self, mock_run):
        """Test successful git info collection."""
        mock_run.side_effect = [
            type("obj", (object,), {"returncode": 0, "stdout": "abc123\n"}),
            type("obj", (object,), {"returncode": 0, "stdout": "main\n"}),
            type("obj", (object,), {"returncode": 0, "stdout": "https://github.com/test/repo.git\n"}),
        ]
        
        git_info = MetadataCollector._get_git_info()
        
        assert git_info["gitCommit"] == "abc123"
        assert git_info["gitBranch"] == "main"
        assert git_info["gitRepository"] == "https://github.com/test/repo.git"

    @patch("smus_cicd.helpers.metadata_collector.subprocess.run")
    def test_get_git_info_failure(self, mock_run):
        """Test git info collection when git fails."""
        mock_run.side_effect = Exception("Git not found")
        
        git_info = MetadataCollector._get_git_info()
        
        assert git_info == {}

    @patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "12345", "GITHUB_REPOSITORY": "test/repo"})
    def test_get_cicd_info_github(self):
        """Test CI/CD info collection for GitHub Actions."""
        cicd_info = MetadataCollector._get_cicd_info()
        
        assert cicd_info["cicdPlatform"] == "github-actions"
        assert cicd_info["runId"] == "12345"
        assert cicd_info["runUrl"] == "https://github.com/test/repo/actions/runs/12345"

    @patch.dict("os.environ", {"GITLAB_CI": "true", "CI_PIPELINE_ID": "67890", "CI_PROJECT_URL": "https://gitlab.com/test/repo"}, clear=True)
    def test_get_cicd_info_gitlab(self):
        """Test CI/CD info collection for GitLab CI."""
        cicd_info = MetadataCollector._get_cicd_info()
        
        assert cicd_info["cicdPlatform"] == "gitlab-ci"
        assert cicd_info["runId"] == "67890"
        assert cicd_info["runUrl"] == "https://gitlab.com/test/repo/-/pipelines/67890"

    @patch.dict("os.environ", {}, clear=True)
    def test_get_cicd_info_none(self):
        """Test CI/CD info collection when no CI/CD platform detected."""
        cicd_info = MetadataCollector._get_cicd_info()
        
        assert cicd_info == {}

    @patch.dict("os.environ", {"USER": "testuser"})
    @patch("smus_cicd.helpers.metadata_collector.subprocess.run")
    def test_collect(self, mock_run):
        """Test full metadata collection."""
        mock_run.side_effect = [
            type("obj", (object,), {"returncode": 0, "stdout": "abc123\n"}),
            type("obj", (object,), {"returncode": 0, "stdout": "main\n"}),
            type("obj", (object,), {"returncode": 0, "stdout": "https://github.com/test/repo.git\n"}),
        ]
        
        metadata = MetadataCollector.collect()
        
        assert "user" in metadata
        assert metadata["user"] == "testuser"
        assert "gitCommit" in metadata
        assert metadata["gitCommit"] == "abc123"
