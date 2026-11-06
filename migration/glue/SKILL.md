---
name: migrate-job-and-connections
description: Use when migrating Glue Python jobs and connections to SageMaker Unified Studio, including manual selections, discovery results, and partially completed migrations.
---

Use supplied inputs/customer credentials; ask only for missing required values. No account/profile search.

Run commands from the repository root with dependencies installed from `migration/glue/requirements.txt` (see [README.md](README.md)).

For every job in the requested migration, connection cloning is required before reporting completion, regardless of whether the job was selected manually, migrated through discovery, or migrated earlier. A job already tagged to the target project still needs the connection step. Reuse ready clones through the CLI's idempotent behavior.

1. For a new manual selection, run `python -m migration.glue.cli`. If job migration already succeeded, resume at step 2. For discovery, use `python -m migration.glue.discover_cli` and process every matched job with its own domain/project from the output, including already-migrated results; leave unmatched/ambiguous jobs alone.
2. For each job, run `python -m migration.glue.cli_connections --job-name JOB` against that job's target, even if job migration skipped it as already migrated. An empty connection list completes this step without changes. Never treat cloning as an optional follow-up.

Both per-job commands take `--job-name`, `--domain-id`, `--project-id`, `--region`, `--apply`. `--region` is the project resource region. If the domain is elsewhere, add `--domain-region` to both per-job commands; discovery only supports a single region. Add `--profile` if supplied. Dry run: omit `--apply` from every command, preview both job and connection steps for all selected/matched jobs, report previews, stop. Failures: report output and incomplete jobs and stop further migration commands. Still offer cutover for earlier jobs with successfully cloned connections; never report a failed job complete or offer its cutover.

CLIs and the rollback helper own migration and rollback. No implementation reads, extra checks/tests/backups/readbacks or ad-hoc scripts/fixes.

For requested migration rollback, use `migration.glue.rollback.rollback_from_snapshot(session, snapshot)` with the snapshot from before the first change, following the [README recovery example](README.md#recovery). Preview first; use `apply=True` when rollback is authorized. Never reimplement restoration with manual AWS calls. Report that rollback overwrites later job edits and retains cloned connections, secret tags, copied scripts, snapshots and project PassRole policies. Recovery from a failed connection cutover uses its live backups as described below, not the pre-migration snapshot.

After rollback completes, explicitly tell the user: **“Rollback did not remove the `iam:PassRole` permission on the Glue job execution role from the SMUS project execution role.”** Explain that other jobs may share the grant and consumers must be checked before manually removing it.

Cloning automatically tags untagged and foreign-project secrets `for-use-with-all-datazone-projects=true`, preserving existing project ownership. Proceed without a separate sharing confirmation or `--shared-secret` flag. Report the CLI's tag changes as part of the result.

Save/report output, snapshot URI when available, and per-job `connections[].sourceName`→`glueName` mappings. After successful apply for each job with cloned connections, explicitly ask: **“Would you also like me to migrate your job to use the cloned DataZone connections?”** Identify the job when processing multiple jobs and explain that this rewrites script references and switches attached connections. Ask the question even when reporting that the current references are unchanged. For jobs with no connections, omit this question. Stop unless the user agrees to cutover for that job:

1. Back up live script bytes/job settings.
2. Check GlueContext arguments (`connectionName`, `catalog_connection`, `extract_jdbc_conf`), catalog/SQL table connection dependencies, and Glue API lookups (`get_connection`, `get_connections`/paginator selections). Stop on unresolved names/wrappers/selections or catalog dependencies on originals; never retarget shared tables. Trace variables/arguments; rewrite only proven connection uses, preserving logic. Compile without execution.
3. Upload to same URI preserving properties. Use `migration.glue.rollback.build_restore_update(current_job)`; map attachments, retain unrelated settings/attachments; `UpdateJob`.
4. Read back script/attachments. Restore backups on write/check failure before job starts. Report edits/checks; keep original connections.
