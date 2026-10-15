"""Unit tests for the scheduled, scoped, relinking lineage sync Lambda."""

import io
import json
from unittest.mock import MagicMock, patch

import lineage_sync


def _dataset(uuid, producer_db, table, producer_account="111111111111"):
    """A Glue/Spark-style OpenLineage dataset: S3 name + Glue symlink (producer)."""
    return {
        "namespace": "s3://producer-bucket",
        "name": f"dzd-source/proj/dev/sys/athena/tables/{uuid}",
        "facets": {
            "symlinks": {
                "identifiers": [
                    {
                        "namespace": f"arn:aws:glue:us-east-1:{producer_account}",
                        "name": f"table/{producer_db}/{table}",
                        "type": "TABLE",
                    }
                ]
            }
        },
    }


def _ol_event(run_id, inputs, outputs):
    return {
        "eventType": "COMPLETE",
        "run": {"runId": run_id},
        "job": {"namespace": "default", "name": "lineage"},
        "inputs": inputs,
        "outputs": outputs,
    }


def _get_event_resp(ol_event):
    return {"event": io.BytesIO(json.dumps(ol_event).encode("utf-8"))}


def _patch_clients(mirrored_tables, lineage_items, event_bodies):
    glue = MagicMock()
    glue.get_tables.return_value = {"TableList": [{"Name": n} for n in mirrored_tables]}
    source_dz = MagicMock()
    source_dz.list_lineage_events.return_value = {"items": lineage_items}
    source_dz.get_lineage_event.side_effect = lambda **kw: event_bodies[kw["identifier"]]
    local_dz = MagicMock()
    return glue, source_dz, local_dz


def test_relink_rewrites_symlink_to_marketplace_arn(base_env):
    """A mirrored-table dataset is relinked to this account's Glue table ARN."""
    config = lineage_sync._load_config()  # ACCOUNT_ID=222..., TARGET_DATABASE=marketplace_db
    ds = _dataset("uuid-1", "producer_db", "customer_accounts")
    table = lineage_sync._matched_mirrored_table(ds, {"customer_accounts"})
    assert table == "customer_accounts"

    lineage_sync._relink_dataset_to_marketplace(ds, table, config)
    ident = ds["facets"]["symlinks"]["identifiers"][0]
    assert ident["namespace"] == "arn:aws:glue:us-east-1:222222222222"
    assert ident["name"] == "table/marketplace_db/customer_accounts"
    assert ident["type"] == "TABLE"


def test_unmirrored_dataset_not_matched(base_env):
    ds = _dataset("uuid-9", "producer_db", "secret_table")
    assert lineage_sync._matched_mirrored_table(ds, {"customer_accounts"}) is None


def test_only_forwards_and_relinks_mirrored_events(base_env):
    config = lineage_sync._load_config()
    # e1 references a mirrored table (relinked, forwarded); e2 does not (skipped)
    e1 = _ol_event("run-1",
                   inputs=[_dataset("u1", "producer_db", "product_catalog")],
                   outputs=[_dataset("u2", "producer_db", "customer_accounts")])
    e2 = _ol_event("run-2",
                   inputs=[_dataset("u3", "producer_db", "secret_table")],
                   outputs=[_dataset("u4", "producer_db", "other_private")])
    items = [{"id": "e1", "processingStatus": "SUCCESS"},
             {"id": "e2", "processingStatus": "SUCCESS"}]
    bodies = {"e1": _get_event_resp(e1), "e2": _get_event_resp(e2)}
    glue, source_dz, local_dz = _patch_clients(
        {"product_catalog", "customer_accounts"}, items, bodies)

    with patch.object(lineage_sync, "_local_glue_client", return_value=glue), \
         patch.object(lineage_sync, "get_source_dz_client", return_value=source_dz), \
         patch.object(lineage_sync, "_local_datazone_client", return_value=local_dz):
        synced = lineage_sync.sync_recent_lineage(config)

    assert synced == 1  # only e1 forwarded
    assert local_dz.post_lineage_event.call_count == 1
    _, kwargs = local_dz.post_lineage_event.call_args
    posted = json.loads(kwargs["event"].decode("utf-8"))
    # both datasets in e1 relinked to marketplace account/db
    arns = []
    for sec in ("inputs", "outputs"):
        for d in posted[sec]:
            arns.append(d["facets"]["symlinks"]["identifiers"][0]["namespace"])
            arns.append(d["facets"]["symlinks"]["identifiers"][0]["name"])
    assert "arn:aws:glue:us-east-1:222222222222" in arns
    assert "table/marketplace_db/product_catalog" in arns
    assert "table/marketplace_db/customer_accounts" in arns


def test_client_token_is_deterministic_for_same_run():
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
