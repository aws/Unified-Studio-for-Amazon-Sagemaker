"""Live e2e fixtures. Every test here is skipped unless GS_SMUS_E2E_* is set.

    eval "$(python .github/workflows/glue-migration-tests/e2e/provision_mysql.py env)"   # long-lived MySQL fixture
    export GS_SMUS_E2E_DOMAIN_ID=... GS_SMUS_E2E_PROJECT_ID=...
    export GS_SMUS_E2E_DOMAIN_REGION=...  # optional: domain region when different from REGION
    export GS_SMUS_E2E_ROLE_ARN=...     # optional: role the migration runs as
    export GS_SMUS_E2E_PROFILE=...      # optional: boto3 profile for setup/teardown
    export GS_SMUS_E2E_RUNNER_PROFILE=...  # optional: profile the migration runs as (wins over ROLE_ARN)
    python -m pytest .github/workflows/glue-migration-tests/e2e -m e2e

Setup/teardown ("the customer's existing Glue Studio state") and independent
assertions use the base credentials. Every call the tool makes, DataZone included,
runs as the runner, which must be a member of each test project.
Everything a test creates is named `e2e-<hex>` and deleted afterwards.
"""
from __future__ import annotations

import json
import os
import time
import uuid

import boto3
import pytest

from migration.glue import datazone_resolve, migrate, rollback
from migration.glue.session import datazone_client

_REQUIRED = ("REGION", "DOMAIN_ID", "PROJECT_ID", "MYSQL_HOST", "MYSQL_PORT", "MYSQL_DB",
             "MYSQL_MASTER_SECRET", "SUBNET_ID", "AZ", "SG_ID", "BUCKET", "JOB_ROLE_ARN")


def pytest_collection_modifyitems(items):
    missing = [k for k in _REQUIRED if not os.environ.get(f"GS_SMUS_E2E_{k}")]
    if missing:
        skip = pytest.mark.skip(reason=f"e2e env not set: GS_SMUS_E2E_{missing[0]} (+{len(missing) - 1})")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip)


@pytest.fixture(scope="session")
def cfg():
    return {k.lower(): os.environ.get(f"GS_SMUS_E2E_{k}")
            for k in _REQUIRED + ("ROLE_ARN", "DOMAIN_REGION")}


@pytest.fixture(scope="session")
def admin(cfg):
    return boto3.Session(profile_name=os.environ.get("GS_SMUS_E2E_PROFILE"), region_name=cfg["region"])


@pytest.fixture(scope="session")
def runner(admin, cfg):
    """Session the migration runs as: a separate runner profile, else the assumed role,
    else the base credentials."""
    if os.environ.get("GS_SMUS_E2E_RUNNER_PROFILE"):
        return boto3.Session(profile_name=os.environ["GS_SMUS_E2E_RUNNER_PROFILE"], region_name=cfg["region"])
    if not cfg["role_arn"]:
        return admin
    c = admin.client("sts").assume_role(RoleArn=cfg["role_arn"], RoleSessionName="gs-smus-e2e")["Credentials"]
    return boto3.Session(aws_access_key_id=c["AccessKeyId"], aws_secret_access_key=c["SecretAccessKey"],
                         aws_session_token=c["SessionToken"], region_name=cfg["region"])


@pytest.fixture
def name():
    return f"e2e-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def source_secret(admin, cfg, name):
    """Fresh, untagged secret holding the MySQL credentials (like a customer's)."""
    sm = admin.client("secretsmanager")
    master = json.loads(sm.get_secret_value(SecretId=cfg["mysql_master_secret"])["SecretString"])
    arn = sm.create_secret(Name=name, SecretString=json.dumps(
        {"username": master["username"], "password": master["password"]}))["ARN"]
    yield arn
    sm.delete_secret(SecretId=arn, ForceDeleteWithoutRecovery=True)


@pytest.fixture
def source_connection(admin, cfg, name, source_secret):
    """V2 MYSQL Glue connection to the fixture DB, as Glue Studio would create it."""
    glue = admin.client("glue")
    glue.create_connection(ConnectionInput={
        "Name": name, "ConnectionType": "MYSQL", "Description": "gs-smus e2e source",
        "ConnectionProperties": {"HOST": cfg["mysql_host"], "PORT": cfg["mysql_port"],
                                 "DATABASE": cfg["mysql_db"], "ROLE_ARN": cfg["job_role_arn"]},
        "AuthenticationConfiguration": {"AuthenticationType": "BASIC", "SecretArn": source_secret},
        "PhysicalConnectionRequirements": {"SubnetId": cfg["subnet_id"], "SecurityGroupIdList": [cfg["sg_id"]],
                                           "AvailabilityZone": cfg["az"]},
        "ValidateCredentials": False, "ValidateForComputeEnvironments": ["SPARK"]})
    try:
        wait_connection_ready(glue, name)
        yield name
    finally:
        wait_connection_ready(glue, name, check=False)
        glue.delete_connection(ConnectionName=name)


