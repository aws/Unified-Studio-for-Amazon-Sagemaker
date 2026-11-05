"""Roll back a migrated job from its keep-forever snapshot.

Restore contract:
1. Full-replace UpdateJob from snapshot['job'] -- restores ScriptLocation,
   removes --smus-orig-asset, reverts enable-flags to their original values,
   and (for a job with connections) restores Connections[] atomically.
   The same UpdateJob landmines apply in reverse: strip read-only fields, and
   drop MaxCapacity when WorkerType+NumberOfWorkers are present.
2. Restore prior values of tags written by migration and remove tags it added.
   Requires priorJobTags, recorded by migration before any mutation.
3. Script: migration does COPY-not-move, so the original script is still at its
   source location. No script restore is needed for a standard rollback; the
   snapshot still carries the original bytes for the copy-was-lost edge case.

Schema note: snapshots may carry the original field names (jobId,
originalScriptBytes) or the newer ones (jobName, scriptBase64). This reader
accepts both.
"""
from __future__ import annotations

from .jobmove import READ_ONLY_FIELDS
from .migrate import _job_arn
from .secret_tags import restore_ops


def build_restore_update(job: dict) -> dict:
    """Build a JobUpdate that restores the original job definition."""
    ju = {k: v for k, v in job.items() if k not in READ_ONLY_FIELDS}
    if ju.get("WorkerType") and ju.get("NumberOfWorkers"):
        ju.pop("MaxCapacity", None)
    return ju


def rollback_from_snapshot(session, snapshot: dict, *, apply: bool = False) -> dict:
    """Restore a job to its pre-migration state from a snapshot dict.

    apply=False (default) is a dry run: builds and returns the restore JobUpdate,
    mutating nothing.
    """
    glue = session.client("glue")

    job = snapshot["job"]
    job_name = job["Name"]
    restore_update = build_restore_update(job)
    prior_tags = snapshot["priorJobTags"]
    tags_restored, tags_removed = restore_ops(prior_tags)

    result = {
        "jobName": job_name,
        "restoreScriptLocation": restore_update["Command"]["ScriptLocation"],
        "jobUpdate": restore_update,
        "tagsRemoved": tags_removed,
        "tagsRestored": tags_restored,
        "applied": False,
    }
    if not apply:
        return result

    glue.update_job(JobName=job_name, JobUpdate=restore_update)

    arn = _job_arn(session, job_name)
    if tags_removed:
        glue.untag_resource(ResourceArn=arn, TagsToRemove=tags_removed)
    if tags_restored:
        glue.tag_resource(ResourceArn=arn, TagsToAdd=tags_restored)

    result["applied"] = True
    return result
