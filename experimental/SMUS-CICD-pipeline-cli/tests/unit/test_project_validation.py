"""Test project existence validation."""

import pytest
from smus_cicd.helpers.utils import validate_project_exists


def test_validate_project_not_found_without_create():
    """Test that validation fails when project not found and create=False."""
    project_info = {
        "status": "NOT_FOUND",
        "projectId": None,
        "name": "test-project"
    }

    with pytest.raises(ValueError) as exc_info:
        validate_project_exists(project_info, "test-project", "test", allow_create=False)

    error_msg = str(exc_info.value)
    assert "Cannot connect to target 'test'" in error_msg
    assert "Project 'test-project' not found" in error_msg


def test_validate_project_not_found_with_create():
    """Test that validation passes when project not found but create=True."""
    project_info = {
        "status": "NOT_FOUND",
        "projectId": None,
        "name": "test-project"
    }

    # Should not raise error
    validate_project_exists(project_info, "test-project", "test", allow_create=True)


def test_validate_domain_not_found():
    """Test that validation fails when domain not found."""
    project_info = {
        "error": "Domain not found - check domain name/tags in manifest"
    }

    with pytest.raises(ValueError) as exc_info:
        validate_project_exists(project_info, "test-project", "test")

    error_msg = str(exc_info.value)
    assert "Cannot connect to target 'test'" in error_msg
    assert "Domain not found" in error_msg


def test_validate_project_exists():
    """Test that validation passes when project exists."""
    project_info = {
        "status": "ACTIVE",
        "projectId": "abc123",
        "project_id": "abc123",
        "name": "test-project",
        "connections": {}
    }

    # Should not raise error
    validate_project_exists(project_info, "test-project", "test")


def test_validate_other_error():
    """Test that validation fails with other errors."""
    project_info = {
        "error": "Some other error occurred"
    }

    with pytest.raises(ValueError) as exc_info:
        validate_project_exists(project_info, "test-project", "test")

    error_msg = str(exc_info.value)
    assert "Cannot connect to target 'test'" in error_msg
    assert "Some other error occurred" in error_msg
