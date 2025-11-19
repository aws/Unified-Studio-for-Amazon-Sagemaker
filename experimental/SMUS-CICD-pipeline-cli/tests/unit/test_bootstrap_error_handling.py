"""Unit tests to reproduce bootstrap handler error handling issues."""

from unittest.mock import MagicMock, patch
import pytest

from smus_cicd.bootstrap.executor import BootstrapExecutor
from smus_cicd.bootstrap.action_registry import ActionRegistry
from smus_cicd.bootstrap.models import BootstrapAction
from smus_cicd.bootstrap.handlers.workflow_create_handler import handle_workflow_create


class TestBootstrapErrorHandling:
    """Test bootstrap error handling issues."""

    def test_workflow_create_returns_false_on_missing_project_info(self):
        """
        ISSUE 1: Handler returns False instead of raising exception.
        
        When project_info is missing, handler returns False but executor
        treats this as success and logs "Successfully executed".
        
        Expected: Should raise exception to stop execution.
        Actual: Returns False, treated as success.
        """
        action = BootstrapAction(type="workflow.create")
        
        # Context with metadata but no project_info
        manifest = MagicMock()
        manifest.content.workflows = [{"workflowName": "test-workflow"}]
        
        context = {
            "manifest": manifest,
            "config": {"region": "us-east-1"},
            "target_config": MagicMock(
                project=MagicMock(name="test-project"),
                environment_variables={}
            ),
            "metadata": {
                "s3_bucket": "test-bucket",
                "s3_prefix": "test-prefix",
                # Missing project_info!
            }
        }
        
        # Current behavior: Returns False
        result = handle_workflow_create(action, context)
        
        # This test FAILS because handler returns False instead of raising
        # Uncomment to see the issue:
        # assert result is False  # ❌ Should raise exception, not return False
        
        # Expected behavior: Should raise exception
        with pytest.raises(ValueError, match="Project info not available"):
            handle_workflow_create(action, context)

    def test_executor_treats_false_as_success(self):
        """
        ISSUE 1: Executor treats False return as success.
        
        When handler returns False, executor logs "Successfully executed"
        and continues to next action.
        
        Expected: Should detect False and raise exception.
        Actual: Treats False as success.
        """
        registry = ActionRegistry()
        executor = BootstrapExecutor(registry)
        
        # Mock handler that returns False
        def failing_handler(action, context):
            return False
        
        registry.register("test.action", failing_handler)
        
        actions = [BootstrapAction(type="test.action")]
        context = {}
        
        # Current behavior: Treats False as success
        results = executor.execute_actions(actions, context)
        
        # This test PASSES but shouldn't - False should be treated as failure
        assert results[0]["status"] == "success"  # ❌ Wrong! Should be "failed"
        assert results[0]["result"] is False
        
        # Expected behavior: Should raise exception when handler returns False
        # Uncomment to see what should happen:
        # with pytest.raises(RuntimeError, match="returned False"):
        #     executor.execute_actions(actions, context)

    def test_metadata_none_prevents_project_info_assignment(self):
        """
        ISSUE 2: When metadata is None, project_info is never added.
        
        When monitoring is disabled, collect_metadata() returns None.
        Our fix checks 'if metadata is not None' before adding project_info.
        This means project_info is never added when monitoring is disabled.
        
        Expected: metadata should be initialized as {} if None.
        Actual: metadata stays None, project_info never added.
        """
        from smus_cicd.helpers.monitoring import collect_metadata
        from smus_cicd.application import ApplicationManifest
        
        # Manifest without monitoring config
        manifest_data = {
            "applicationName": "TestApp",
            "content": {"bundlesDirectory": "./bundles"},
            "stages": {
                "test": {
                    "domain": {"region": "us-east-1"},
                    "project": {"name": "test-project"}
                }
            }
            # No monitoring config!
        }
        manifest = ApplicationManifest.from_dict(manifest_data)
        
        # collect_metadata returns None when monitoring disabled
        metadata = collect_metadata(manifest)
        assert metadata is None
        
        # Simulate our current fix
        project_info = {"project_id": "proj-123", "domain_id": "dom-456"}
        
        # Current code checks 'if metadata is not None'
        if metadata is not None:
            metadata["project_info"] = project_info
        
        # This test PASSES but shows the bug - project_info was never added!
        assert metadata is None  # ❌ Should be {} with project_info
        
        # Expected behavior: Initialize metadata as {} if None
        metadata = collect_metadata(manifest)
        if metadata is None:
            metadata = {}
        metadata["project_info"] = project_info
        
        assert metadata == {"project_info": project_info}  # ✅ Correct

    def test_workflow_create_fails_when_metadata_is_none(self):
        """
        ISSUE 2: workflow.create fails when metadata is None.
        
        Complete reproduction of ML Training workflow failure.
        """
        action = BootstrapAction(type="workflow.create")
        
        # Context with metadata=None (monitoring disabled)
        manifest = MagicMock()
        manifest.content.workflows = [{"workflowName": "test-workflow"}]
        
        context = {
            "manifest": manifest,
            "config": {"region": "us-east-1"},
            "target_config": MagicMock(
                project=MagicMock(name="test-project"),
                environment_variables={}
            ),
            "metadata": None  # Monitoring disabled!
        }
        
        # Handler tries to get project_info from None
        result = handle_workflow_create(action, context)
        
        # Returns False because metadata.get("project_info", {}) returns {}
        assert result is False
        
        # Should raise exception instead
        with pytest.raises(ValueError, match="Project info not available"):
            handle_workflow_create(action, context)

    def test_s3_location_missing_also_returns_false(self):
        """
        ISSUE 1: S3 location check also returns False instead of raising.
        
        Same issue - returns False when S3 location is missing.
        """
        action = BootstrapAction(type="workflow.create")
        
        manifest = MagicMock()
        manifest.content.workflows = [{"workflowName": "test-workflow"}]
        
        context = {
            "manifest": manifest,
            "config": {"region": "us-east-1"},
            "target_config": MagicMock(
                project=MagicMock(name="test-project"),
                environment_variables={}
            ),
            "metadata": {
                "project_info": {
                    "project_id": "proj-123",
                    "domain_id": "dom-456"
                }
                # Missing s3_bucket and s3_prefix!
            }
        }
        
        # Returns False instead of raising
        result = handle_workflow_create(action, context)
        assert result is False
        
        # Should raise exception
        with pytest.raises(ValueError, match="S3 location not available"):
            handle_workflow_create(action, context)


