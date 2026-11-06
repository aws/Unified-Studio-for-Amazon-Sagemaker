"""Resolve a SMUS project's environment via DataZone.

Given a (domain, project), find the project's default S3 bucket so the customer
only has to pass --domain-id/--project-id (an explicit --bucket override still
wins). Select the default IAM connection using the SMUS toolkit's names, then
read the S3 bucket from that connection's environment.
"""
from __future__ import annotations

import re

# provisionedResources entries whose value is an s3://... URI or a bare bucket.
_S3_URI = re.compile(r"^s3://([^/]+)")


def _bucket_from_value(value: str) -> str | None:
    if not value:
        return None
    m = _S3_URI.match(value)
    if m:
        return m.group(1)
    # some environments expose the bare bucket name (no scheme)
    if "/" not in value and value.startswith("amazon-sagemaker-"):
        return value
    return None


def resolve_project_iam_connection(datazone, domain_id: str, project_id: str) -> dict | None:
    """The toolkit's default IAM connection (default.iam or project.iam)."""
    token = None
    while True:
        page = datazone.list_connections(
            domainIdentifier=domain_id, projectIdentifier=project_id, type="IAM",
            **({"nextToken": token} if token else {}),
        )
        for connection in page.get("items", []):
            if connection.get("name") in ("default.iam", "project.iam"):
                return datazone.get_connection(
                    domainIdentifier=domain_id, identifier=connection["connectionId"],
                )
        token = page.get("nextToken")
        if not token:
            return None


def resolve_project_bucket(datazone, domain_id: str, project_id: str) -> str:
    """Return the project's default S3 bucket name.

    Read only the environment referenced by the default IAM connection.
    Raises LookupError if no default environment or bucket is found.
    """
    connection = resolve_project_iam_connection(datazone, domain_id, project_id)
    env_id = (connection or {}).get("environmentId")
    if not env_id:
        raise LookupError(
            f"no default IAM environment found for project {project_id} "
            f"in domain {domain_id}; pass --bucket to override"
        )

    detail = datazone.get_environment(domainIdentifier=domain_id, identifier=env_id)
    for res in detail.get("provisionedResources", []) or []:
        bucket = _bucket_from_value(res.get("value", ""))
        if bucket:
            return bucket

    raise LookupError(
        f"could not resolve an S3 bucket from the default environment of project "
        f"{project_id} (domain {domain_id}); pass --bucket to override"
    )
