"""Unit tests for catalog_sync_mirror."""

import io
import json
from unittest import mock

import pytest

import catalog_sync_mirror as csm


def test_load_config_requires_env(monkeypatch):
    for key in csm._REQUIRED_ENV_VARS:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(csm.ConfigurationError):
        csm._load_config()


def test_load_form_parses_named_form():
    forms = [{"formName": "GlueTableForm", "content": json.dumps({"tableName": "t"})}]
    assert csm._load_form(forms, "GlueTableForm") == {"tableName": "t"}
    assert csm._load_form(forms, "MissingForm") is None


def test_find_managed_asset_matches_deterministically(base_env):
    config = csm._load_config()
    dz = mock.Mock()
    dz.search.return_value = {
        "items": [
            {"assetItem": {"identifier": "wrong"}},
            {"assetItem": {"identifier": "right"}},
        ],
        "nextToken": None,
    }

    def _get_asset(domainIdentifier, identifier):
        if identifier == "right":
            glue = {"catalogId": "222222222222",
                    "databaseName": "marketplace_db",
                    "tableName": "customers"}
        else:
            glue = {"catalogId": "999999999999",
                    "databaseName": "other",
                    "tableName": "customers"}
        return {"formsOutput": [{"formName": "GlueTableForm", "content": json.dumps(glue)}]}

    dz.get_asset.side_effect = _get_asset
    with mock.patch.object(csm, "_local_datazone_client", return_value=dz):
        asset_id = csm.find_managed_asset(config, "customers")
    assert asset_id == "right"


def test_find_managed_asset_returns_none_when_no_match(base_env):
    config = csm._load_config()
    dz = mock.Mock()
    dz.search.return_value = {"items": [], "nextToken": None}
    with mock.patch.object(csm, "_local_datazone_client", return_value=dz):
        assert csm.find_managed_asset(config, "customers") is None


def test_extract_business_metadata():
    source_asset = {
        "name": "Customers",
        "description": "d" * 5000,
        "formsOutput": [
            {"formName": "AssetCommonDetailsForm",
             "content": json.dumps({"summary": "s", "readMe": "r"})},
            {"formName": "ColumnBusinessMetadataForm",
             "content": json.dumps({"columns": []})},
        ],
    }
    meta = csm._extract_business_metadata(source_asset)
    assert meta["asset_name"] == "Customers"
    assert len(meta["description"]) == csm._DESCRIPTION_MAX_LEN
    assert meta["summary"] == "s"
    assert meta["readme"] == "r"
    assert meta["column_metadata"] == {"columns": []}


def test_asset_event_awaits_data_source_when_no_managed_asset(base_env):
    event = {
        "detail-type": "Asset Added To Catalog",
        "detail": {"data": {"assetId": "src-asset"}},
    }
    source_dz = mock.Mock()
    source_dz.get_asset.return_value = {
        "name": "customers",
        "description": "",
        "formsOutput": [
            {"formName": "GlueTableForm", "content": json.dumps({"tableName": "customers"})}
        ],
    }
    with mock.patch.object(csm, "get_source_dz_client", return_value=source_dz), \
         mock.patch.object(csm, "find_managed_asset", return_value=None), \
         mock.patch("glue_table_sync.mirror_table", return_value=("Created", {})):
        result = csm.handler(event, None)
    assert result["statusCode"] == 202
    assert "awaiting data source run" in result["body"]


def test_lineage_only_forwards_events_referencing_asset(base_env):
    config = csm._load_config()
    source_dz = mock.Mock()
    local_dz = mock.Mock()
    source_dz.list_lineage_events.return_value = {
        "items": [
            {"id": "e1", "processingStatus": "SUCCESS"},
            {"id": "e2", "processingStatus": "SUCCESS"},
        ],
        "nextToken": None,
    }

    def _get_event(domainIdentifier, identifier):
        if identifier == "e1":
            payload = {"eventType": "COMPLETE", "asset": "target-asset"}
        else:
            payload = {"eventType": "COMPLETE", "asset": "unrelated"}
        return {"event": io.BytesIO(json.dumps(payload).encode("utf-8"))}

    source_dz.get_lineage_event.side_effect = _get_event
    with mock.patch.object(csm, "get_source_dz_client", return_value=source_dz), \
         mock.patch.object(csm, "_local_datazone_client", return_value=local_dz):
        synced = csm.sync_lineage_for_asset(config, "target-asset")
    assert synced == 1
    local_dz.post_lineage_event.assert_called_once()


def test_unhandled_event_is_noop(base_env):
    result = csm.handler({"detail-type": "Some Other Event"}, None)
    assert result["statusCode"] == 200
    assert result["body"] == "No action needed"
