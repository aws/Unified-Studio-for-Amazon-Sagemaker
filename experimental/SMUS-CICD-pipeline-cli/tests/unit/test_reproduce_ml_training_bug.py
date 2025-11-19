"""
Minimal reproduction of ML Training workflow bug from GitHub Actions run 19518064784.

This test reproduces the exact failure seen in:
https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/19518064784/job/55876433542

The bug chain:
1. collect_metadata() returns None (monitoring disabled)
2. deploy.py doesn't initialize metadata to {} (missing in remote branch)
3. Handler crashes with AttributeError when calling metadata.get()
4. OR if metadata is {}, handler raises ValueError (current local code)
5. Remote branch had: handler returns False instead of raising (old code)
6. Executor treats False as success and logs "Successfully executed"

This test documents what SHOULD happen vs what WAS happening in remote.
"""

import pytest
from unittest.mock import MagicMock
from smus_cicd.bootstrap.handlers.workflow_create_handler import handle_workflow_create
from smus_cicd.bootstrap.models import BootstrapAction


def test_ml_training_bug_metadata_none_causes_crash():
    """
    BUG: When metadata=None, handler crashes with AttributeError.
    
    This happens when:
    - collect_metadata() returns None
    - deploy.py doesn't initialize metadata = {}
    - Handler tries metadata.get("project_info")
    
    Current local code: This crashes with AttributeError
    """
    action = BootstrapAction(type="workflow.create")
    
    manifest = MagicMock()
    manifest.content.workflows = [{"workflowName": "ml_training_workflow"}]
    
    context = {
        "manifest": manifest,
        "config": {"region": "us-east-1"},
        "target_config": MagicMock(
            project=MagicMock(name="test-project"),
            environment_variables={}
        ),
        "metadata": None  # Bug: not initialized to {}
    }
    
    # Current behavior: crashes with AttributeError
    with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'get'"):
        handle_workflow_create(action, context)


def test_ml_training_bug_missing_project_info_raises():
    """
    FIXED: When metadata={} but project_info missing, handler raises ValueError.
    
    This is the CORRECT behavior after the fix.
    Current local code: Raises ValueError (good!)
    Remote branch old code: Returned False (bad!)
    """
    action = BootstrapAction(type="workflow.create")
    
    manifest = MagicMock()
    manifest.content.workflows = [{"workflowName": "ml_training_workflow"}]
    
    context = {
        "manifest": manifest,
        "config": {"region": "us-east-1"},
        "target_config": MagicMock(
            project=MagicMock(name="test-project"),
            environment_variables={}
        ),
        "metadata": {}  # Initialized but empty
    }
    
    # Current local code: Raises ValueError (correct!)
    with pytest.raises(ValueError, match="Project info not available"):
        handle_workflow_create(action, context)

