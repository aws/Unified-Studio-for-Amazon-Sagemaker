"""Lineage Sync Lambda.

Trigger: an EventBridge schedule (engine-agnostic), or a manual
``{"action": "sync_lineage", "max_results": N}`` invocation.

Action: reads recent OpenLineage ``COMPLETE`` events from the Producer domain,
keeps only those that reference a table mirrored into this (Marketplace) account's
target database, remaps the domain identifier, and posts them to this domain's
lineage.

Why a schedule rather than a per-job event: lineage can be produced by any engine
(Glue, EMR, Athena, Redshift, custom OpenLineage emitters), and there is no
DataZone event for "lineage ingested". A schedule covers every engine and keeps
cost independent of job volume (one scoped sweep per interval, not one run per
job). Posting is made idempotent with a deterministic client token so repeated
sweeps do not create duplicate lineage.

This coexists with the pull-based lineage sync in ``catalog_sync_mirror`` (which
forwards lineage scoped to a single asset during a metadata sync).

Lineage is supplementary: failures are logged and surfaced in the response but a
single bad event does not abort the whole sweep.
"""

import hashlib
import json
import logging
import os

import boto3
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_REQUIRED_ENV_VARS = (
    "SOURCE_ACCOUNT_ID",
    "SOURCE_DOMAIN_ID",
    "SOURCE_DZ_ROLE_ARN",
    "DOMAIN_ID",
    "TARGET_DATABASE",
    "ACCOUNT_ID",
)

_BOTO_CONFIG = Config(retries={"max_attempts": 5, "mode": "standard"})

_MAX_LINEAGE_PAGES = 20
_DEFAULT_MAX_RESULTS = 50


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
        "source_domain_id": os.environ["SOURCE_DOMAIN_ID"],
        "source_dz_role_arn": os.environ["SOURCE_DZ_ROLE_ARN"],
        "domain_id": os.environ["DOMAIN_ID"],
        "target_database": os.environ["TARGET_DATABASE"],
        # Marketplace (this) account + region, used to build the Glue table ARN
        # that this domain's managed assets use as their sourceIdentifier.
        "account_id": os.environ.get("ACCOUNT_ID", ""),
        "region": os.environ.get("AWS_REGION", "us-east-1"),
    }


def _sts_client():
    return boto3.client("sts", config=_BOTO_CONFIG)


def _local_datazone_client():
    return boto3.client("datazone", config=_BOTO_CONFIG)


def _local_glue_client():
    return boto3.client("glue", config=_BOTO_CONFIG)


def get_source_dz_client(source_dz_role_arn):
    """Assume the Producer DataZone read role and return a scoped client."""
    creds = _sts_client().assume_role(
        RoleArn=source_dz_role_arn, RoleSessionName="lineage-sync"
    )["Credentials"]
    return boto3.client(
        "datazone",
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        config=_BOTO_CONFIG,
    )


def get_mirrored_table_names(config):
    """Return the set of table names mirrored into the target database.

    These are the only tables whose lineage should cross into this domain; they
    bound what the sweep forwards so lineage for unshared datasets never comes
    across the account boundary.
    """
    glue = _local_glue_client()
    names = set()
    next_token = None
    while True:
        kwargs = {"DatabaseName": config["target_database"], "MaxResults": 100}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = glue.get_tables(**kwargs)
        for table in resp.get("TableList", []):
            if table.get("Name"):
                names.add(table["Name"])
        next_token = resp.get("NextToken")
        if not next_token:
            break
    return names


def _client_token_for(ol_event, fallback_id):
    """Derive a deterministic idempotency token for a lineage event.

    Keyed on the OpenLineage run id + event type, which survive the domain-id
    remap, so re-posting the same source event is an idempotent no-op.
    """
    run_id = (ol_event.get("run") or {}).get("runId", "")
    basis = f"{run_id}:{ol_event.get('eventType', '')}" if run_id else str(fallback_id)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:128]


def _matched_mirrored_table(dataset, mirrored_tables):
    """Return the mirrored table name this dataset node refers to, or None.

    Glue/Spark emits a ``symlinks`` facet whose identifier name is
    ``table/<database>/<table>`` — the authoritative table identity. We also
    fall back to the dataset ``name`` token. Matching is on the final
    ``<table>`` segment against the set of mirrored table names.
    """
    candidates = []
    symlinks = (dataset.get("facets", {}) or {}).get("symlinks", {}) or {}
    for ident in symlinks.get("identifiers", []) or []:
        candidates.append(ident.get("name", "") or "")  # e.g. table/db/tbl
    candidates.append(dataset.get("name", "") or "")

    for cand in candidates:
        # last path/dot segment is the table name
        last = cand.replace("/", ".").split(".")[-1]
        if last in mirrored_tables:
            return last
    return None


