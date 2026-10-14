"""DQ Results Sync Lambda.

Trigger: a native Glue ``Data Quality Evaluation Results Available`` event
(``source: aws.glue-dataquality``) forwarded from the Producer account, or a
manual ``{"result_id": "...", "table_name": "..."}`` invocation.

Action: reads the completed Glue DQ result from the Producer account and posts it
onto the matching managed asset in this (Marketplace) account's DataZone domain as
a time-series data point.

This is the event-driven DQ path: it reacts the moment a DQ ruleset finishes in
the Producer, independent of any asset re-publish or data source run. It
coexists with the pull-based DQ sync in ``catalog_sync_mirror`` (which refreshes
DQ as part of a metadata sync); because DQ is posted as time-series data points,
both paths can run independently without overwriting each other.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_REQUIRED_ENV_VARS = (
    "SOURCE_ACCOUNT_ID",
    "SOURCE_DATABASE",
    "SOURCE_ROLE_ARN",
    "DOMAIN_ID",
    "PROJECT_ID",
)

_BOTO_CONFIG = Config(retries={"max_attempts": 5, "mode": "standard"})

_MAX_SEARCH_PAGES = 20
_DQ_FORM_TYPE = "amazon.datazone.DataQualityResultFormType"


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _load_config():
    missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(sorted(missing))}"
        )
    return {
        "source_account": os.environ["SOURCE_ACCOUNT_ID"],
        "source_database": os.environ["SOURCE_DATABASE"],
        "source_role_arn": os.environ["SOURCE_ROLE_ARN"],
        "domain_id": os.environ["DOMAIN_ID"],
        "project_id": os.environ["PROJECT_ID"],
        "account_id": os.environ.get("ACCOUNT_ID", ""),
    }


def _sts_client():
    return boto3.client("sts", config=_BOTO_CONFIG)


def _local_datazone_client():
    return boto3.client("datazone", config=_BOTO_CONFIG)


def get_source_glue_client(source_role_arn):
    """Assume the Producer Glue read role and return a scoped Glue client."""
    creds = _sts_client().assume_role(
        RoleArn=source_role_arn, RoleSessionName="dq-results-sync"
    )["Credentials"]
    return boto3.client(
        "glue",
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        config=_BOTO_CONFIG,
    )


def _load_form(forms, form_name):
    for form in forms or []:
        if form.get("formName") == form_name:
            try:
                return json.loads(form.get("content", "{}"))
            except (ValueError, TypeError):
                return {}
    return None


def find_managed_asset(config, table_name):
    """Return the managed asset id whose GlueTableForm matches this account's
    target and table. Paginates and matches deterministically rather than
    trusting the first search hit.
    """
    dz = _local_datazone_client()
    next_token = None
    pages = 0
    while pages < _MAX_SEARCH_PAGES:
        kwargs = {
            "domainIdentifier": config["domain_id"],
            "owningProjectIdentifier": config["project_id"],
            "searchScope": "ASSET",
            "searchText": table_name,
            "maxResults": 50,
        }
        if next_token:
            kwargs["nextToken"] = next_token
        resp = dz.search(**kwargs)

        for item in resp.get("items", []):
            asset_id = item.get("assetItem", {}).get("identifier")
            if not asset_id:
                continue
            full_asset = dz.get_asset(
                domainIdentifier=config["domain_id"], identifier=asset_id
            )
            glue_form = _load_form(full_asset.get("formsOutput", []), "GlueTableForm")
            if not glue_form:
                continue
            if glue_form.get("tableName") == table_name and (
                not config["account_id"]
                or glue_form.get("catalogId") == config["account_id"]
            ):
                logger.info(
                    "Matched managed asset",
                    extra={"asset_id": asset_id, "table": table_name},
                )
                return asset_id

        next_token = resp.get("nextToken")
        pages += 1
        if not next_token:
            break

    logger.warning("No managed asset matched", extra={"table": table_name})
    return None


def _get_form_type_revision(config):
    try:
        return _local_datazone_client().get_form_type(
            domainIdentifier=config["domain_id"],
            formTypeIdentifier=_DQ_FORM_TYPE,
        ).get("revision", "1")
    except Exception:  # noqa: BLE001 - form type lookup is best-effort
        return "1"


def _convert_glue_dq_to_datazone(dq_result):
    """Project a Glue DQ result into the DataZone time-series content payload."""
    rule_results = dq_result.get("RuleResults", [])
    evaluations = []
    for rule in rule_results:
        evaluation = {
            "types": [rule.get("Name", "Unknown")],
            "description": rule.get("Description", rule.get("EvaluatedRule", "")),
            "details": {},
            "applicableFields": [],
            "status": rule.get("Result", "UNKNOWN"),
        }
        if rule.get("Result") == "FAIL" and rule.get("EvaluationMessage"):
            evaluation["details"]["EVALUATION_MESSAGE"] = rule["EvaluationMessage"]
        evaluations.append(evaluation)

    total = len(rule_results)
    passed = sum(1 for r in rule_results if r.get("Result") == "PASS")
    percentage = (passed / total * 100) if total else 0
    return {
        "evaluations": evaluations,
        "passingPercentage": percentage,
        "evaluationsCount": total,
    }


def post_dq_results(config, asset_id, ruleset_name, dq_result):
    """Post a Glue DQ result onto a managed asset as a time-series data point."""
    content = _convert_glue_dq_to_datazone(dq_result)
    _local_datazone_client().post_time_series_data_points(
        domainIdentifier=config["domain_id"],
        entityIdentifier=asset_id,
        entityType="ASSET",
        forms=[
            {
                "formName": ruleset_name,
                "content": json.dumps(content),
                "timestamp": datetime.now(timezone.utc).timestamp(),
                "typeIdentifier": _DQ_FORM_TYPE,
                "typeRevision": _get_form_type_revision(config),
            }
        ],
    )
    logger.info(
        "Posted DQ results",
        extra={"asset_id": asset_id, "rules": content["evaluationsCount"],
               "passing_percentage": round(content["passingPercentage"])},
    )


def sync_dq(config, result_id, table_name, ruleset_name="dq_rules"):
    """Read a Producer DQ result and post it onto the matching managed asset."""
    asset_id = find_managed_asset(config, table_name)
    if not asset_id:
        return {"statusCode": 404, "body": f"No managed asset for {table_name}"}

    source_glue = get_source_glue_client(config["source_role_arn"])
    dq_result = source_glue.get_data_quality_result(ResultId=result_id)
    post_dq_results(config, asset_id, ruleset_name, dq_result)
    return {"statusCode": 200, "body": f"DQ synced for {table_name} to {asset_id}"}


def handler(event, context):
    """Lambda entry point for manual and EventBridge (native Glue DQ) invocations."""
    logger.info("Received event", extra={"event": event})
    config = _load_config()

    # Manual invocation: {"result_id": "...", "table_name": "..."}
    if isinstance(event, dict) and "result_id" in event:
        return sync_dq(
            config,
            event["result_id"],
            event.get("table_name", ""),
            event.get("ruleset_name", "dq_rules"),
        )

    detail_type = event.get("detail-type", "") if isinstance(event, dict) else ""
    if detail_type != "Data Quality Evaluation Results Available":
        return {"statusCode": 200, "body": "No action needed"}

    detail = event.get("detail", {}) or {}
    context_block = detail.get("context", {}) or {}
    result_id = detail.get("resultId", "")
    table_name = context_block.get("tableName", "")
    database_name = context_block.get("databaseName", "")
    ruleset_names = detail.get("rulesetNames") or ["dq_rules"]

    if database_name != config["source_database"] or not table_name or not result_id:
        logger.info(
            "DQ event does not match the configured source database; skipping",
            extra={"event_database": database_name,
                   "source_database": config["source_database"],
                   "table": table_name},
        )
        return {"statusCode": 200, "body": "No action needed"}

    return sync_dq(config, result_id, table_name, ruleset_names[0])
