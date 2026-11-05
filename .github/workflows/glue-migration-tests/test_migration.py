"""Unit tests for the pure logic: naming + jobmove landmines. No AWS calls."""
import pytest
from botocore.session import get_session
from botocore.validate import validate_parameters

from migration.glue import jobmove, naming, rollback


# ---- naming ----

def test_canonical_script_key_has_project_root_prefix():
    key = naming.canonical_script_key("dzd-abc", "proj123", "myjob")
    assert key == "dzd-abc/proj123/shared/jobs/myjob/myjob.py"


def test_smus_orig_asset_is_project_relative():
    assert naming.smus_orig_asset("myjob") == "jobs/myjob/myjob.py"


def test_snapshot_key_outside_shared():
    key = naming.snapshot_key("dzd-abc", "proj123", "myjob", "mig1")
    assert key == "dzd-abc/proj123/.migration-snapshots/myjob/mig1.json"
    assert "/shared/" not in key


# ---- DefaultArguments allowlist normalization (landmine 6) ----

def test_normalize_only_touches_allowlisted_empty_flags():
    da = {
        "--enable-metrics": "",              # allowlisted -> "true"
        "--enable-glue-datacatalog": "",     # allowlisted -> "true"
        "--enable-spark-ui": "true",         # allowlisted, already set -> unchanged
        "--TempDir": "",                     # NOT allowlisted -> stays ""
        "--my-custom-flag": "",              # NOT allowlisted -> stays ""
        "--job-language": "python",          # unchanged
    }
    out = jobmove.normalize_default_arguments(da)
    assert out["--enable-metrics"] == "true"
    assert out["--enable-glue-datacatalog"] == "true"
    assert out["--enable-spark-ui"] == "true"
    assert out["--TempDir"] == ""            # path arg untouched
    assert out["--my-custom-flag"] == ""     # custom arg untouched
    assert out["--job-language"] == "python"


def test_normalize_handles_empty_and_none():
    assert jobmove.normalize_default_arguments({}) == {}
    assert jobmove.normalize_default_arguments(None) == {}


# ---- build_job_update landmines ----

def _base_job():
    return {
        "Name": "myjob",
        "CreatedOn": "2020-01-01",
        "LastModifiedOn": "2020-01-02",
        "AllocatedCapacity": 10,
        "MaxCapacity": 10.0,
        "WorkerType": "G.1X",
        "NumberOfWorkers": 10,
        "Role": "arn:aws:iam::111:role/exec",
        "Command": {"Name": "glueetl", "ScriptLocation": "s3://src-bucket/scripts/x.py"},
        "DefaultArguments": {"--enable-metrics": "", "--job-language": "python"},
        "SourceControlDetails": {"Provider": "GITHUB"},
    }


def test_strips_read_only_fields():
    ju = jobmove.build_job_update(_base_job(), "destbkt", "dzd-abc", "proj123")
    for f in ("Name", "CreatedOn", "LastModifiedOn", "AllocatedCapacity"):
        assert f not in ju


def test_drops_maxcapacity_with_workertype():
    ju = jobmove.build_job_update(_base_job(), "destbkt", "dzd-abc", "proj123")
    assert "MaxCapacity" not in ju
    assert ju["WorkerType"] == "G.1X"
    assert ju["NumberOfWorkers"] == 10


def test_drops_source_control_details():
    ju = jobmove.build_job_update(_base_job(), "destbkt", "dzd-abc", "proj123")
    assert "SourceControlDetails" not in ju


def test_repoints_script_and_adds_orig_asset():
    ju = jobmove.build_job_update(_base_job(), "destbkt", "dzd-abc", "proj123")
    assert ju["Command"]["ScriptLocation"] == "s3://destbkt/dzd-abc/proj123/shared/jobs/myjob/myjob.py"
    assert ju["DefaultArguments"]["--smus-orig-asset"] == "jobs/myjob/myjob.py"


def test_keeps_role():
    ju = jobmove.build_job_update(_base_job(), "destbkt", "dzd-abc", "proj123")
    assert ju["Role"] == "arn:aws:iam::111:role/exec"


def test_normalizes_enable_flag_in_full_build():
    ju = jobmove.build_job_update(_base_job(), "destbkt", "dzd-abc", "proj123")
    assert ju["DefaultArguments"]["--enable-metrics"] == "true"


