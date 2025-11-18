"""Unit tests for EventBridgeEmitter base class."""

import json
import unittest
from unittest.mock import MagicMock, patch

from smus_cicd.helpers.eventbridge_client import EventBridgeEmitter


class TestEventBridgeEmitter(unittest.TestCase):
    """Test EventBridgeEmitter base class."""

    def setUp(self):
        """Set up test fixtures."""
        self.emitter = EventBridgeEmitter(
            enabled=True, event_bus_name="test-bus", region="us-east-1"
        )

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_client_lazy_load(self, mock_boto_client):
        """Test EventBridge client is lazy-loaded."""
        emitter = EventBridgeEmitter(enabled=True)
        self.assertIsNone(emitter._client)
        _ = emitter.client
        mock_boto_client.assert_called_once_with("events", region_name=None)

    def test_client_not_created_when_disabled(self):
        """Test client is not created when disabled."""
        emitter = EventBridgeEmitter(enabled=False)
        self.assertIsNone(emitter.client)

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_emit_event_success(self, mock_boto_client):
        """Test successful event emission."""
        mock_events = MagicMock()
        mock_events.put_events.return_value = {"FailedEntryCount": 0}
        mock_boto_client.return_value = mock_events

        result = self.emitter.emit_event(
            source="test.source",
            detail_type="TestEvent",
            detail={"key": "value"},
        )

        self.assertTrue(result)
        mock_events.put_events.assert_called_once()
        call_args = mock_events.put_events.call_args[1]
        entry = call_args["Entries"][0]
        self.assertEqual(entry["Source"], "test.source")
        self.assertEqual(entry["DetailType"], "TestEvent")
        self.assertEqual(json.loads(entry["Detail"]), {"key": "value"})
        self.assertEqual(entry["EventBusName"], "test-bus")

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_emit_event_with_resources(self, mock_boto_client):
        """Test event emission with resources."""
        mock_events = MagicMock()
        mock_events.put_events.return_value = {"FailedEntryCount": 0}
        mock_boto_client.return_value = mock_events

        resources = ["arn:aws:s3:::bucket"]
        result = self.emitter.emit_event(
            source="test.source",
            detail_type="TestEvent",
            detail={"key": "value"},
            resources=resources,
        )

        self.assertTrue(result)
        call_args = mock_events.put_events.call_args[1]
        entry = call_args["Entries"][0]
        self.assertEqual(entry["Resources"], resources)

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_emit_event_failure(self, mock_boto_client):
        """Test event emission failure."""
        mock_events = MagicMock()
        mock_events.put_events.return_value = {"FailedEntryCount": 1}
        mock_boto_client.return_value = mock_events

        result = self.emitter.emit_event(
            source="test.source",
            detail_type="TestEvent",
            detail={"key": "value"},
        )

        self.assertFalse(result)

    @patch("smus_cicd.helpers.eventbridge_client.boto3.client")
    def test_emit_event_exception(self, mock_boto_client):
        """Test event emission with exception."""
        mock_events = MagicMock()
        mock_events.put_events.side_effect = Exception("API error")
        mock_boto_client.return_value = mock_events

        result = self.emitter.emit_event(
            source="test.source",
            detail_type="TestEvent",
            detail={"key": "value"},
        )

        self.assertFalse(result)

    def test_emit_event_when_disabled(self):
        """Test event emission when disabled."""
        emitter = EventBridgeEmitter(enabled=False)
        result = emitter.emit_event(
            source="test.source",
            detail_type="TestEvent",
            detail={"key": "value"},
        )
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
