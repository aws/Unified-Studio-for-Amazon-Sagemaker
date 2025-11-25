"""Tests for workflow bootstrap actions."""

import pytest
from unittest.mock import MagicMock, patch

from smus_cicd.bootstrap.handlers.workflow_handler import (
    handle_workflow_action,
    run_workflow,
    fetch_workflow_logs,
    monitor_workflow,
)
from smus_cicd.bootstrap.models import BootstrapAction


class TestWorkflowBootstrapActions:
    """Test workflow bootstrap action handlers."""

    def test_handle_workflow_action_run(self):
        """Test workflow.run action routing."""
        action = BootstrapAction(
            type="workflow.run",
            parameters={"workflowName": "test_dag"},
        )
        context = {
            "manifest": MagicMock(application_name="TestApp"),
            "target_config": MagicMock(
                project=MagicMock(name="test-project"),
                domain=MagicMock(region="us-east-2"),
            ),
        }

        with patch(
            "smus_cicd.bootstrap.handlers.workflow_handler.WorkflowOperations.trigger_workflow"
        ) as mock_trigger:
            mock_trigger.return_value = {
                "success": True,
                "run_id": "run123",
                "status": "STARTING",
                "workflow_arn": "arn:aws:airflow-serverless:us-east-2:123:workflow/test",
                "workflow_name": "TestApp_test_project_test_dag",
            }

            result = handle_workflow_action(action, context)

            assert result["action"] == "workflow.run"
            assert result["run_id"] == "run123"
            assert result["status"] == "STARTING"
            mock_trigger.assert_called_once()

    def test_handle_workflow_action_logs(self):
        """Test workflow.logs action routing."""
        action = BootstrapAction(
            type="workflow.logs",
            parameters={"workflowName": "test_dag", "lines": 50},
        )
        context = {
            "manifest": MagicMock(application_name="TestApp"),
            "target_config": MagicMock(
                project=MagicMock(name="test-project"),
                domain=MagicMock(region="us-east-2"),
            ),
        }

        with patch(
            "smus_cicd.bootstrap.handlers.workflow_handler.WorkflowOperations.get_workflow_status"
        ) as mock_status, patch(
            "smus_cicd.bootstrap.handlers.workflow_handler.WorkflowOperations.fetch_logs"
        ) as mock_logs:
            mock_status.return_value = {
                "success": True,
                "workflow_arn": "arn:aws:airflow-serverless:us-east-2:123:workflow/test",
            }
            mock_logs.return_value = {
                "success": True,
                "run_id": "run123",
                "status": "SUCCESS",
                "logs": ["log line 1", "log line 2"],
            }

            result = handle_workflow_action(action, context)

            assert result["action"] == "workflow.logs"
            assert result["run_id"] == "run123"
            assert result["log_lines"] == 2

    def test_run_workflow_missing_workflow_name(self):
        """Test run_workflow raises error when workflowName missing."""
        action = BootstrapAction(type="workflow.run", parameters={})
        context = {}

        with pytest.raises(ValueError, match="workflowName is required"):
            run_workflow(action, context)

    def test_fetch_workflow_logs_missing_workflow_name(self):
        """Test fetch_workflow_logs raises error when workflowName missing."""
        action = BootstrapAction(type="workflow.logs", parameters={})
        context = {}

        with pytest.raises(ValueError, match="workflowName is required"):
            fetch_workflow_logs(action, context)

    def test_handle_workflow_action_unknown_api(self):
        """Test unknown workflow action raises error."""
        action = BootstrapAction(
            type="workflow.unknown",
            parameters={},
        )
        context = {}

        with pytest.raises(ValueError, match="Unknown workflow action"):
            handle_workflow_action(action, context)

    def test_handle_workflow_action_monitor(self):
        """Test workflow.monitor action routing."""
        action = BootstrapAction(
            type="workflow.monitor",
            parameters={"workflowName": "test_dag"},
        )
        context = {
            "manifest": MagicMock(application_name="TestApp"),
            "target_config": MagicMock(
                project=MagicMock(name="test-project"),
                domain=MagicMock(region="us-east-2"),
            ),
        }

        with patch(
            "smus_cicd.bootstrap.handlers.workflow_handler.WorkflowOperations.get_workflow_status"
        ) as mock_status:
            mock_status.return_value = {
                "success": True,
                "workflow_arn": "arn:aws:airflow-serverless:us-east-2:123:workflow/test",
                "workflow_name": "TestApp_test_project_test_dag",
                "runs": [
                    {"run_id": "run1", "status": "SUCCESS"},
                    {"run_id": "run2", "status": "FAILED"},
                ],
            }

            result = handle_workflow_action(action, context)

            assert result["action"] == "workflow.monitor"
            assert result["workflow_name"] == "TestApp_test_project_test_dag"
            assert len(result["recent_runs"]) == 2
            mock_status.assert_called_once()

    def test_monitor_workflow_missing_workflow_name(self):
        """Test monitor_workflow raises error when workflowName missing."""
        action = BootstrapAction(type="workflow.monitor", parameters={})
        context = {}

        with pytest.raises(ValueError, match="workflowName is required"):
            monitor_workflow(action, context)