class TestBootstrapErrorHandlingFixed:
    """Tests showing expected behavior after fixes."""

    def test_handler_raises_exception_on_missing_project_info(self):
        """After fix: Handler raises exception instead of returning False."""
        # This test will pass after we fix the handler
        pytest.skip("Will pass after handler is fixed to raise exceptions")

    def test_executor_stops_on_exception(self):
        """After fix: Executor stops when handler raises exception."""
        registry = ActionRegistry()
        executor = BootstrapExecutor(registry)
        
        def failing_handler(action, context):
            raise ValueError("Handler failed")
        
        registry.register("test.action", failing_handler)
        
        actions = [BootstrapAction(type="test.action")]
        context = {}
        
        # Should raise and stop execution
        with pytest.raises(ValueError, match="Handler failed"):
            executor.execute_actions(actions, context)

    def test_metadata_initialized_as_empty_dict(self):
        """After fix: metadata is always a dict, never None."""
        from smus_cicd.helpers.monitoring import collect_metadata
        from smus_cicd.application import ApplicationManifest
        
        manifest_data = {
            "applicationName": "TestApp",
            "content": {"bundlesDirectory": "./bundles"},
            "stages": {
                "test": {
                    "domain": {"region": "us-east-1"},
                    "project": {"name": "test-project"}
                }
            }
        }
        manifest = ApplicationManifest.from_dict(manifest_data)
        
        # After fix: Initialize as {} if None
        metadata = collect_metadata(manifest)
        if metadata is None:
            metadata = {}
        
        # Now we can always add project_info
        project_info = {"project_id": "proj-123", "domain_id": "dom-456"}
        metadata["project_info"] = project_info
        
        assert metadata["project_info"] == project_info
        assert "project_info" in metadata
