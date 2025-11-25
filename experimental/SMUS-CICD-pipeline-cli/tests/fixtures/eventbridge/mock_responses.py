"""Mock EventBridge API responses for testing."""


def get_put_events_success():
    """Mock successful put_events response."""
    return {"FailedEntryCount": 0, "Entries": [{"EventId": "test-event-id"}]}


def get_put_events_failure():
    """Mock failed put_events response."""
    return {
        "FailedEntryCount": 1,
        "Entries": [
            {
                "ErrorCode": "InternalException",
                "ErrorMessage": "Failed to put event",
            }
        ],
    }
