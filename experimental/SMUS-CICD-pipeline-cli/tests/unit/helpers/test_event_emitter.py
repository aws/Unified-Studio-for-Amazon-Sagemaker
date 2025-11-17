"""Unit tests for EventEmitter."""

import json
from unittest.mock import MagicMock, patch

import pytest

from smus_cicd.helpers.event_emitter import EventEmitter


class TestEventEmitter:
    """Test EventEmitter class."""

    def test_init_enabled(self):
        """Test EventEmitter initialization when enabled."""
        emitter = EventEmitter(enabled=True, event_bus_name="test-bus", region="us-east-1")
        assert emitter.enabled is True
        assert emitter.event_bus_name == "test-bus"
        assert emitter.region == "us-east-1"

    def test_init_disabled(self):
        """Test EventEmitter initialization when disabled."""
        emitter = EventEmitter(enabled=False)
        assert emitter.enabled is False

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_lazy_client_loading(self, mock_boto_client):
        """Test that boto3 client is lazy-loaded."""
        emitter = EventEmitter(enabled=True, region="us-east-1")
        assert emitter._client is None
        
        # Access client property
        _ = emitter.client
        mock_boto_client.assert_called_once_with("events", region_name="us-east-1")

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_emit_success(self, mock_boto_client):
        """Test successful event emission."""
        mock_client = MagicMock()
        mock_client.put_events.return_value = {"FailedEntryCount": 0}
        mock_boto_client.return_value = mock_client

        emitter = EventEmitter(enabled=True, region="us-east-1")
        result = emitter.emit("TestEvent", {"key": "value"})

        assert result is True
        mock_client.put_events.assert_called_once()
        call_args = mock_client.put_events.call_args[1]
        assert call_args["Entries"][0]["Source"] == "com.amazon.smus.cicd"
        assert call_args["Entries"][0]["DetailType"] == "TestEvent"

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_emit_failure(self, mock_boto_client):
        """Test failed event emission."""
        mock_client = MagicMock()
        mock_client.put_events.return_value = {"FailedEntryCount": 1}
        mock_boto_client.return_value = mock_client

        emitter = EventEmitter(enabled=True, region="us-east-1")
        result = emitter.emit("TestEvent", {"key": "value"})

        assert result is False

    def test_emit_disabled(self):
        """Test that emit returns True when disabled."""
        emitter = EventEmitter(enabled=False)
        result = emitter.emit("TestEvent", {"key": "value"})
        assert result is True

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_deploy_started(self, mock_boto_client):
        """Test deploy started event."""
        mock_client = MagicMock()
        mock_client.put_events.return_value = {"FailedEntryCount": 0}
        mock_boto_client.return_value = mock_client

        emitter = EventEmitter(enabled=True, region="us-east-1")
        target = {"name": "test", "stage": "TEST"}
        bundle_info = {"path": "/tmp/bundle.zip"}
        
        result = emitter.deploy_started("TestPipeline", target, bundle_info)
        
        assert result is True
        call_args = mock_client.put_events.call_args[1]
        detail = json.loads(call_args["Entries"][0]["Detail"])
        assert detail["applicationName"] == "TestPipeline"
        assert detail["stage"] == "deploy"
        assert detail["status"] == "started"

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_deploy_failed(self, mock_boto_client):
        """Test deploy failed event."""
        mock_client = MagicMock()
        mock_client.put_events.return_value = {"FailedEntryCount": 0}
        mock_boto_client.return_value = mock_client

        emitter = EventEmitter(enabled=True, region="us-east-1")
        target = {"name": "test", "stage": "TEST"}
        error = {"code": "TEST_ERROR", "message": "Test error"}
        
        result = emitter.deploy_failed("TestPipeline", target, error)
        
        assert result is True
        call_args = mock_client.put_events.call_args[1]
        detail = json.loads(call_args["Entries"][0]["Detail"])
        assert detail["status"] == "failed"
        assert detail["error"]["code"] == "TEST_ERROR"

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_workflow_creation_completed(self, mock_boto_client):
        """Test workflow creation completed event."""
        mock_client = MagicMock()
        mock_client.put_events.return_value = {"FailedEntryCount": 0}
        mock_boto_client.return_value = mock_client

        emitter = EventEmitter(enabled=True, region="us-east-1")
        target = {"name": "test", "stage": "TEST"}
        workflows = [{"workflowName": "test_wf", "status": "created"}]
        
        result = emitter.workflow_creation_completed("TestPipeline", target, workflows)
        
        assert result is True
        call_args = mock_client.put_events.call_args[1]
        detail = json.loads(call_args["Entries"][0]["Detail"])
        assert detail["stage"] == "workflow-creation"
        assert detail["status"] == "completed"
        assert len(detail["workflows"]) == 1
