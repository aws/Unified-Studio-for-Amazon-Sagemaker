"""Self-contained, keep-forever migration snapshot (rollback payload).

Written FIRST, before any mutation. One JSON object per migration under the
project namespace (outside shared/, so the migrated job role can't overwrite it).
Never overwritten -- staleness is handled by a rollback-time warning, not deletion.

Payload is self-contained so rollback needs no live lookups:
- full original job definition (GetJob['Job'])
- prior values of tags written by migration (priorJobTags, added by the migrator)
- original script bytes, base64-inlined
- triggers referencing the job (best-effort)
- full-fidelity connection definitions the job references (GetConnection per
  connection). Stores the SECRET ARN, never the secret VALUE -- the snapshot can
  recreate a connection but holds no credential material. This is CAPTURE only;
  connection migration is a separate workstream and is intentionally not done here.
"""
from __future__ import annotations

import base64
import json
import time

from . import naming

SNAPSHOT_VERSION = 2


def capture_connections(glue, job: dict) -> list:
    """Best-effort full-fidelity capture of every connection the job references.

    Reads the job's top-level Connections list and calls glue:GetConnection for
    each. Returns a list of ConnectionInput-shaped dicts (name + definition).
    Best-effort: a job with no connections returns []; a GetConnection that fails
    (denied, deleted) is skipped rather than aborting the snapshot -- the snapshot
    must still be written before any mutation.

    Does NOT return secret VALUES. glue:GetConnection echoes only the secret ARN
    inside ConnectionProperties (e.g. SECRET_ID), never the credential itself.
    """
    conn_block = job.get("Connections") or {}
    names = conn_block.get("Connections") or []
    captured = []
    for name in names:
        try:
            conn = glue.get_connection(Name=name, HidePassword=True)["Connection"]
        except Exception:
            continue  # best-effort: never block the snapshot on a connection read
        captured.append({"name": name, "definition": conn})
    return captured


def build_snapshot(migration_id: str, job: dict, script_bytes: bytes,
                   triggers: list | None, connections: list | None = None) -> dict:
    return {
        "snapshotVersion": SNAPSHOT_VERSION,
        "migrationId": migration_id,
        "createdAt": int(time.time()),
        "jobName": job["Name"],
        "job": job,
        "scriptBase64": base64.b64encode(script_bytes).decode("ascii"),
        "triggers": triggers or [],
        "connections": connections or [],
    }


def write_snapshot(s3, bucket: str, domain_id: str, project_id: str, job_name: str,
                   migration_id: str, snapshot: dict) -> str:
    """PUT the snapshot JSON; returns the S3 key. Never overwrites (unique migrationId)."""
    key = naming.snapshot_key(domain_id, project_id, job_name, migration_id)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(snapshot, default=str).encode("utf-8"),
        ContentType="application/json",
    )
    return key
