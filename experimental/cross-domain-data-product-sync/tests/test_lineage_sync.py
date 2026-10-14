"""Unit tests for the scheduled, scoped, idempotent lineage sync Lambda."""

import io
import json
from unittest.mock import MagicMock, patch

import lineage_sync


def _ol_complete_event(run_id, body_text):
    """Build a get_lineage_event response whose body is a COMPLETE OL event."""
    payload = {"eventType": "COMPLETE", "run": {"runId": run_id}, "_raw": body_text}
    return {"event": io.BytesIO(json.dumps(payload).encode("utf-8"))}


def _patch_clients(mirrored_tables, lineage_items, event_bodies):
    """Patch the Glue table listing and the source/local DataZone clients."""
    glue = MagicMock()
    glue.get_tables.return_value = {
        "TableList": [{"Name": n} for n in mirrored_tables]
    }

    source_dz = MagicMock()
    source_dz.list_lineage_events.return_value = {"items": lineage_items}
    source_dz.get_lineage_event.side_effect = lambda **kw: event_bodies[kw["identifier"]]

    local_dz = MagicMock()
    return glue, source_dz, local_dz


def test_only_forwards_lineage_referencing_mirrored_tables(base_env):
    config = lineage_sync._load_config()
    items = [
        {"id": "e1", "processingStatus": "SUCCESS"},
        {"id": "e2", "processingStatus": "SUCCESS"},
    ]
    bodies = {
        "e1": _ol_complete_event("run-1", "reads from customer_accounts"),  # mirrored
        "e2": _ol_complete_event("run-2", "reads from secret_private_table"),  # not
    }
    glue, source_dz, local_dz = _patch_clients(
        {"customer_accounts"}, items, bodies
    )

    with patch.object(lineage_sync, "_local_glue_client", return_value=glue), \
         patch.object(lineage_sync, "get_source_dz_client", return_value=source_dz), \
         patch.object(lineage_sync, "_local_datazone_client", return_value=local_dz):
        synced = lineage_sync.sync_recent_lineage(config)

    assert synced == 1
    assert local_dz.post_lineage_event.call_count == 1
    # The one posted must be the mirrored-table event, with a client token.
    _, kwargs = local_dz.post_lineage_event.call_args
    assert kwargs["domainIdentifier"] == config["domain_id"]
    assert kwargs.get("clientToken")


def test_no_mirrored_tables_posts_nothing(base_env):
    config = lineage_sync._load_config()
    glue, source_dz, local_dz = _patch_clients(set(), [], {})
    with patch.object(lineage_sync, "_local_glue_client", return_value=glue), \
         patch.object(lineage_sync, "get_source_dz_client", return_value=source_dz), \
         patch.object(lineage_sync, "_local_datazone_client", return_value=local_dz):
        synced = lineage_sync.sync_recent_lineage(config)
    assert synced == 0
    local_dz.post_lineage_event.assert_not_called()


def test_client_token_is_deterministic_for_same_run():
    """Same run id + event type must yield the same token (idempotent re-post)."""
    ev = {"eventType": "COMPLETE", "run": {"runId": "run-xyz"}}
    assert lineage_sync._client_token_for(ev, "fallback") == \
        lineage_sync._client_token_for(ev, "other-fallback")


def test_scheduled_event_triggers_sync(base_env):
    with patch.object(lineage_sync, "sync_recent_lineage", return_value=3) as m:
        resp = lineage_sync.handler({"detail-type": "Scheduled Event"}, None)
    assert resp["statusCode"] == 200
    m.assert_called_once()


def test_unrelated_event_is_noop(base_env):
    with patch.object(lineage_sync, "sync_recent_lineage") as m:
        resp = lineage_sync.handler({"detail-type": "Something Else"}, None)
    assert resp["statusCode"] == 200
    assert "No action" in resp["body"]
    m.assert_not_called()