def test_connections_preserved_verbatim():
    job = _base_job()
    job["Connections"] = {"Connections": ["orig-conn"]}
    ju = jobmove.build_job_update(job, "destbkt", "dzd-abc", "proj123")
    assert ju["Connections"] == {"Connections": ["orig-conn"]}  # not appended


# ---- Step 1: already-migrated detection ----

def _migrated_job():
    job = _base_job()
    job["DefaultArguments"] = {
        "--smus-orig-asset": "jobs/myjob/myjob.py",
        "--job-language": "python",
    }
    return job


def test_already_migrated_when_project_tag_matches():
    tags = {"AmazonDataZoneDomain": "dzd-abc", "AmazonDataZoneProject": "proj123"}
    assert jobmove.is_already_migrated(_migrated_job(), tags, "dzd-abc", "proj123") is True


def test_project_tag_is_sufficient_without_domain_or_orig_asset():
    tags = {"AmazonDataZoneProject": "proj123"}
    assert jobmove.is_already_migrated(_base_job(), tags, "dzd-abc", "proj123") is True


def test_domain_tag_does_not_affect_project_ownership():
    tags = {"AmazonDataZoneDomain": "another-domain", "AmazonDataZoneProject": "proj123"}
    assert jobmove.is_already_migrated(_base_job(), tags, "dzd-abc", "proj123") is True


def test_not_migrated_when_tags_missing():
    assert jobmove.is_already_migrated(_migrated_job(), {}, "dzd-abc", "proj123") is False


def test_not_migrated_when_tags_point_at_different_project():
    tags = {"AmazonDataZoneDomain": "dzd-abc", "AmazonDataZoneProject": "OTHER"}
    assert jobmove.is_already_migrated(_migrated_job(), tags, "dzd-abc", "proj123") is False


def test_not_migrated_when_orig_asset_present_but_no_tags_yet():
    # partial state: repointed (has --smus-orig-asset) but tag step never ran
    assert jobmove.is_already_migrated(_migrated_job(), None, "dzd-abc", "proj123") is False


# ---- snapshot connection capture (capture-only, secret ARN not value) ----

from migration.glue import snapshot


class _FakeGlue:
    def __init__(self, conns):
        self._conns = conns  # {name: definition-or-Exception}

    def get_connection(self, Name, HidePassword=True):
        v = self._conns[Name]
        if isinstance(v, Exception):
            raise v
        return {"Connection": v}


def test_capture_connections_empty_when_job_has_none():
    job = {"Name": "j"}  # no Connections block
    assert snapshot.capture_connections(_FakeGlue({}), job) == []


def test_capture_connections_returns_full_definitions():
    job = {"Name": "j", "Connections": {"Connections": ["c1", "c2"]}}
    glue = _FakeGlue({
        "c1": {"Name": "c1", "ConnectionType": "JDBC",
                "ConnectionProperties": {"SECRET_ID": "arn:aws:secretsmanager:...:secret:c1"}},
        "c2": {"Name": "c2", "ConnectionType": "NETWORK"},
    })
    out = snapshot.capture_connections(glue, job)
    assert [c["name"] for c in out] == ["c1", "c2"]
    # secret ARN preserved, no secret value present
    assert out[0]["definition"]["ConnectionProperties"]["SECRET_ID"].startswith("arn:aws:secretsmanager:")


def test_capture_connections_skips_failed_reads_best_effort():
    job = {"Name": "j", "Connections": {"Connections": ["ok", "gone"]}}
    glue = _FakeGlue({"ok": {"Name": "ok"}, "gone": RuntimeError("deleted")})
    out = snapshot.capture_connections(glue, job)
    assert [c["name"] for c in out] == ["ok"]  # failed read skipped, snapshot not blocked


def test_build_snapshot_includes_connections():
    snap = snapshot.build_snapshot("mig1", {"Name": "j"}, b"code", [], [{"name": "c1"}])
    assert snap["connections"] == [{"name": "c1"}]
    assert snap["snapshotVersion"] == 2


def test_build_snapshot_connections_default_empty():
    snap = snapshot.build_snapshot("mig1", {"Name": "j"}, b"code", [])
    assert snap["connections"] == []


