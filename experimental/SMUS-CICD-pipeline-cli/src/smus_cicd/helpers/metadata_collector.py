"""Metadata collector for deployment events."""

import os
import subprocess
from typing import Any, Dict, Optional

from .logger import get_logger

logger = get_logger("metadata_collector")


class MetadataCollector:
    """Collect metadata about deployment context."""

    @staticmethod
    def collect() -> Dict[str, Any]:
        """
        Collect all available metadata.

        Returns:
            Dictionary with metadata fields
        """
        metadata = {}

        # User info
        user = MetadataCollector._get_user()
        if user:
            metadata["user"] = user

        # Git info
        git_info = MetadataCollector._get_git_info()
        if git_info:
            metadata.update(git_info)

        # CI/CD platform info
        cicd_info = MetadataCollector._get_cicd_info()
        if cicd_info:
            metadata.update(cicd_info)

        return metadata

    @staticmethod
    def _get_user() -> Optional[str]:
        """Get current user."""
        try:
            return os.environ.get("USER") or os.environ.get("USERNAME")
        except Exception:
            return None

    @staticmethod
    def _get_git_info() -> Dict[str, Any]:
        """Get git repository information."""
        git_info = {}

        try:
            # Git commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                git_info["gitCommit"] = result.stdout.strip()

            # Git branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                git_info["gitBranch"] = result.stdout.strip()

            # Git repository URL
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                git_info["gitRepository"] = result.stdout.strip()

        except Exception as e:
            logger.debug(f"Failed to collect git info: {e}")

        return git_info

    @staticmethod
    def _get_cicd_info() -> Dict[str, Any]:
        """Detect CI/CD platform and collect relevant info."""
        cicd_info = {}

        # GitHub Actions
        if os.environ.get("GITHUB_ACTIONS"):
            cicd_info["cicdPlatform"] = "github-actions"
            if run_id := os.environ.get("GITHUB_RUN_ID"):
                cicd_info["runId"] = run_id
            if repo := os.environ.get("GITHUB_REPOSITORY"):
                cicd_info["runUrl"] = f"https://github.com/{repo}/actions/runs/{run_id}"

        # GitLab CI
        elif os.environ.get("GITLAB_CI"):
            cicd_info["cicdPlatform"] = "gitlab-ci"
            if pipeline_id := os.environ.get("CI_PIPELINE_ID"):
                cicd_info["runId"] = pipeline_id
            if project_url := os.environ.get("CI_PROJECT_URL"):
                cicd_info["runUrl"] = f"{project_url}/-/pipelines/{pipeline_id}"

        # Jenkins
        elif os.environ.get("JENKINS_URL"):
            cicd_info["cicdPlatform"] = "jenkins"
            if build_number := os.environ.get("BUILD_NUMBER"):
                cicd_info["runId"] = build_number
            if build_url := os.environ.get("BUILD_URL"):
                cicd_info["runUrl"] = build_url

        # CircleCI
        elif os.environ.get("CIRCLECI"):
            cicd_info["cicdPlatform"] = "circleci"
            if build_num := os.environ.get("CIRCLE_BUILD_NUM"):
                cicd_info["runId"] = build_num
            if build_url := os.environ.get("CIRCLE_BUILD_URL"):
                cicd_info["runUrl"] = build_url

        # AWS CodeBuild
        elif os.environ.get("CODEBUILD_BUILD_ID"):
            cicd_info["cicdPlatform"] = "aws-codebuild"
            if build_id := os.environ.get("CODEBUILD_BUILD_ID"):
                cicd_info["runId"] = build_id

        # Travis CI
        elif os.environ.get("TRAVIS"):
            cicd_info["cicdPlatform"] = "travis-ci"
            if build_number := os.environ.get("TRAVIS_BUILD_NUMBER"):
                cicd_info["runId"] = build_number
            if build_url := os.environ.get("TRAVIS_BUILD_WEB_URL"):
                cicd_info["runUrl"] = build_url

        return cicd_info
