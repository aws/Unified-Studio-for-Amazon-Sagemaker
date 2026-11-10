"""Connection-migration e2e against real Glue / Secrets Manager / DataZone."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlencode

import pytest
from botocore.validate import validate_parameters

from migration.glue import connections, connmigrate, jobmove, naming, rollback, secret_tags
from migration.glue.session import datazone_client

pytestmark = pytest.mark.e2e


def _can_read(session, arn):
    sm = session.client("secretsmanager")
    try:
        sm.get_secret_value(SecretId=arn)  # value discarded; only access is asserted
        return True
    except sm.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "AccessDeniedException":
            return False
        raise


def eventually(fn, expected, timeout=60):
    """Tags and tag-based authz are eventually consistent after TagResource."""
    deadline = time.time() + timeout
    while (got := fn()) != expected and time.time() < deadline:
        time.sleep(3)
    return got


def _tags(admin, arn):
    return {t["Key"]: t["Value"] for t in admin.client("secretsmanager").describe_secret(SecretId=arn).get("Tags", [])}


def test_foreign_project_secret_is_shared_automatically(admin, runner, cfg, source_secret):
    admin.client("secretsmanager").tag_resource(
        SecretId=source_secret, Tags=[{"Key": "AmazonDataZoneProject", "Value": "some-other-project"}])
    foreign = {"AmazonDataZoneProject": "some-other-project"}
    assert eventually(lambda: _tags(admin, source_secret), foreign) == foreign
    sm = runner.client("secretsmanager")
    change = secret_tags.tag_secret(sm, source_secret, domain_id=cfg["domain_id"],
                                    project_id=cfg["project_id"])
    want = {**foreign, "for-use-with-all-datazone-projects": "true"}
    assert eventually(lambda: _tags(admin, source_secret), want) == want
    assert eventually(lambda: _can_read(runner, source_secret), True)
    secret_tags.restore_secret_tags(runner.client("secretsmanager"), change)
    assert eventually(lambda: _tags(admin, source_secret), foreign) == foreign


def _connections(glue, job):
    return glue.get_job(JobName=job)["Job"]["Connections"]["Connections"]


def _migration_tags(tags):
    return {key for key in tags if key in {"AmazonDataZoneProject", "AmazonDataZoneMigratedJob"}
            or key.startswith(jobmove.PRE_MIGRATION_CONNECTION_TAG_PREFIX)}


def test_raw_connection_tags_accept_maximum_names_at_tag_capacity(
        admin, runner, cfg, source_job):
    glue = admin.client("glue")
    account = admin.client("sts").get_caller_identity()["Account"]
    arn = f"arn:aws:glue:{cfg['region']}:{account}:job/{source_job}"
    names = ["x" * 255, "é" * 255, "数据库" * 85, " legacy-db_1.:/=+-@\u00a0数据库 "]
    names.extend(f"connection-{i}" for i in range(44))
    planned = jobmove.migration_tags(
        {"Connections": {"Connections": names}}, {}, cfg["domain_id"], cfg["project_id"])
    runner.client("glue").tag_resource(ResourceArn=arn, TagsToAdd=planned)
    tags = glue.get_tags(ResourceArn=arn)["Tags"]
    assert len(tags) == 50
    assert [tags[f"AmazonDataZonePreMigrationConnection-{i}"] for i in range(48)] == names


# Reads once through a literal connection name and once through a job argument.
FLOW_SCRIPT = """\
import sys
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
args = getResolvedOptions(sys.argv, ["CONNECTION_NAME"])
glue = GlueContext(SparkContext.getOrCreate())
literal = glue.create_dynamic_frame.from_options(
    connection_type="mysql",
    connection_options={"useConnectionProperties": "true", "connectionName": "SRC",
                        "dbtable": "information_schema.ENGINES"}).toDF().count()
argument = glue.create_dynamic_frame.from_options(
    connection_type="mysql",
    connection_options={"useConnectionProperties": "true", "connectionName": args["CONNECTION_NAME"],
                        "dbtable": "information_schema.ENGINES"}).toDF().count()
