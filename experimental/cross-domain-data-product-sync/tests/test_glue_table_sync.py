"""Unit tests for glue_table_sync."""

from unittest import mock

import pytest

import glue_table_sync as gts


def test_load_config_requires_env(monkeypatch):
    for key in gts._REQUIRED_ENV_VARS:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(gts.ConfigurationError):
        gts._load_config()


def test_build_table_input_preserves_partition_keys():
    source_table = {
        "Name": "customers",
        "DatabaseName": "producer_db",       # read-only, must be dropped
        "CreateTime": "2024-01-01",           # read-only, must be dropped
        "CatalogId": "111111111111",          # read-only, must be dropped
        "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "bigint"}]},
        "PartitionKeys": [{"Name": "dt", "Type": "string"}],
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {"classification": "parquet"},
    }
    table_input = gts._build_table_input(source_table)

    assert table_input["Name"] == "customers"
    assert table_input["PartitionKeys"] == [{"Name": "dt", "Type": "string"}]
    assert table_input["StorageDescriptor"]["Columns"][0]["Name"] == "id"
    assert "DatabaseName" not in table_input
    assert "CreateTime" not in table_input
    assert "CatalogId" not in table_input


def test_build_table_input_defaults_table_type():
    table_input = gts._build_table_input({"Name": "t"})
    assert table_input["TableType"] == "EXTERNAL_TABLE"


def test_grant_project_role_access_idempotent(base_env):
    config = gts._load_config()
    lf = mock.Mock()
    lf.exceptions.AlreadyExistsException = type(
        "AlreadyExistsException", (Exception,), {}
    )
    lf.grant_permissions.side_effect = lf.exceptions.AlreadyExistsException()
    with mock.patch.object(gts, "_lakeformation_client", return_value=lf):
        # Should not raise on an already-existing grant.
        gts.grant_project_role_access(config, "customers")
    lf.grant_permissions.assert_called_once()


def test_grant_project_role_access_skips_without_role(base_env, monkeypatch):
    monkeypatch.delenv("PROJECT_ROLE_ARN", raising=False)
    config = gts._load_config()
    lf = mock.Mock()
    with mock.patch.object(gts, "_lakeformation_client", return_value=lf):
        gts.grant_project_role_access(config, "customers")
    lf.grant_permissions.assert_not_called()


def test_handler_ignores_non_matching_database(base_env):
    event = {
        "detail": {
            "eventName": "CreateTable",
            "requestParameters": {
                "databaseName": "some_other_db",
                "tableInput": {"name": "customers"},
            },
        }
    }
    with mock.patch.object(gts, "mirror_table") as mirror:
        result = gts.handler(event, None)
    mirror.assert_not_called()
    assert result["statusCode"] == 200
    assert result["body"] == "No action needed"


def test_handler_manual_invocation_calls_mirror(base_env):
    with mock.patch.object(gts, "mirror_table", return_value=("Created", {})) as mirror:
        result = gts.handler({"table_name": "customers"}, None)
    mirror.assert_called_once()
    assert result["statusCode"] == 200
    assert "Created table customers" in result["body"]
