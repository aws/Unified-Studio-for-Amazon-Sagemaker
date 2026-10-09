"""Lineage Sync Lambda.

Trigger: a Glue ``Glue Job State Change`` (``SUCCEEDED``) event forwarded from the
Producer account, or a manual ``{"action": "sync_lineage", "max_results": N}``
invocation.

Action: reads recent OpenLineage ``COMPLETE`` events from the Producer domain,
remaps the domain identifier to this (Marketplace) domain, and posts them to this
domain's lineage. This is the event-driven lineage path; it coexists with the
pull-based lineage sync in ``catalog_sync_mirror`` (which forwards lineage scoped
to an asset during a metadata sync).

Lineage is supplementary: failures are logged and surfaced in the response but a
single bad event does not abort the whole run.
"""

import json
import logging
import os

import boto3
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_REQUIRED_ENV_VARS = (
    "SOURCE_DOMAIN_ID",
    "SOURCE_DZ_ROLE_ARN",
    "DOMAIN_ID",
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
        "source_domain_id": os.environ["SOURCE_DOMAIN_ID"],
        "source_dz_role_arn": os.environ["SOURCE_DZ_ROLE_ARN"],
        "domain_id": os.environ["DOMAIN_ID"],
    }


def _sts_client():
    return boto3.client("sts", config=_BOTO_CONFIG)


def _local_datazone_client():
    return boto3.client("datazone", config=_BOTO_CONFIG)


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


def sync_recent_lineage(config, max_results=_DEFAULT_MAX_RESULTS):
    """Forward COMPLETE lineage events from the Producer domain to this domain.

    Only successfully-processed COMPLETE events are copied; the source domain id
    is remapped to the target domain id before posting.
    """
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
            except Exception as exc:  # noqa: BLE001 - lineage is supplementary
                logger.error(
                    "Failed to forward lineage event",
                    extra={"event_id": item.get("id"), "error": str(exc)},
                )

        next_token = resp.get("nextToken")
        pages += 1
        if not next_token:
            break

    logger.info("Synced lineage events", extra={"count": synced})
    return synced


def handler(event, context):
    """Lambda entry point for manual and EventBridge (Glue job) invocations."""
    logger.info("Received event", extra={"event": event})
    config = _load_config()

    # Manual invocation: {"action": "sync_lineage", "max_results": N}
    if isinstance(event, dict) and event.get("action") == "sync_lineage":
        synced = sync_recent_lineage(config, event.get("max_results", _DEFAULT_MAX_RESULTS))
        return {"statusCode": 200, "body": f"Synced {synced} lineage events"}

    detail_type = event.get("detail-type", "") if isinstance(event, dict) else ""
    if detail_type != "Glue Job State Change":
        return {"statusCode": 200, "body": "No action needed"}

    state = (event.get("detail", {}) or {}).get("state", "")
    if state != "SUCCEEDED":
        return {"statusCode": 200, "body": "No action needed"}

    synced = sync_recent_lineage(config)
    return {"statusCode": 200, "body": f"Synced {synced} lineage events"}