def wait_connection_ready(glue, name, timeout=300, check=True):
    """V2 VPC connections are created asynchronously and cannot be deleted mid-flight."""
    deadline = time.time() + timeout
    while True:
        c = glue.get_connection(Name=name, HidePassword=True)["Connection"]
        status = c.get("Status", "READY")
        if status == "READY" or (status == "FAILED" and not check):
            return c
        if status == "FAILED" or time.time() > deadline:
            raise AssertionError(f"connection {name} status {status}: {c.get('StatusReason')}")
        time.sleep(5)


# Customer-style Spark job: reads MySQL through the Glue connection named in
# --CONNECTION_NAME and fails unless it gets rows back.
JOB_SCRIPT = """
import sys
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

args = getResolvedOptions(sys.argv, ["CONNECTION_NAME"])
glue = GlueContext(SparkContext.getOrCreate())
rows = glue.create_dynamic_frame.from_options(
    connection_type="mysql",
    connection_options={"useConnectionProperties": "true", "connectionName": args["CONNECTION_NAME"],
                        "dbtable": "information_schema.ENGINES"},
).toDF().count()
print(f"E2E_ROWS={rows}")
if rows < 1:
    raise SystemExit("no rows read through the connection")
"""


@pytest.fixture
def source_job(admin, cfg, name, source_connection):
    """Glue Studio-style job running as its own role, attached to the source connection."""
    s3, glue = admin.client("s3"), admin.client("glue")
    key = f"e2e/{name}/job.py"
    s3.put_object(Bucket=cfg["bucket"], Key=key, Body=JOB_SCRIPT.encode())
    glue.create_job(Name=name, Role=cfg["job_role_arn"], GlueVersion="5.0", WorkerType="G.1X",
                    NumberOfWorkers=2, Timeout=15,
                    Command={"Name": "glueetl", "ScriptLocation": f"s3://{cfg['bucket']}/{key}",
                             "PythonVersion": "3"},
                    DefaultArguments={"--CONNECTION_NAME": source_connection, "--enable-metrics": ""},
                    Connections={"Connections": [source_connection]})
    yield name
    glue.delete_job(JobName=name)
    s3.delete_object(Bucket=cfg["bucket"], Key=key)


@pytest.fixture(scope="session")
def run_job():
    return _run_job


def _run_job(glue, job_name, arguments=None, timeout=1200):
    """Start a run and wait for a terminal state; returns (state, error message)."""
    kw = {"Arguments": arguments} if arguments else {}
    deadline = time.time() + timeout
    while True:  # a just-finished run can still count against MaxConcurrentRuns briefly
        try:
            run_id = glue.start_job_run(JobName=job_name, **kw)["JobRunId"]
            break
        except glue.exceptions.ConcurrentRunsExceededException:
            if time.time() > deadline - 60:
                raise
            time.sleep(15)
    while time.time() < deadline:
        run = glue.get_job_run(JobName=job_name, RunId=run_id)["JobRun"]
        if run["JobRunState"] in ("SUCCEEDED", "FAILED", "ERROR", "TIMEOUT", "STOPPED"):
            return run["JobRunState"], run.get("ErrorMessage")
        time.sleep(15)
    raise AssertionError(f"job run {run_id} still running after {timeout}s")


@pytest.fixture
def move_job(admin, runner, cfg, name, source_connection):
    """Create a Glue Studio job with this script (CRLF, BOM) and move it into the project."""
    s3, glue = admin.client("s3"), admin.client("glue")
    dz = datazone_client(runner, cfg["domain_region"] or cfg["region"])
    bucket = datazone_resolve.resolve_project_bucket(dz, cfg["domain_id"], cfg["project_id"])
    key, moved = f"e2e/{name}/job.py", {}

    def move(script: str, arguments=None):
        s3.put_object(Bucket=cfg["bucket"], Key=key, Body=b"\xef\xbb\xbf" + script.replace("\n", "\r\n").encode())
        glue.create_job(Name=name, Role=cfg["job_role_arn"], GlueVersion="5.0", WorkerType="G.1X",
                        NumberOfWorkers=2, DefaultArguments=arguments or {},
                        Command={"Name": "glueetl", "ScriptLocation": f"s3://{cfg['bucket']}/{key}",
                                 "PythonVersion": "3"},
                        Connections={"Connections": [source_connection]})
        moved.update(migrate.migrate_job(runner, job_name=name, domain_id=cfg["domain_id"],
                                         project_id=cfg["project_id"], bucket=bucket, region=cfg["region"],
                                         domain_region=cfg["domain_region"],
                                         apply=True))
        return name, bucket
    try:
        yield move
    finally:
        if moved:
            snap = json.loads(s3.get_object(Bucket=bucket, Key=moved["snapshotKey"])["Body"].read())
            rollback.rollback_from_snapshot(runner, snap, apply=True)
            for k in (moved["snapshotKey"], moved["destKey"]):
                s3.delete_object(Bucket=bucket, Key=k)
            glue.delete_job(JobName=name)
        s3.delete_object(Bucket=cfg["bucket"], Key=key)
