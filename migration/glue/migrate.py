"""Orchestrate a job's migration: snapshot -> PassRole -> copy -> repoint -> tag."""
from __future__ import annotations

import uuid

from . import datazone_resolve, jobmove, passrole, snapshot


def migrate_job(session, *, job_name: str, domain_id: str, project_id: str,
                bucket: str | None = None, region: str = "us-east-2",
                domain_region: str | None = None,
                apply: bool = False) -> dict:
    """Migrate a single Glue script job into the SMUS project layout.

    bucket is OPTIONAL: when omitted it is resolved from DataZone (the project's
    default S3 bucket). An explicit bucket overrides resolution. Resolution uses
    DataZone in domain_region (or region when omitted).

    apply=False (default) is a dry run: it builds and returns the JobUpdate that
    WOULD be sent, mutating nothing.

    Jobs whose AmazonDataZoneProject tag matches the target project skip job
    updates, but still plan/apply the project's PassRole grant.
    """
    glue = session.client("glue")
    job = glue.get_job(JobName=job_name)["Job"]
    source_uri = job["Command"]["ScriptLocation"]
    migration_id = uuid.uuid4().hex

    # Step 1: already-migrated check (tags live outside the job def).
    tags = glue.get_tags(ResourceArn=_job_arn(session, job_name)).get("Tags", {})
    already = jobmove.is_already_migrated(job, tags, domain_id, project_id)

    result = {
        "jobName": job_name,
        "migrationId": migration_id,
        "bucket": bucket,
        "bucketSource": "override" if bucket else "not-resolved",
        "sourceScript": source_uri,
        "destScript": source_uri,
        "jobUpdate": {},
        "alreadyMigrated": already,
        "applied": False,
    }

    datazone = session_datazone(session, domain_region or region)
    iam = session.client("iam")
    grant = passrole.plan(iam, datazone, domain_id, project_id, job["Role"])
    result["passRole"] = grant

    if already:
        result["skipped"] = True
        result["skipReason"] = (
            "Job already belongs to this project (matching AmazonDataZoneProject tag)."
        )
        if apply:
            passrole.apply(iam, grant)
            result["applied"] = grant["needsUpdate"]
        return result

    s3 = session.client("s3")
    bucket_source = "override"
    if not bucket:
        bucket = datazone_resolve.resolve_project_bucket(datazone, domain_id, project_id)
        bucket_source = "resolved"
    job_update = jobmove.build_job_update(job, bucket, domain_id, project_id)
    result.update(
        bucket=bucket, bucketSource=bucket_source,
        destScript=job_update["Command"]["ScriptLocation"], jobUpdate=job_update)

    tags_to_add = jobmove.migration_tags(job, tags, domain_id, project_id)
    result["tagsToAdd"] = tags_to_add
    if not apply:
        return result

    # 1. Snapshot FIRST (before any mutation).
    src_bucket, src_key = jobmove._parse_s3_uri(source_uri)
    script_bytes = s3.get_object(Bucket=src_bucket, Key=src_key)["Body"].read()
    try:
        triggers = glue.get_triggers(DependentJobName=job_name).get("Triggers", [])
    except Exception:
        triggers = []  # best-effort; GetTriggers may be denied or job may have none
    connections = snapshot.capture_connections(glue, job)  # best-effort, capture-only
    snap = snapshot.build_snapshot(migration_id, job, script_bytes, triggers, connections)
    snap["priorJobTags"] = {key: tags.get(key) for key in tags_to_add}
    result["snapshotKey"] = snapshot.write_snapshot(
        s3, bucket, domain_id, project_id, job_name, migration_id, snap
    )

    # Grant before updating the job; a denied IAM write leaves the job untouched.
    passrole.apply(iam, grant)

    # 2. Copy script (copy, NOT move -- original stays for rollback).
    result["destKey"] = jobmove.copy_script(
        s3, source_uri, bucket, domain_id, project_id, job_name
    )

    # 3. Repoint via UpdateJob.
    glue.update_job(JobName=job_name, JobUpdate=job_update)

    # 4. Tag LAST -- the commit marker that flips the job editable in SMUS.
    glue.tag_resource(
        ResourceArn=_job_arn(session, job_name),
        TagsToAdd=tags_to_add,
    )

    result["applied"] = True
    return result


def _job_arn(session, job_name: str) -> str:
    sts = session.client("sts")
    ident = sts.get_caller_identity()
    region = session.region_name
    partition = session.get_partition_for_region(region)
    return f"arn:{partition}:glue:{region}:{ident['Account']}:job/{job_name}"


def session_datazone(session, region: str):
    """Build a DataZone client in the domain region (delegates to session.datazone_client)."""
    from . import session as session_mod
    return session_mod.datazone_client(session, region)