print(f"E2E_ROWS={literal},{argument}")
if min(literal, argument) < 1:
    raise SystemExit("no rows read through the connection")
"""


def _script(s3, job):
    b, _, key = job["Command"]["ScriptLocation"][len("s3://"):].partition("/")
    return s3.get_object(Bucket=b, Key=key)["Body"].read()


def test_job_migration_preserves_originals_while_clones_are_created_separately(
        admin, runner, cfg, run_job, move_job, source_connection, source_secret):
    glue, s3 = admin.client("glue"), admin.client("s3")
    domain_region = cfg["domain_region"] or cfg["region"]
    dz = datazone_client(admin, domain_region)
    job, _ = move_job(FLOW_SCRIPT.replace("SRC", source_connection), {"--CONNECTION_NAME": source_connection})
    original = glue.get_job(JobName=job)["Job"]
    script = _script(s3, original)
    state, err = run_job(glue, job)
    assert state == "SUCCEEDED", err
    job_arn = f"arn:aws:glue:{cfg['region']}:{admin.client('sts').get_caller_identity()['Account']}:job/{job}"
    tags = glue.get_tags(ResourceArn=job_arn)["Tags"]
    assert tags["AmazonDataZoneProject"] == cfg["project_id"]
    assert tags["AmazonDataZoneMigratedJob"] == "true"
    assert "AmazonDataZoneDomain" not in tags
    assert tags[jobmove.PRE_MIGRATION_CONNECTION_TAG_PREFIX + "0"] == source_connection

    kw = dict(glue=runner.client("glue"), sm=runner.client("secretsmanager"),
              dz=datazone_client(runner, domain_region), domain_id=cfg["domain_id"],
              project_id=cfg["project_id"], name=source_connection, shared_secret=True)
    migrated = connmigrate.migrate_connection(**kw)
    try:
        dzc = dz.get_connection(domainIdentifier=cfg["domain_id"], identifier=migrated.datazone_id)
        assert (dzc["projectId"], connmigrate._status(dzc)[0]) == (cfg["project_id"], "READY")
        clone = glue.get_connection(Name=migrated.glue_name, HidePassword=True)["Connection"]
        env = connmigrate.resolve_tooling_environment(dz, cfg["domain_id"], cfg["project_id"])
        assert clone["ConnectionProperties"]["ROLE_ARN"] == env.user_role_arn
        assert eventually(lambda: _can_read(runner, source_secret), True)

        current = glue.get_job(JobName=job)["Job"]
        for field in ("Connections", "Role", "DefaultArguments", "Command"):
            assert current[field] == original[field]
        assert _script(s3, current) == script
        assert _connections(glue, job) == [source_connection]
        state, err = run_job(glue, job)
        assert state == "SUCCEEDED", err
        again = connmigrate.migrate_connection(**kw)
        assert again.reused and again.glue_name == migrated.glue_name
        assert _script(s3, glue.get_job(JobName=job)["Job"]) == script
    finally:
        dz.delete_connection(domainIdentifier=cfg["domain_id"], identifier=migrated.datazone_id)
        assert eventually(lambda: _datazone_gone(dz, cfg["domain_id"], migrated.datazone_id), True, timeout=300)
    assert _connections(glue, job) == [source_connection]


def _datazone_gone(dz, domain_id, cid):
    try:
        detail = dz.get_connection(domainIdentifier=domain_id, identifier=cid)
        return connmigrate._status(detail)[0] == "DELETED"
    except dz.exceptions.ResourceNotFoundException:
        return True


@pytest.mark.skipif(not os.environ.get("GS_SMUS_E2E_PROJECT2_ID"), reason="GS_SMUS_E2E_PROJECT2_ID not set")
def test_same_connection_into_two_projects(admin, runner, cfg, source_connection):
    """Glue names are account-wide: each project gets its own clone, and each clone
    retains the source connection settings with its own project role."""
    domain_region = cfg["domain_region"] or cfg["region"]
    dz = datazone_client(admin, domain_region)
    made = []
    try:
        for project in (cfg["project_id"], os.environ["GS_SMUS_E2E_PROJECT2_ID"]):
            m = connmigrate.migrate_connection(
                glue=runner.client("glue"), sm=runner.client("secretsmanager"),
                dz=datazone_client(runner, domain_region),
                domain_id=cfg["domain_id"], project_id=project, name=source_connection, shared_secret=True)
            made.append(m)
            # DataZone names the Glue clone after the DataZone connection; we send that name too
            assert m.glue_name == m.datazone_name and "." not in m.glue_name
            source = runner.client("glue").get_connection(Name=source_connection, HidePassword=True)["Connection"]
            clone = runner.client("glue").get_connection(Name=m.glue_name, HidePassword=True)["Connection"]
            source_input = connections.to_datazone_input(source)
            clone_input = connections.to_datazone_input(clone)
            source_input.pop("description", None)
            clone_input.pop("description", None)
            assert source_input == clone_input
        assert made[0].glue_name != made[1].glue_name
    finally:
        for m in made:
            dz.delete_connection(domainIdentifier=cfg["domain_id"], identifier=m.datazone_id)
        for m in made:
            assert eventually(lambda: _datazone_gone(dz, cfg["domain_id"], m.datazone_id), True, timeout=300)


CUTOVER_SCRIPT = """\
import sys
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
args = getResolvedOptions(sys.argv, ["CONNECTION_NAME"])
glue = GlueContext(SparkContext.getOrCreate())
CONNECTION = "PREFIX" + "SUFFIX"
if CONNECTION != "SRC":
    raise RuntimeError("business condition changed")
