"""Catalog Sync Mirror Lambda.

Overlays Producer-domain business metadata onto the managed asset that a
Marketplace-domain data source creates for a mirrored Glue table, then keeps
data quality (DQ) results and lineage in sync.

Triggers:
  * ``Asset Added To Catalog`` / ``New Asset Version Available`` /
    ``Asset Schema Changed`` from the Producer domain.
  * ``Data Source Run Succeeded`` in the Marketplace domain (bootstrap overlay
    after the managed asset is first created).
  * Manual ``{"table_name": "..."}`` invocation.

Data quality and lineage are pulled from the Producer during a sync cycle; there
is no dedicated DQ event.
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
    "TARGET_DATABASE",
    "SOURCE_ROLE_ARN",
    "SOURCE_DZ_ROLE_ARN",
    "SOURCE_DOMAIN_ID",
    "DOMAIN_ID",
    "PROJECT_ID",
    "ACCOUNT_ID",
)

_BOTO_CONFIG = Config(retries={"max_attempts": 5, "mode": "standard"})

_MAX_SEARCH_PAGES = 20
_MAX_LINEAGE_PAGES = 20
_DESCRIPTION_MAX_LEN = 2048
_DQ_FORM_TYPE = "amazon.datazone.DataQualityResultFormType"


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class AssetSyncError(RuntimeError):
    """Raised when a sync operation fails in a way the caller must surface."""


def _load_config():
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
        "source_dz_role_arn": os.environ["SOURCE_DZ_ROLE_ARN"],
        "source_domain_id": os.environ["SOURCE_DOMAIN_ID"],
        "source_project_id": os.environ.get("SOURCE_PROJECT_ID", ""),
        "domain_id": os.environ["DOMAIN_ID"],
        "project_id": os.environ["PROJECT_ID"],
        "account_id": os.environ["ACCOUNT_ID"],
    }


def _sts_client():
    return boto3.client("sts", config=_BOTO_CONFIG)


def _local_datazone_client():
    return boto3.client("datazone", config=_BOTO_CONFIG)


def _assumed_client(service, role_arn, session_name):
    creds = _sts_client().assume_role(
        RoleArn=role_arn, RoleSessionName=session_name
    )["Credentials"]
    return boto3.client(
        service,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        config=_BOTO_CONFIG,
    )


def get_source_glue_client(config):
    return _assumed_client("glue", config["source_role_arn"], "catalog-sync-glue")


def get_source_dz_client(config):
    return _assumed_client("datazone", config["source_dz_role_arn"], "catalog-sync-dz")


def _load_form(forms, form_name):
    for form in forms or []:
        if form.get("formName") == form_name:
            try:
                return json.loads(form.get("content", "{}"))
            except (ValueError, TypeError):
                logger.warning("Could not parse form", extra={"form": form_name})
            return {}
    return None


def _glue_table_name_from_forms(forms, default):
    glue_form = _load_form(forms, "GlueTableForm")
    if glue_form:
        return glue_form.get("tableName", default)
    return default


def find_managed_asset(config, table_name):
    """Return the managed asset id whose GlueTableForm matches this account,
    target database and table. Paginates and matches deterministically instead
    of trusting the first search hit.
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
            if (
                glue_form.get("catalogId") == config["account_id"]
                and glue_form.get("databaseName") == config["target_database"]
                and glue_form.get("tableName") == table_name
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

    logger.warning(
        "No managed asset matched",
        extra={"table": table_name, "catalog_id": config["account_id"],
               "database": config["target_database"]},
    )
    return None


def find_source_asset_id(config, source_dz, table_name):
    """Deterministically find the Producer asset id for a table by matching its
    GlueTableForm against the source account/database/table.
    """
    next_token = None
    pages = 0
    while pages < _MAX_SEARCH_PAGES:
        kwargs = {
            "domainIdentifier": config["source_domain_id"],
            "searchScope": "ASSET",
            "searchText": table_name,
            "maxResults": 50,
        }
        if config["source_project_id"]:
            kwargs["owningProjectIdentifier"] = config["source_project_id"]
        if next_token:
            kwargs["nextToken"] = next_token
        resp = source_dz.search(**kwargs)

        for item in resp.get("items", []):
            asset_id = item.get("assetItem", {}).get("identifier")
            if not asset_id:
                continue
            full_asset = source_dz.get_asset(
                domainIdentifier=config["source_domain_id"], identifier=asset_id
            )
            glue_form = _load_form(full_asset.get("formsOutput", []), "GlueTableForm")
            if not glue_form:
                continue
            if (
                glue_form.get("databaseName") == config["source_database"]
                and glue_form.get("tableName") == table_name
            ):
                return asset_id

        next_token = resp.get("nextToken")
        pages += 1
        if not next_token:
            break
    return None


def update_managed_asset(config, asset_id, asset_name, description,
                         column_metadata=None, readme=None, summary=None):
    """Create and publish a managed-asset revision, preserving existing forms."""
    dz = _local_datazone_client()
    existing = dz.get_asset(domainIdentifier=config["domain_id"], identifier=asset_id)

    forms_input = []
    column_form_seen = False
    for form in existing.get("formsOutput", []):
        form_name = form.get("formName")
        content = form.get("content", "{}")

        if form_name == "AssetCommonDetailsForm":
            try:
                form_data = json.loads(content)
            except (ValueError, TypeError):
                form_data = {}
            if summary is not None:
                form_data["summary"] = summary
            if readme is not None:
                form_data["readMe"] = readme
            content = json.dumps(form_data)
        elif form_name == "ColumnBusinessMetadataForm" and column_metadata is not None:
            content = json.dumps(column_metadata)
            column_form_seen = True

        forms_input.append({"formName": form_name, "content": content})

    if column_metadata is not None and not column_form_seen:
        forms_input.append(
            {"formName": "ColumnBusinessMetadataForm",
             "content": json.dumps(column_metadata)}
        )

    revision = dz.create_asset_revision(
        domainIdentifier=config["domain_id"],
        identifier=asset_id,
        name=asset_name,
        description=description,
        formsInput=forms_input,
    )
    dz.create_listing_change_set(
        domainIdentifier=config["domain_id"],
        entityIdentifier=asset_id,
        entityType="ASSET",
        action="PUBLISH",
    )
    logger.info(
        "Updated and published managed asset",
        extra={"asset_id": asset_id, "revision": revision.get("revision")},
    )
    return f"Asset {asset_id} updated and published"


def _extract_business_metadata(source_asset):
    common = _load_form(source_asset.get("formsOutput", []), "AssetCommonDetailsForm") or {}
    column_metadata = _load_form(source_asset.get("formsOutput", []),
                                 "ColumnBusinessMetadataForm")
    return {
        "asset_name": source_asset.get("name", ""),
        "description": (source_asset.get("description", "") or "")[:_DESCRIPTION_MAX_LEN],
        "summary": common.get("summary"),
        "readme": common.get("readMe"),
        "column_metadata": column_metadata,
    }


def sync_dq_results(config, table_name, target_asset_id):
    """Copy the latest Glue DQ result for a table onto the managed asset.

    Best-effort by design: DQ is supplementary. Failures are logged and reported
    to the caller but do not fail the overall asset sync.
    """
    try:
        source_glue = get_source_glue_client(config)
        listed = source_glue.list_data_quality_results(
            Filter={
                "DataSource": {
                    "GlueTable": {
                        "DatabaseName": config["source_database"],
                        "TableName": table_name,
                        "CatalogId": config["source_account"],
                    }
                }
            },
            MaxResults=10,
        )
        results = listed.get("Results", [])
        if not results:
            logger.info("No DQ results found", extra={"table": table_name})
            return False

        result_id = results[0].get("ResultId")
        if not result_id:
            return False

        dq_result = source_glue.get_data_quality_result(ResultId=result_id)
        rule_results = dq_result.get("RuleResults", [])
        evaluations = [
            {
                "types": [rule.get("Name", "Unknown")],
                "description": rule.get("Description", rule.get("EvaluatedRule", "")),
                "details": {},
                "applicableFields": [],
                "status": rule.get("Result", "UNKNOWN"),
            }
            for rule in rule_results
        ]
        total = len(rule_results)
        passed = sum(1 for r in rule_results if r.get("Result") == "PASS")
        percentage = (passed / total * 100) if total else 0

        dz = _local_datazone_client()
        try:
            revision = dz.get_form_type(
                domainIdentifier=config["domain_id"],
                formTypeIdentifier=_DQ_FORM_TYPE,
            ).get("revision", "1")
        except Exception:  # noqa: BLE001 - form type lookup is best-effort
            revision = "1"

        dz.post_time_series_data_points(
            domainIdentifier=config["domain_id"],
            entityIdentifier=target_asset_id,
            entityType="ASSET",
            forms=[
                {
                    "formName": dq_result.get("RulesetName", "dq_rules"),
                    "content": json.dumps(
                        {
                            "evaluations": evaluations,
                            "passingPercentage": percentage,
                            "evaluationsCount": total,
                        }
                    ),
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "typeIdentifier": _DQ_FORM_TYPE,
                    "typeRevision": revision,
                }
            ],
        )
        logger.info(
            "Posted DQ results",
            extra={"table": table_name, "rules": total,
                   "passing_percentage": round(percentage)},
        )
        return True
    except Exception as exc:  # noqa: BLE001 - DQ is supplementary, never fatal
        logger.error("DQ sync failed", extra={"table": table_name, "error": str(exc)})
        return False


def sync_lineage_for_asset(config, source_asset_id):
    """Forward COMPLETE lineage events that reference the given source asset.

    Only events whose serialized body references the source asset id are copied,
    so lineage is scoped to the asset being synced rather than the whole domain.
    """
    if not source_asset_id:
        return 0
    try:
        source_dz = get_source_dz_client(config)
        local_dz = _local_datazone_client()
        synced = 0
        next_token = None
        pages = 0

        while pages < _MAX_LINEAGE_PAGES:
            kwargs = {"domainIdentifier": config["source_domain_id"], "maxResults": 50}
            if next_token:
                kwargs["nextToken"] = next_token
            resp = source_dz.list_lineage_events(**kwargs)

            for item in resp.get("items", []):
                if item.get("processingStatus") != "SUCCESS":
                    continue
                event_resp = source_dz.get_lineage_event(
                    domainIdentifier=config["source_domain_id"], identifier=item["id"]
                )
                body = event_resp.get("event")
                if not body:
                    continue
                raw = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
                if source_asset_id not in raw:
                    continue
                ol_event = json.loads(raw)
                if ol_event.get("eventType") != "COMPLETE":
                    continue
                remapped = json.dumps(ol_event).replace(
                    config["source_domain_id"], config["domain_id"]
                )
                local_dz.post_lineage_event(
                    domainIdentifier=config["domain_id"],
                    event=remapped.encode("utf-8"),
                )
                synced += 1

            next_token = resp.get("nextToken")
            pages += 1
            if not next_token:
                break

        logger.info(
            "Synced lineage events",
            extra={"count": synced, "source_asset_id": source_asset_id},
        )
        return synced
    except Exception as exc:  # noqa: BLE001 - lineage is supplementary, never fatal
        logger.error(
            "Lineage sync failed",
            extra={"source_asset_id": source_asset_id, "error": str(exc)},
        )
        return 0


def _sync_source_asset(config, source_asset, target_asset_id):
    metadata = _extract_business_metadata(source_asset)
    table_name = _glue_table_name_from_forms(
        source_asset.get("formsOutput", []), metadata["asset_name"]
    )
    update_managed_asset(
        config,
        target_asset_id,
        metadata["asset_name"],
        metadata["description"],
        metadata["column_metadata"],
        metadata["readme"],
        metadata["summary"],
    )
    sync_dq_results(config, table_name, target_asset_id)
    sync_lineage_for_asset(config, source_asset.get("id") or source_asset.get("identifier"))


def _handle_data_source_run(config):
    """Overlay metadata for every producer table that has a managed asset."""
    source_glue = get_source_glue_client(config)
    source_dz = get_source_dz_client(config)
    results = []
    next_token = None

    while True:
        kwargs = {
            "CatalogId": config["source_account"],
            "DatabaseName": config["source_database"],
            "MaxResults": 100,
        }
        if next_token:
            kwargs["NextToken"] = next_token
        resp = source_glue.get_tables(**kwargs)

        for table in resp.get("TableList", []):
            table_name = table["Name"]
            target_asset_id = find_managed_asset(config, table_name)
            if not target_asset_id:
                results.append(f"{table_name}: no managed asset")
                continue
            source_asset_id = find_source_asset_id(config, source_dz, table_name)
            if not source_asset_id:
                results.append(f"{table_name}: no source asset")
                continue
            source_asset = source_dz.get_asset(
                domainIdentifier=config["source_domain_id"], identifier=source_asset_id
            )
            _sync_source_asset(config, source_asset, target_asset_id)
            results.append(f"{table_name}: synced")

        next_token = resp.get("NextToken")
        if not next_token:
            break

    return {"statusCode": 200, "body": json.dumps({"dataSourceSync": results})}


def _handle_asset_event(config, event):
    from glue_table_sync import mirror_table  # local import; shared table copy logic

    source_asset_id = event.get("detail", {}).get("data", {}).get("assetId", "")
    if not source_asset_id:
        return {"statusCode": 400, "body": "No assetId in event"}

    source_dz = get_source_dz_client(config)
    source_asset = source_dz.get_asset(
        domainIdentifier=config["source_domain_id"], identifier=source_asset_id
    )
    metadata = _extract_business_metadata(source_asset)
    table_name = _glue_table_name_from_forms(
        source_asset.get("formsOutput", []), metadata["asset_name"]
    )

    # Ensure the Glue table mirror exists/updates before overlaying metadata.
    mirror_table(config, table_name)

    target_asset_id = find_managed_asset(config, table_name)
    if not target_asset_id:
        logger.warning(
            "Table mirrored but managed asset not found yet",
            extra={"table": table_name},
        )
        return {
            "statusCode": 202,
            "body": f"Table {table_name} mirrored; awaiting data source run",
        }

    update_managed_asset(
        config,
        target_asset_id,
        metadata["asset_name"],
        metadata["description"],
        metadata["column_metadata"],
        metadata["readme"],
        metadata["summary"],
    )
    sync_dq_results(config, table_name, target_asset_id)
    sync_lineage_for_asset(config, source_asset_id)
    return {"statusCode": 200, "body": f"Asset {target_asset_id} synced"}


def handler(event, context):
    """Lambda entry point.

    Errors from a sync raise, so the invocation fails and the event can be
    retried or routed to the dead-letter queue rather than being masked as 200.
    """
    logger.info("Received event", extra={"event": event})
    config = _load_config()

    if isinstance(event, dict) and "table_name" in event:
        from glue_table_sync import mirror_table

        table_name = event["table_name"]
        mirror_table(config, table_name)
        target_asset_id = find_managed_asset(config, table_name)
        if not target_asset_id:
            return {
                "statusCode": 202,
                "body": f"Table {table_name} mirrored; awaiting data source run",
            }
        source_dz = get_source_dz_client(config)
        source_asset_id = find_source_asset_id(config, source_dz, table_name)
        if source_asset_id:
            source_asset = source_dz.get_asset(
                domainIdentifier=config["source_domain_id"], identifier=source_asset_id
            )
            _sync_source_asset(config, source_asset, target_asset_id)
        return {"statusCode": 200, "body": f"Synced {table_name}"}

    detail_type = event.get("detail-type", "") if isinstance(event, dict) else ""

    if detail_type == "Data Source Run Succeeded":
        return _handle_data_source_run(config)

    if detail_type in (
        "Asset Added To Catalog",
        "New Asset Version Available",
        "Asset Schema Changed",
    ):
        return _handle_asset_event(config, event)

    return {"statusCode": 200, "body": "No action needed"}