# ---- DataZone bucket resolution ----

from migration.glue import datazone_resolve


class _FakeDataZone:
    def __init__(self, envs, env_details, default_env=None):
        self._envs = envs                # list of {id}
        self._env_details = env_details  # {env_id: detail dict}
        self._default_env = default_env or (envs[0]["id"] if envs else None)

    def list_connections(self, domainIdentifier, projectIdentifier, type):
        assert type == "IAM"
        return {"items": [{"connectionId": "iam1", "name": "project.iam"}]
                if self._default_env else []}

    def get_connection(self, domainIdentifier, identifier):
        assert identifier == "iam1"
        return {"environmentId": self._default_env}

    def get_environment(self, domainIdentifier, identifier):
        assert identifier == self._default_env
        return self._env_details[identifier]


def test_resolve_bucket_from_s3_uri_provisioned_resource():
    dz = _FakeDataZone(
        envs=[{"id": "env1"}],
        env_details={"env1": {"provisionedResources": [
            {"name": "s3BucketPath", "value": "s3://amazon-sagemaker-111-us-east-2-abc/shared"},
        ]}},
    )
    assert datazone_resolve.resolve_project_bucket(dz, "dzd-x", "proj") == "amazon-sagemaker-111-us-east-2-abc"


def test_resolve_bucket_from_bare_bucket_name():
    dz = _FakeDataZone(
        envs=[{"id": "env1"}],
        env_details={"env1": {"provisionedResources": [
            {"name": "bucket", "value": "amazon-sagemaker-111-us-east-2-abc"},
        ]}},
    )
    assert datazone_resolve.resolve_project_bucket(dz, "dzd-x", "proj") == "amazon-sagemaker-111-us-east-2-abc"


def test_resolve_bucket_uses_default_iam_environment_not_unrelated_environment():
    dz = _FakeDataZone(
        envs=[{"id": "env1"}, {"id": "env2"}],
        env_details={
            "env1": {"provisionedResources": [{"name": "s3", "value": "s3://unrelated-bucket/shared"}]},
            "env2": {"provisionedResources": [{"name": "s3", "value": "s3://amazon-sagemaker-999/shared"}]},
        },
        default_env="env2",
    )
    assert datazone_resolve.resolve_project_bucket(dz, "dzd-x", "proj") == "amazon-sagemaker-999"


def test_resolve_bucket_ignores_unreachable_unrelated_environment():
    dz = _FakeDataZone(
        envs=[{"id": "unreachable"}, {"id": "env2"}],
        env_details={"env2": {"provisionedResources": [
            {"name": "s3BucketPath", "value": "s3://amazon-sagemaker-999/shared"},
        ]}},
        default_env="env2",
    )
    assert datazone_resolve.resolve_project_bucket(dz, "dzd-x", "proj") == "amazon-sagemaker-999"


def test_resolve_bucket_raises_when_no_environments():
    dz = _FakeDataZone(envs=[], env_details={})
    try:
        datazone_resolve.resolve_project_bucket(dz, "dzd-x", "proj")
        assert False, "expected LookupError"
    except LookupError:
        pass


def test_resolve_bucket_raises_when_no_bucket_found():
    dz = _FakeDataZone(
        envs=[{"id": "env1"}],
        env_details={"env1": {"provisionedResources": [{"name": "x", "value": "not-a-bucket"}]}},
    )
    try:
        datazone_resolve.resolve_project_bucket(dz, "dzd-x", "proj")
        assert False, "expected LookupError"
    except LookupError:
        pass


@pytest.mark.parametrize("field,value", [
    ("ProfileName", "profile"), ("AutoUpgradeMetadata", {"TargetVersion": "5.0"}),
])
@pytest.mark.parametrize("operation", ["migrate", "rollback"])
def test_update_builders_accept_get_job_response_fields(field, value, operation):
    job = {**_base_job(), field: value}
    model = get_session().get_service_model("glue")
    validate_parameters(job, model.shape_for("Job"))
    update = (jobmove.build_job_update(job, "destbkt", "dzd-abc", "proj123")
              if operation == "migrate" else rollback.build_restore_update(job))
    validate_parameters(update, model.shape_for("JobUpdate"))
    assert field not in update
    assert update["Role"] == job["Role"]
