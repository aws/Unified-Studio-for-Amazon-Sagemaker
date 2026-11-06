"""Build the UpdateJob payload and move the script -- all verified landmines.

Verified UpdateJob landmines (each cost a real failure to discover):
1. Read-only fields: GetJob echoes Name/CreatedOn/LastModifiedOn/AllocatedCapacity;
   UpdateJob rejects them inside JobUpdate. Strip them.
2. MaxCapacity vs WorkerType: GetJob echoes a computed MaxCapacity even for a
   WorkerType job; UpdateJob rejects MaxCapacity alongside WorkerType+NumberOfWorkers.
   Drop MaxCapacity when both are present.
3. SourceControlDetails must be dropped on migrate (we sever the GS git link).
4. Connections preserved VERBATIM -- never append the SMUS project default
   (Glue rejects a job straddling two VPCs).
5. Role is REQUIRED in JobUpdate and requires iam:PassRole on the caller ONLY
   when the Role is set/changed. We round-trip it unchanged.
6. DefaultArguments enable-flags stored as "" fail SMUS console editor validation.
   Allowlist-only: rewrite ""->"true" for known Glue presence-boolean flags.
   "" and "true" are equivalent to the Glue runtime for these, so this is GS-safe.
   NEVER blanket-coerce other "".
"""
from __future__ import annotations

import unicodedata

from . import naming

READ_ONLY_FIELDS = frozenset({
    "Name", "CreatedOn", "LastModifiedOn", "AllocatedCapacity", "ProfileName", "AutoUpgradeMetadata",
})
PRE_MIGRATION_CONNECTION_TAG_PREFIX = "AmazonDataZonePreMigrationConnection-"


def migration_tags(job: dict, tags: dict, domain_id: str, project_id: str) -> dict:
    names = (job.get("Connections") or {}).get("Connections") or []
    # Retrying a partial migration must preserve the original connection list.
    original = {key: value for key, value in tags.items()
                if key.startswith(PRE_MIGRATION_CONNECTION_TAG_PREFIX)}
    if not original:
        original = {f"{PRE_MIGRATION_CONNECTION_TAG_PREFIX}{i}": name
                    for i, name in enumerate(names)}
    for key, name in original.items():
        if len(name) > 256:
            raise ValueError(f"{key} exceeds Glue's 256-character tag value limit")
        if any(unicodedata.category(char)[0] not in "LNZ" and char not in "_.:/=+-@"
               for char in name):
            raise ValueError(
                f"Connection name {name!r} contains characters unsupported by Glue tags")
    tags_to_add = {
        "AmazonDataZoneProject": project_id,
        "AmazonDataZoneMigratedJob": "true",
        **original,
    }
    if len({key for key in tags | tags_to_add if not key.startswith("aws:")}) > 50:
        raise ValueError("Migration tags exceed Glue's 50-user-tag limit")
    return tags_to_add

# Glue "enable" toggle flags: presence == ON. Old console stored them as "".
# Rewrite ""->"true" for THESE keys only; every other arg passes through as-is.
GLUE_BOOLEAN_ENABLE_FLAGS = frozenset({
    "--enable-metrics",
    "--enable-glue-datacatalog",
    "--enable-continuous-cloudwatch-log",
    "--enable-spark-ui",
    "--enable-job-insights",
    "--enable-observability-metrics",
    "--enable-auto-scaling",
})


def normalize_default_arguments(default_arguments: dict | None) -> dict:
    """Allowlist-only: rewrite "" -> "true" for known Glue enable-toggle flags.

    All other keys/values are left exactly as-is. Does NOT blanket-coerce, so
    path args (--TempDir, --spark-event-logs-path) and custom args are untouched.
    """
    if not default_arguments:
        return dict(default_arguments or {})
    out = dict(default_arguments)
    for key in GLUE_BOOLEAN_ENABLE_FLAGS:
        if out.get(key) == "":
            out[key] = "true"
    return out


def is_already_migrated(job: dict, tags: dict, domain_id: str, project_id: str) -> bool:
    """Skip jobs owned by the target project, including native SMUS jobs.

    AmazonDataZoneProject from GetTags is the sole ownership marker.
    """
    return (tags or {}).get("AmazonDataZoneProject") == project_id


def build_job_update(job: dict, bucket: str, domain_id: str, project_id: str) -> dict:
    """Translate a GetJob['Job'] into a JobUpdate that migrates the script job."""
    name = job["Name"]

    # Start from the job, strip read-only fields.
    ju = {k: v for k, v in job.items() if k not in READ_ONLY_FIELDS}

    # Landmine 3: sever the GS git link.
    ju.pop("SourceControlDetails", None)

    # Landmine 2: MaxCapacity vs WorkerType.
    if ju.get("WorkerType") and ju.get("NumberOfWorkers"):
        ju.pop("MaxCapacity", None)

    # Repoint the script to the canonical SMUS location.
    command = dict(ju.get("Command", {}))
    command["ScriptLocation"] = naming.canonical_script_uri(bucket, domain_id, project_id, name)
    ju["Command"] = command

    # DefaultArguments: add --smus-orig-asset, then normalize enable-flags (landmine 6).
    da = dict(ju.get("DefaultArguments", {}))
    da["--smus-orig-asset"] = naming.smus_orig_asset(name)
    ju["DefaultArguments"] = normalize_default_arguments(da)

    # Landmine 4: Connections stay verbatim -- do nothing (they are already in ju).
    # Landmine 5: Role stays (already in ju, round-tripped unchanged).
    return ju


def copy_script(s3, source_uri: str, bucket: str, domain_id: str, project_id: str, job_name: str) -> str:
    """Copy (not move) the script to the canonical SMUS key. Returns the dest key."""
    src_bucket, src_key = _parse_s3_uri(source_uri)
    dest_key = naming.canonical_script_key(domain_id, project_id, job_name)
    s3.copy_object(
        Bucket=bucket,
        Key=dest_key,
        CopySource={"Bucket": src_bucket, "Key": src_key},
    )
    return dest_key


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"not an s3 uri: {uri!r}")
    rest = uri[len("s3://"):]
    bucket, _, key = rest.partition("/")
    return bucket, key
