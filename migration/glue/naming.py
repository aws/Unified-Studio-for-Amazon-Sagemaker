"""Deterministic S3 path/key construction for the SMUS project layout.

Project bucket layout:
    s3://<bucket>/<domainId>/<projectId>/shared/jobs/<jobName>/<jobName>.py
                  ^^^^^^^^^^^^^^^^^^^^^^^ project root prefix (BEFORE shared/)

- The absolute `ScriptLocation` is the full s3:// URI above.
- `--smus-orig-asset` is PROJECT-RELATIVE (relative to `shared/`):
    jobs/<jobName>/<jobName>.py
- Snapshots live under the project namespace but NOT under shared/, so the
  migrated job's execution role (scoped to shared/jobs/*) cannot overwrite them:
    <domainId>/<projectId>/.migration-snapshots/<jobName>/<migrationId>.json
"""
from __future__ import annotations

import hashlib
import re
from typing import Mapping, NamedTuple, Optional

SHARED_JOBS_PREFIX = "shared/jobs"

SMUS_NAME_MAX = 41  # The SMUS UI is stricter than the DataZone backend.
_HASH_LEN = 8
_CLONE_SUFFIX = "-SMUSClone"
_INVALID = re.compile(r"[^A-Za-z0-9_-]+")
SNAPSHOTS_PREFIX = ".migration-snapshots"



def project_root_prefix(domain_id: str, project_id: str) -> str:
    """The `<domainId>/<projectId>` prefix that precedes shared/."""
    return f"{domain_id}/{project_id}"


def canonical_script_key(domain_id: str, project_id: str, job_name: str) -> str:
    """S3 key (no bucket) for the migrated script's canonical location."""
    root = project_root_prefix(domain_id, project_id)
    return f"{root}/{SHARED_JOBS_PREFIX}/{job_name}/{job_name}.py"


def canonical_script_uri(bucket: str, domain_id: str, project_id: str, job_name: str) -> str:
    """Absolute s3:// URI for ScriptLocation."""
    return f"s3://{bucket}/{canonical_script_key(domain_id, project_id, job_name)}"


def smus_orig_asset(job_name: str) -> str:
    """Project-relative asset path for the --smus-orig-asset default argument."""
    return f"{SHARED_JOBS_PREFIX.split('/', 1)[1]}/{job_name}/{job_name}.py"  # jobs/<job>/<job>.py


def snapshot_key(domain_id: str, project_id: str, job_name: str, migration_id: str) -> str:
    """S3 key for a keep-forever migration snapshot, outside shared/."""
    root = project_root_prefix(domain_id, project_id)
    return f"{root}/{SNAPSHOTS_PREFIX}/{job_name}/{migration_id}.json"


def datazone_connection_name(glue_name: str, *, project_id: str) -> str:
    """Map a Glue connection name to a DataZone-valid, deterministic, unique name.

    <sanitized-prefix>-<8 hex of sha256(project, original)>-SMUSClone, at most
    41 characters. DataZone names the Glue clone after the DataZone connection
    and Glue names are account-wide, so the project is hashed in: the same C
    migrated into two projects gets two clones.
    The hash is over the ORIGINAL name, so inputs that sanitize/truncate to the
    same prefix still differ.

    The result matches ^[A-Za-z0-9_-]+$ (no '.'). Keep this format stable so
    reruns can find clones created by earlier versions.
    """
    seed = f"{project_id}\x00{glue_name}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:_HASH_LEN]
    prefix = _INVALID.sub("_", glue_name)
    if not prefix or not (prefix[0].isalnum() or prefix[0] == "_"):
        prefix = "c" + prefix
    prefix = prefix[: SMUS_NAME_MAX - _HASH_LEN - 1 - len(_CLONE_SUFFIX)]
    return f"{prefix}-{digest}{_CLONE_SUFFIX}"


class ConnectionNameConflict(ValueError):
    """The generated name is taken by a connection with foreign or unknown ownership."""


class ResolvedName(NamedTuple):
    name: str
    reuse: bool  # True: a prior migration of this connection already created it


def resolve_datazone_connection_name(
    glue_name: str, existing: Mapping[str, Optional[str]], *, project_id: str
) -> ResolvedName:
    """Pick the DataZone connection name for `glue_name`, deduping against `existing`.

    existing: connection name -> the source Glue connection it was migrated from
    (read from our ownership marker), or None if the name is taken by something
    that is not ours (a DataZone connection, or a bare Glue connection).
    Reuse a prior migration of this source, create if the name is free, or raise
    immediately if its ownership is foreign or unknown.
    """
    name = datazone_connection_name(glue_name, project_id=project_id)
    if name not in existing:
        return ResolvedName(name, reuse=False)
    if existing[name] == glue_name:
        return ResolvedName(name, reuse=True)
    raise ConnectionNameConflict(
        f"connection name {name!r} is already taken by a connection "
        "with foreign or unknown ownership")


_MARKER = re.compile(r"\[gs-smus-src:[0-9a-f]{16}\]")


def is_clone_description(description: str) -> bool:
    """True when a DataZone connection description carries our ownership marker."""
    return bool(_MARKER.search(description or ""))


def source_marker(glue_name: str) -> str:
    """Ownership marker stored in the DataZone connection description."""
    return f"[gs-smus-src:{hashlib.sha256(glue_name.encode('utf-8')).hexdigest()[:16]}]"