def read(options):
    print("E2E_CONNECTION=" + options["connectionName"], flush=True)
    return glue.create_dynamic_frame.from_options(
        connection_type="mysql", connection_options=options).toDF().count()
literal = read({"useConnectionProperties": "true", "connectionName": "SRC",
                "dbtable": "information_schema.ENGINES"})
argument = read({"useConnectionProperties": "true", "connectionName": args["CONNECTION_NAME"],
                 "dbtable": "information_schema.ENGINES"})
print(f"E2E_ROWS={literal},{argument}", flush=True)
if min(literal, argument) < 1:
    raise SystemExit("no rows read through the connection")
"""


def _cli_result(runner, command, arguments):
    credentials = runner.get_credentials().get_frozen_credentials()
    env = dict(os.environ)
    for key in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE"):
        env.pop(key, None)
    env.update(AWS_ACCESS_KEY_ID=credentials.access_key,
               AWS_SECRET_ACCESS_KEY=credentials.secret_key,
               AWS_SESSION_TOKEN=credentials.token or "")
    result = subprocess.run(
        [sys.executable, "-m", command, *arguments],
        cwd=Path(__file__).resolve().parents[4],
        env=env, text=True, capture_output=True, timeout=1200)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.split("\n", 1)[1])


@pytest.mark.parametrize("domain_tag", [None, "another-domain"], ids=["project-only", "conflicting-domain"])
def test_project_owned_job_is_skipped_without_original_asset(
        admin, runner, cfg, source_job, domain_tag):
    glue, s3 = admin.client("glue"), admin.client("s3")
    account = admin.client("sts").get_caller_identity()["Account"]
    arn = f"arn:aws:glue:{cfg['region']}:{account}:job/{source_job}"
    tags = {"AmazonDataZoneProject": cfg["project_id"]}
    if domain_tag:
        tags["AmazonDataZoneDomain"] = domain_tag
    glue.tag_resource(ResourceArn=arn, TagsToAdd=tags)
    assert eventually(lambda: glue.get_tags(ResourceArn=arn)["Tags"], tags) == tags
    original = glue.get_job(JobName=source_job)["Job"]
    assert "--smus-orig-asset" not in original["DefaultArguments"]
    script = _script(s3, original)
    args = ["--job-name", source_job, "--domain-id", cfg["domain_id"],
            "--project-id", cfg["project_id"], "--region", cfg["region"],
            "--domain-region", cfg["domain_region"] or cfg["region"]]
    for apply in ([], ["--apply"]):
        result = _cli_result(runner, "migration.glue.cli", [*args, *apply])
        assert result["skipped"] and result["alreadyMigrated"]
        assert result["applied"] == bool(apply and result["passRole"]["needsUpdate"])
        assert result["bucketSource"] == "not-resolved" and result["jobUpdate"] == {}
        assert glue.get_job(JobName=source_job)["Job"] == original
        assert glue.get_tags(ResourceArn=arn)["Tags"] == tags
        assert _script(s3, original) == script


def test_job_migration_and_rollback_preserve_existing_domain_tag(
        admin, runner, cfg, source_job):
    glue, s3 = admin.client("glue"), admin.client("s3")
    account = admin.client("sts").get_caller_identity()["Account"]
    arn = f"arn:aws:glue:{cfg['region']}:{account}:job/{source_job}"
    original_tags = {"AmazonDataZoneProject": "another-project", "AmazonDataZoneDomain": "another-domain"}
    glue.tag_resource(ResourceArn=arn, TagsToAdd=original_tags)
    assert eventually(lambda: glue.get_tags(ResourceArn=arn)["Tags"], original_tags) == original_tags
    original = glue.get_job(JobName=source_job)["Job"]
    args = ["--job-name", source_job, "--domain-id", cfg["domain_id"],
            "--project-id", cfg["project_id"], "--region", cfg["region"],
            "--domain-region", cfg["domain_region"] or cfg["region"]]
    preview = _cli_result(runner, "migration.glue.cli", args)
    try:
        moved = _cli_result(runner, "migration.glue.cli", [*args, "--apply"])
        assert moved["applied"]
        tags = glue.get_tags(ResourceArn=arn)["Tags"]
        assert tags["AmazonDataZoneProject"] == cfg["project_id"]
        assert tags["AmazonDataZoneDomain"] == original_tags["AmazonDataZoneDomain"]
        assert tags[jobmove.PRE_MIGRATION_CONNECTION_TAG_PREFIX + "0"] == (
            original["Connections"]["Connections"][0])
        snapshot = json.loads(s3.get_object(
            Bucket=moved["bucket"], Key=moved["snapshotKey"])["Body"].read())
        assert "AmazonDataZoneDomain" not in snapshot["priorJobTags"]
        assert snapshot["priorJobTags"]["AmazonDataZoneProject"] == original_tags["AmazonDataZoneProject"]
        assert snapshot["priorJobTags"][jobmove.PRE_MIGRATION_CONNECTION_TAG_PREFIX + "0"] is None
        retry = _cli_result(runner, "migration.glue.cli", [*args, "--apply"])
        assert retry["skipped"] and not retry["applied"]
    finally:
        prefix = f"{cfg['domain_id']}/{cfg['project_id']}/.migration-snapshots/{source_job}/"
        snapshots = [item["Key"] for page in s3.get_paginator("list_objects_v2").paginate(
            Bucket=preview["bucket"], Prefix=prefix) for item in page.get("Contents", [])]
        try:
            if snapshots:
                snapshot = json.loads(s3.get_object(
                    Bucket=preview["bucket"], Key=snapshots[0])["Body"].read())
                restored = rollback.rollback_from_snapshot(runner, snapshot, apply=True)
                assert restored["applied"]
                assert "AmazonDataZoneDomain" not in restored["tagsRemoved"]
                assert eventually(lambda: glue.get_tags(ResourceArn=arn)["Tags"], original_tags) == original_tags
                assert rollback.build_restore_update(glue.get_job(JobName=source_job)["Job"]) == (
                    rollback.build_restore_update(original))
        finally:
            for key in [*snapshots, naming.canonical_script_key(cfg["domain_id"], cfg["project_id"], source_job)]:
                s3.delete_object(Bucket=preview["bucket"], Key=key)


def test_cli_rewrite_cutover_execution_and_recovery(
        admin, runner, cfg, run_job, source_job, source_connection, source_secret, request):
    """Exercise migration and recovery with literal, wrapper, and argument consumers."""
    glue, s3, sm = admin.client("glue"), admin.client("s3"), admin.client("secretsmanager")
    domain_region = cfg["domain_region"] or cfg["region"]
    dz = datazone_client(admin, domain_region)
    runner_glue, runner_s3 = runner.client("glue"), runner.client("s3")
    update_shape = runner_glue.meta.service_model.shape_for("JobUpdate")
    account = admin.client("sts").get_caller_identity()["Account"]
    arn = f"arn:aws:glue:{cfg['region']}:{account}:job/{source_job}"
    original = glue.get_job(JobName=source_job)["Job"]
    source_bucket, _, source_key = original["Command"]["ScriptLocation"][5:].partition("/")
    script = CUTOVER_SCRIPT.replace("PREFIX", source_connection[:4]).replace(
        "SUFFIX", source_connection[4:]).replace("SRC", source_connection)
    original_bytes = b"\xef\xbb\xbf" + script.replace("\n", "\r\n").encode()
    s3.put_object(Bucket=source_bucket, Key=source_key, Body=original_bytes,
                  ContentType="text/x-python", Metadata={"purpose": "cli-e2e"},
                  Tagging="purpose=cli-e2e")
    # Use existing project ownership tags on this new fixture secret.
    sm.tag_resource(SecretId=source_secret, Tags=[
        {"Key": "AmazonDataZoneProject", "Value": cfg["project_id"]},
        {"Key": "AmazonDataZoneDomain", "Value": cfg["domain_id"]}])
    args = ["--job-name", source_job, "--domain-id", cfg["domain_id"],
            "--project-id", cfg["project_id"], "--region", cfg["region"],
            "--domain-region", domain_region]
    moved, clones = {}, []
    checkpoint, destination, object_args = None, None, None
    project_bucket = None
    runs = []
    print(json.dumps({"job": source_job, "source": source_connection, "phase": "setup"}), flush=True)

    def execute(label, expected):
        print(f"E2E_PHASE={label}", flush=True)
        state, error = run_job(glue, source_job, {"--CONNECTION_NAME": source_connection})
        assert state == "SUCCEEDED", error
        run = glue.get_job_runs(JobName=source_job, MaxResults=1)["JobRuns"][0]
        logs = admin.client("logs")

        def output():
            try:
                return "".join(e["message"] for e in logs.get_log_events(
                    logGroupName="/aws-glue/jobs/output", logStreamName=run["Id"],
                    startFromHead=True)["events"])
            except logs.exceptions.ResourceNotFoundException:
                return ""

        assert eventually(lambda: re.findall(r"E2E_CONNECTION=([^\s]+)", output()) ==
                          [expected, expected] and "E2E_ROWS=" in output(), True)
        messages = output()
        selected = re.findall(r"E2E_CONNECTION=([^\s]+)", messages)
        rows = re.search(r"E2E_ROWS=(\d+),(\d+)", messages)
        assert selected == [expected, expected], selected
        assert rows and min(map(int, rows.groups())) > 0
        runs.append({"phase": label, "runId": run["Id"], "state": state,
                     "connections": selected, "rows": list(map(int, rows.groups()))})
        print(json.dumps(runs[-1]), flush=True)
        return runs[-1]["rows"]

    def cleanup_objects():
        if not project_bucket:
            return
        prefix = f"{cfg['domain_id']}/{cfg['project_id']}/.migration-snapshots/{source_job}/"
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=project_bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                s3.delete_object(Bucket=project_bucket, Key=item["Key"])
        s3.delete_object(Bucket=project_bucket, Key=naming.canonical_script_key(
            cfg["domain_id"], cfg["project_id"], source_job))
        print("E2E_CLEANUP=project_objects", flush=True)

    def cleanup_clones():
        marker = naming.source_marker(source_connection)
        for summary in connmigrate._project_connections(dz, cfg["domain_id"], cfg["project_id"]):
            detail = connmigrate._get_live(dz, cfg["domain_id"], summary["connectionId"])
            if detail and marker in (detail.get("description") or ""):
                cid = summary["connectionId"]
                dz.delete_connection(domainIdentifier=cfg["domain_id"], identifier=cid)
                assert eventually(lambda: _datazone_gone(dz, cfg["domain_id"], cid),
                                  True, timeout=300)
        print("E2E_CLEANUP=project_clones", flush=True)

    def restore_original():
        current_job = glue.get_job(JobName=source_job)["Job"]
        tags = glue.get_tags(ResourceArn=arn)["Tags"]
        if current_job["Command"] != original["Command"] or _migration_tags(tags):
            snapshot = (json.loads(s3.get_object(Bucket=moved["bucket"], Key=moved["snapshotKey"])[
                "Body"].read()) if moved else {
                    "job": original, "priorJobTags": dict.fromkeys(_migration_tags(tags))})
            rollback.rollback_from_snapshot(runner, snapshot, apply=True)
        assert glue.get_job(JobName=source_job)["Job"]["Command"] == original["Command"]
        assert not _migration_tags(glue.get_tags(ResourceArn=arn)["Tags"])
        print("E2E_CLEANUP=original_job_restored", flush=True)

    def stop_runs():
        active = [r["Id"] for r in glue.get_job_runs(JobName=source_job)["JobRuns"]
                  if r["JobRunState"] in ("STARTING", "RUNNING", "WAITING", "STOPPING")]
        if active:
            glue.batch_stop_job_run(JobName=source_job, JobRunIds=active)
            assert eventually(lambda: all(glue.get_job_run(JobName=source_job, RunId=r)["JobRun"][
                "JobRunState"] not in ("STARTING", "RUNNING", "WAITING", "STOPPING")
                for r in active), True, timeout=180)

    # Pytest runs all finalizers even when an earlier cleanup reports a failure.
    for finalizer in (cleanup_objects, cleanup_clones, restore_original, stop_runs):
        request.addfinalizer(finalizer)
    try:
        baseline = execute("original", source_connection)
        preview = _cli_result(runner, "migration.glue.cli", args)
        project_bucket = preview["bucket"]
        validate_parameters(preview["jobUpdate"], update_shape)
        assert not preview["applied"]
        assert not _cli_result(runner, "migration.glue.cli_connections", args)["applied"]
        moved = _cli_result(runner, "migration.glue.cli", [*args, "--apply"])
        assert moved["applied"]
        tags = glue.get_tags(ResourceArn=arn)["Tags"]
        assert tags["AmazonDataZoneProject"] == cfg["project_id"]
        assert tags["AmazonDataZoneMigratedJob"] == "true"
        assert "AmazonDataZoneDomain" not in tags
        assert tags[jobmove.PRE_MIGRATION_CONNECTION_TAG_PREFIX + "0"] == source_connection
        retry = _cli_result(runner, "migration.glue.cli", [*args, "--apply"])
        assert retry["skipped"] and not retry["applied"]
        current = glue.get_job(JobName=source_job)["Job"]
        assert current["Connections"] == original["Connections"]
        assert current["Role"] == original["Role"]
        assert _script(s3, current) == original_bytes
        migrated = _cli_result(runner, "migration.glue.cli_connections", [*args, "--apply"])
        clones = migrated["connections"]
        assert migrated["applied"] and len(clones) == 1
        clone = clones[0]
        assert clone["sourceName"] == source_connection and clone["glueName"]
        detail = dz.get_connection(domainIdentifier=cfg["domain_id"], identifier=clone["datazoneId"])
        assert (detail["projectId"], connmigrate._status(detail)[0]) == (cfg["project_id"], "READY")
        assert connmigrate._glue_name_of(detail) == clone["glueName"]
        cloned = glue.get_connection(Name=clone["glueName"], HidePassword=True)["Connection"]
        source = glue.get_connection(Name=source_connection, HidePassword=True)["Connection"]
        environment = connmigrate.resolve_tooling_environment(dz, cfg["domain_id"], cfg["project_id"])
        assert cloned["ConnectionProperties"]["ROLE_ARN"] == environment.user_role_arn
        assert connections.secret_arn(cloned) == connections.secret_arn(source) == source_secret
        assert cloned["PhysicalConnectionRequirements"] == source["PhysicalConnectionRequirements"]
        assert _connections(glue, source_job) == [source_connection]
        assert _script(s3, current) == original_bytes
        assert _tags(admin, source_secret) == {
            "AmazonDataZoneProject": cfg["project_id"], "AmazonDataZoneDomain": cfg["domain_id"]}
        again = _cli_result(runner, "migration.glue.cli_connections", [*args, "--apply"])
        assert again["connections"][0]["reused"]
        assert again["connections"][0]["glueName"] == clone["glueName"]

        destination = (moved["bucket"], moved["destKey"])
        head = s3.head_object(Bucket=destination[0], Key=destination[1])
        tags = s3.get_object_tagging(Bucket=destination[0], Key=destination[1])["TagSet"]
        object_args = {"ContentType": head["ContentType"], "Metadata": head["Metadata"],
                       "Tagging": urlencode([(t["Key"], t["Value"]) for t in tags])}
        for field in ("ServerSideEncryption", "SSEKMSKeyId"):
            if field in head:
                object_args[field] = head[field]
        checkpoint = copy.deepcopy(current)
        target = json.dumps(clone["glueName"]).encode()
        literal = f'"connectionName": "{source_connection}"'.encode()
        argument = b'"connectionName": args["CONNECTION_NAME"]'
        assert original_bytes.count(literal) == original_bytes.count(argument) == 1
        rewritten = original_bytes.replace(literal, b'"connectionName": ' + target).replace(
            argument, b'"connectionName": {' + json.dumps(source_connection).encode() +
            b': ' + target + b'}[args["CONNECTION_NAME"]]')
        compile(rewritten, "<rewritten-e2e-script>", "exec")
        assert f'if CONNECTION != "{source_connection}":'.encode() in rewritten
        assert rewritten.startswith(b"\xef\xbb\xbf") and b"\r\n" in rewritten
        update = rollback.build_restore_update(current)
        update["Connections"] = {"Connections": [clone["glueName"]]}
        validate_parameters(update, update_shape)
        assert current == checkpoint
        assert not glue.get_triggers(DependentJobName=source_job)["Triggers"]
        assert glue.get_job(JobName=source_job)["Job"] == checkpoint
        assert _script(s3, checkpoint) == original_bytes
        runner_s3.put_object(Bucket=destination[0], Key=destination[1], Body=rewritten, **object_args)
        runner_glue.update_job(JobName=source_job, JobUpdate=update)
        live = glue.get_job(JobName=source_job)["Job"]
        for field in ("Role", "DefaultArguments", "NonOverridableArguments", "Command"):
            assert live.get(field) == checkpoint.get(field)
        assert _connections(glue, source_job) == [clone["glueName"]]
        assert _script(s3, glue.get_job(JobName=source_job)["Job"]) == rewritten
        assert s3.head_object(Bucket=destination[0], Key=destination[1])["Metadata"] == head["Metadata"]
        assert s3.get_object_tagging(Bucket=destination[0], Key=destination[1])["TagSet"] == tags
        assert execute("cutover", clone["glueName"]) == baseline

        runner_s3.put_object(Bucket=destination[0], Key=destination[1], Body=original_bytes, **object_args)
        runner_glue.update_job(JobName=source_job, JobUpdate=rollback.build_restore_update(checkpoint))
        recovered = glue.get_job(JobName=source_job)["Job"]
        for field in ("Role", "DefaultArguments", "NonOverridableArguments", "Command", "Connections"):
            assert recovered.get(field) == checkpoint.get(field)
        assert _script(s3, recovered) == original_bytes
        assert _connections(glue, source_job) == [source_connection]
        assert execute("recovered", source_connection) == baseline
        assert glue.get_tags(ResourceArn=arn)["Tags"][
            jobmove.PRE_MIGRATION_CONNECTION_TAG_PREFIX + "0"] == source_connection
        print(json.dumps({"job": source_job, "source": source_connection, "clone": clone,
                          "snapshotKey": moved["snapshotKey"], "runs": runs}), flush=True)
    finally:
        print("E2E_PHASE=cleanup", flush=True)
