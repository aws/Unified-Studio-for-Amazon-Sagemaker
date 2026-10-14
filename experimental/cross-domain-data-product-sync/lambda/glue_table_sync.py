"""Glue Table Sync Lambda.

Trigger: Glue CreateTable / UpdateTable event (via CloudTrail) forwarded from the
Producer account, or a manual ``{"table_name": "..."}`` invocation.

Action: mirrors a Glue table definition from the Producer account into this
account's target database (metadata only; storage still points at the Producer's
S3 location) and grants Lake Formation SELECT/DESCRIBE (grantable) to the project
environment role.

The mirrored table intentionally preserves the full source schema, including
``PartitionKeys``, so partitioned tables are represented correctly.
"""

import json
import logging
import os

import boto3
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Fields copied verbatim from the source Glue table definition. Root-level fields
# such as PartitionKeys must be included or partitioned tables lose their layout.
_COPIED_TABLE_FIELDS = (
    "Description",
    "Owner",
    "Retention",
    "StorageDescriptor",
    "PartitionKeys",
    "TableType",
    "Parameters",
    "TargetTable",
)

_REQUIRED_ENV_VARS = (
    "SOURCE_ACCOUNT_ID",
    "SOURCE_DATABASE",
    "TARGET_DATABASE",
    "SOURCE_ROLE_ARN",
)

_BOTO_CONFIG = Config(retries={"max_attempts": 5, "mode": "standard"})


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _load_config():
    """Read and validate configuration from the environment.

    Raising here (rather than at import time) keeps the module importable for
    unit tests that patch the environment per test.
    """
    missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(sorted(missing))}"
        )
    return {
        "source_account": os.environ["SOURCE_ACCOUNT_ID"],
        "source_database": os.environ["SOURCE_DATABASE"],
        "target_database": os.environ["TARGET_DATABASE"],
        "source_role_arn": os.environ["SOURCE_ROLE_ARN"],
        "project_role_arn": os.environ.get("PROJECT_ROLE_ARN", ""),
    }


def _sts_client():
    return boto3.client("sts", config=_BOTO_CONFIG)


def _local_glue_client():
    return boto3.client("glue", config=_BOTO_CONFIG)


def _lakeformation_client():
    return boto3.client("lakeformation", config=_BOTO_CONFIG)


def get_source_glue_client(source_role_arn):
    """Assume the Producer Glue read role and return a scoped Glue client."""
    creds = _sts_client().assume_role(
        RoleArn=source_role_arn, RoleSessionName="glue-table-sync"
    )["Credentials"]
    return boto3.client(
        "glue",
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        config=_BOTO_CONFIG,
    )


def _build_table_input(source_table):
    """Project a source Glue table definition into a CreateTable/UpdateTable input.

    Only known, copyable fields are included. Read-only fields returned by
    GetTable (``DatabaseName``, ``CreateTime``, ``CreatedBy``, ``CatalogId``,
    ``VersionId``, ``IsRegisteredWithLakeFormation`` and similar) are excluded
    because they are rejected by the write APIs.
    """
    table_input = {"Name": source_table["Name"]}
    for field in _COPIED_TABLE_FIELDS:
        if field in source_table and source_table[field] is not None:
            table_input[field] = source_table[field]
    table_input.setdefault("TableType", "EXTERNAL_TABLE")
    return table_input


def mirror_table(config, table_name):
    """Create or update the mirrored table in the target database.

    Returns the action taken ("Created" or "Updated") and the source table
    definition so callers can reuse it without a second GetTable call.
    """
    source_glue = get_source_glue_client(config["source_role_arn"])
    source_table = source_glue.get_table(
        CatalogId=config["source_account"],
        DatabaseName=config["source_database"],
        Name=table_name,
    )["Table"]

    table_input = _build_table_input(source_table)
    local_glue = _local_glue_client()
    try:
        local_glue.create_table(
            DatabaseName=config["target_database"], TableInput=table_input
        )
        action = "Created"
    except local_glue.exceptions.AlreadyExistsException:
        local_glue.update_table(
            DatabaseName=config["target_database"], TableInput=table_input
        )
        action = "Updated"

    grant_project_role_access(config, table_name)
    logger.info(
        "Mirrored table",
        extra={"table": table_name, "action": action,
               "target_database": config["target_database"]},
    )
    return action, source_table


def grant_project_role_access(config, table_name):
    """Grant SELECT + DESCRIBE (grantable) to the project environment role.

    Idempotent: an already-granted permission is treated as success. Any other
    failure is raised so the caller can surface it rather than silently continue.
    """
    project_role_arn = config.get("project_role_arn", "")
    if not project_role_arn:
        logger.warning("PROJECT_ROLE_ARN not set; skipping Lake Formation grant")
        return

    lf = _lakeformation_client()
    try:
        lf.grant_permissions(
            Principal={"DataLakePrincipalIdentifier": project_role_arn},
            Resource={
                "Table": {
                    "DatabaseName": config["target_database"],
                    "Name": table_name,
                }
            },
            Permissions=["SELECT", "DESCRIBE"],
            PermissionsWithGrantOption=["SELECT", "DESCRIBE"],
        )
        logger.info(
            "Granted Lake Formation SELECT/DESCRIBE (grantable)",
            extra={"principal": project_role_arn, "table": table_name},
        )
    except lf.exceptions.AlreadyExistsException:
        logger.info(
            "Lake Formation permission already present; nothing to do",
            extra={"principal": project_role_arn, "table": table_name},
        )


def _extract_glue_event_table(detail):
    """Return (event_name, database_name, table_name) from a Glue CloudTrail event."""
    event_name = detail.get("eventName", "")
    request_params = detail.get("requestParameters", {}) or {}
    table_name = (request_params.get("tableInput", {}) or {}).get("name", "")
    database_name = request_params.get("databaseName", "")
    return event_name, database_name, table_name


def handler(event, context):
    """Lambda entry point for manual and EventBridge (Glue via CloudTrail) invocations."""
    logger.info("Received event", extra={"event": event})
    config = _load_config()

    # Manual invocation: {"table_name": "..."}
    if isinstance(event, dict) and "table_name" in event:
        table_name = event["table_name"]
        action, _ = mirror_table(config, table_name)
        return {
            "statusCode": 200,
            "body": f"{action} table {table_name} in {config['target_database']}",
        }

    detail = event.get("detail", {}) if isinstance(event, dict) else {}
    event_name, database_name, table_name = _extract_glue_event_table(detail)

    if event_name not in ("CreateTable", "UpdateTable"):
        return {"statusCode": 200, "body": "No action needed"}

    if database_name != config["source_database"] or not table_name:
        logger.info(
            "Event does not match the configured source database; skipping",
            extra={"event_database": database_name,
                   "source_database": config["source_database"],
                   "table": table_name},
        )
        return {"statusCode": 200, "body": "No action needed"}

    action, _ = mirror_table(config, table_name)
    return {
        "statusCode": 200,
        "body": f"{action} table {table_name} in {config['target_database']}",
    }