def _relink_dataset_to_marketplace(dataset, table, config):
    """Rewrite a dataset node so DataZone resolves it to THIS domain's asset.

    DataZone links an OpenLineage dataset node to a managed asset only when the
    node's computed ``sourceIdentifier`` equals the asset's sourceIdentifier,
    which for a Glue table asset is the Glue table ARN. We therefore set a Glue
    ``symlinks`` facet pointing at this (Marketplace) account's mirrored table,
    so the node's sourceIdentifier becomes
    ``arn:aws:glue:<region>:<account>:table/<target_db>/<table>`` and links to
    the mirrored asset.
    """
    glue_arn_ns = f"arn:aws:glue:{config['region']}:{config['account_id']}"
    symlink_name = f"table/{config['target_database']}/{table}"
    facets = dataset.setdefault("facets", {})
    facets["symlinks"] = {
        "_producer": "cross-domain-data-product-sync",
        "_schemaURL": (
            "https://openlineage.io/spec/facets/1-0-0/"
            "SymlinksDatasetFacet.json#/$defs/SymlinksDatasetFacet"
        ),
        "identifiers": [
            {"namespace": glue_arn_ns, "name": symlink_name, "type": "TABLE"}
        ],
    }
    return dataset


def _relink_event_datasets(ol_event, mirrored_tables, config):
    """Relink every input/output dataset that references a mirrored table.

    Returns (event, relinked_count). Datasets that do not reference a mirrored
    table are left untouched (they are upstream/unshared and simply won't link
    to an asset in this domain).
    """
    relinked = 0
    for section in ("inputs", "outputs"):
        for dataset in ol_event.get(section, []) or []:
            table = _matched_mirrored_table(dataset, mirrored_tables)
            if table:
                _relink_dataset_to_marketplace(dataset, table, config)
                relinked += 1
    return ol_event, relinked


def sync_recent_lineage(config, max_results=_DEFAULT_MAX_RESULTS):
    """Forward COMPLETE lineage events for mirrored tables into this domain.

    Only successfully-processed COMPLETE events that reference a mirrored table
    are copied; the source domain id is remapped to the target domain id, and
    posting is idempotent (deterministic client token) so repeated sweeps do not
    duplicate lineage.
    """
    mirrored_tables = get_mirrored_table_names(config)
    if not mirrored_tables:
        logger.info("No mirrored tables in target database; nothing to sync")
        return 0

    source_dz = get_source_dz_client(config["source_dz_role_arn"])
    local_dz = _local_datazone_client()
    synced = 0
    next_token = None
    pages = 0

    while pages < _MAX_LINEAGE_PAGES:
        kwargs = {"domainIdentifier": config["source_domain_id"],
                  "maxResults": max_results}
        if next_token:
            kwargs["nextToken"] = next_token
        resp = source_dz.list_lineage_events(**kwargs)

        for item in resp.get("items", []):
            if item.get("processingStatus") != "SUCCESS":
                continue
            try:
                event_resp = source_dz.get_lineage_event(
                    domainIdentifier=config["source_domain_id"], identifier=item["id"]
                )
                body = event_resp.get("event")
                if not body:
                    continue
                raw = body.read().decode("utf-8") if hasattr(body, "read") else str(body)

                # Scope: only forward lineage that references a mirrored table.
                if not any(name in raw for name in mirrored_tables):
                    continue

                ol_event = json.loads(raw)
                if ol_event.get("eventType") != "COMPLETE":
                    continue

                # Relink the datasets that reference a mirrored table so their
                # sourceIdentifier resolves to THIS domain's Glue table ARN
                # (arn:aws:glue:<region>:<account>:table/<target_db>/<table>) —
                # that exact-match on sourceIdentifier is how DataZone attaches
                # the lineage node to the managed asset. Datasets are otherwise
                # identified by raw S3 path and never link to the asset.
                ol_event, relinked = _relink_event_datasets(
                    ol_event, mirrored_tables, config
                )
                if not relinked:
                    # No input/output resolves to a mirrored asset in this
                    # domain; forwarding it would create orphan nodes.
                    continue

                payload = json.dumps(ol_event).encode("utf-8")
                local_dz.post_lineage_event(
                    domainIdentifier=config["domain_id"],
                    event=payload,
                    clientToken=_client_token_for(ol_event, item["id"]),
                )
                synced += 1
            except Exception as exc:  # noqa: BLE001 - lineage is supplementary
                logger.error(
                    "Failed to forward lineage event %s: %s",
                    item.get("id"), str(exc),
                )

        next_token = resp.get("nextToken")
        pages += 1
        if not next_token:
            break

    logger.info("Synced lineage events", extra={"count": synced})
    return synced


def handler(event, context):
    """Lambda entry point for scheduled and manual invocations."""
    logger.info("Received event", extra={"event": event})
    config = _load_config()

    # Manual invocation: {"action": "sync_lineage", "max_results": N}
    if isinstance(event, dict) and event.get("action") == "sync_lineage":
        synced = sync_recent_lineage(config, event.get("max_results", _DEFAULT_MAX_RESULTS))
        return {"statusCode": 200, "body": f"Synced {synced} lineage events"}

    # EventBridge scheduled sweep.
    detail_type = event.get("detail-type", "") if isinstance(event, dict) else ""
    if detail_type != "Scheduled Event":
        return {"statusCode": 200, "body": "No action needed"}

    synced = sync_recent_lineage(config)
    return {"statusCode": 200, "body": f"Synced {synced} lineage events"}
