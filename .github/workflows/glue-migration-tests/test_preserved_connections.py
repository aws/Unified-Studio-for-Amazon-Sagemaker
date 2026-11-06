"""Job migration keeps dependencies usable without connection-read permissions."""
import copy
import io
import json

import boto3
import pytest
from botocore.exceptions import ClientError

from migration.glue import migrate, rollback

PREFIX = "AmazonDataZonePreMigrationConnection-"


SCRIPT = b'\xef\xbb\xbfconnection_options = {"connectionName": "legacy-db"}\r\n'
JOB = {
    "Name": "job",
    "Role": "arn:aws:iam::111122223333:role/legacy",
    "Command": {"Name": "glueetl", "ScriptLocation": "s3://source/job.py"},
    "DefaultArguments": {"--CONNECTION_NAME": "legacy-db"},
    "NonOverridableArguments": {"--OTHER_CONNECTION": "another-db"},
    "Connections": {"Connections": ["legacy-db", "another-db"]},
}


class Session:
    get_partition_for_region = staticmethod(boto3.Session().get_partition_for_region)
    region_name = "eu-north-1"

    def __init__(self, job=None, tags=None):
        self.job = copy.deepcopy(JOB if job is None else job)
        self.tags = tags or {}
        self.writes = []
        self.policies = {}

    def client(self, _service, **_kw):
        return self

    def list_connections(self, **_kw):
        return {"items": [{"name": "project.iam", "connectionId": "iam1"}]}

    def get_role_policy(self, RoleName, PolicyName):
        if (RoleName, PolicyName) not in self.policies:
            raise ClientError({"Error": {"Code": "NoSuchEntity"}}, "GetRolePolicy")
        return {"PolicyDocument": self.policies[RoleName, PolicyName]}

    def put_role_policy(self, RoleName, PolicyName, PolicyDocument):
        self.writes.append(("policy", {"RoleName": RoleName, "PolicyName": PolicyName}))
        self.policies[RoleName, PolicyName] = json.loads(PolicyDocument)

    def get_caller_identity(self):
        return {"Account": "111122223333"}

    def get_job(self, **_kw):
        return {"Job": self.job}

    def get_tags(self, **_kw):
        return {"Tags": self.tags}

    def get_triggers(self, **_kw):
        return {"Triggers": []}

    def get_connection(self, **_kw):
        if "domainIdentifier" in _kw:
            return {"environmentUserRole": "arn:aws:iam::111122223333:role/project/exec"}
        raise PermissionError("no access to original connections")

    def get_object(self, **_kw):
        return {"Body": io.BytesIO(SCRIPT)}

    def put_object(self, **kw):
        self.writes.append(("put", kw))

    def copy_object(self, **kw):
        self.writes.append(("copy", kw))

    def update_job(self, **kw):
        self.writes.append(("update", kw))

    def tag_resource(self, **kw):
        self.writes.append(("tag", kw))
        self.tags.update(kw["TagsToAdd"])

    def untag_resource(self, **kw):
        self.writes.append(("untag", kw))
        for key in kw["TagsToRemove"]:
            self.tags.pop(key, None)


def run(session, **kw):
    return migrate.migrate_job(session, job_name="job", domain_id="dzd-1", project_id="p1",
                               bucket="dest", **kw)


def test_migration_preserves_dependencies_and_tags_original_names_last():
    session = Session()
    result = run(session, apply=True)
    assert result["applied"]
    assert [op for op, _ in session.writes] == ["put", "policy", "copy", "update", "tag"]
    update = session.writes[3][1]["JobUpdate"]
    for field in ("Connections", "Role", "NonOverridableArguments"):
        assert update[field] == JOB[field]
    assert update["DefaultArguments"]["--CONNECTION_NAME"] == "legacy-db"
    tags = session.writes[-1][1]["TagsToAdd"]
    assert "AmazonDataZoneDomain" not in tags
    assert tags["AmazonDataZoneMigratedJob"] == "true"
    assert tags == {
        "AmazonDataZoneProject": "p1",
        "AmazonDataZoneMigratedJob": "true",
        PREFIX + "0": "legacy-db",
        PREFIX + "1": "another-db",
    }
    saved = json.loads(session.writes[0][1]["Body"])
    assert saved["connections"] == []  # denied GetConnection does not block migration


def test_dry_run_reports_tags_without_writing():
    session = Session()
    result = run(session)
    assert result["tagsToAdd"]["AmazonDataZoneMigratedJob"] == "true"
    assert result["tagsToAdd"][PREFIX + "0"] == "legacy-db"
    assert result["tagsToAdd"][PREFIX + "1"] == "another-db"
    assert session.writes == []


@pytest.mark.parametrize("apply", [False, True])
@pytest.mark.parametrize("tags", [
    {"AmazonDataZoneProject": "p1"},
    {"AmazonDataZoneProject": "p1", "AmazonDataZoneDomain": "another-domain"},
    {"AmazonDataZoneProject": "p1", "AmazonDataZoneMigratedJob": "false"},
])
def test_project_owned_job_only_repairs_passrole(apply, tags):
    job = copy.deepcopy(JOB)
    session = Session(job=job, tags=tags)
    result = run(session, apply=apply)
    assert result["alreadyMigrated"]
    assert result["skipped"]
    assert result["applied"] == apply
    assert [op for op, _ in session.writes] == (["policy"] if apply else [])


def test_project_owned_job_skips_without_resolving_bucket():
    session = Session(tags={"AmazonDataZoneProject": "p1"})
    result = migrate.migrate_job(
        session, job_name="job", domain_id="dzd-1", project_id="p1", apply=True)
    assert result["skipped"]
    assert [op for op, _ in session.writes] == ["policy"]


def test_migration_rejects_force_option():
    session = Session()
    with pytest.raises(TypeError, match="force"):
        run(session, apply=True, force=True)
    assert session.writes == []


def test_migration_keeps_original_names_even_after_user_removes_a_connection():
    job = copy.deepcopy(JOB)
    job["Connections"]["Connections"] = ["legacy-db"]
    original = {PREFIX + "0": "legacy-db", PREFIX + "1": "another-db"}
    session = Session(job=job, tags=original)
    result = run(session)
    assert {key: value for key, value in result["tagsToAdd"].items()
            if key.startswith(PREFIX)} == original


def test_obsolete_connection_marker_is_ignored():
    session = Session(tags={"AmazonDataZonePreMigrationConnections": "obsolete"})
    tags = run(session)["tagsToAdd"]
    assert tags[PREFIX + "0"] == "legacy-db"
    assert tags[PREFIX + "1"] == "another-db"
    assert "AmazonDataZonePreMigrationConnections" not in tags
    assert session.writes == []


@pytest.mark.parametrize("name", ["a,b", 'a"b', "a\tb", "cafe\u0301", "db😀"])
def test_unsupported_tag_characters_are_rejected_before_writes(name):
    job = {**JOB, "Connections": {"Connections": [name]}}
    session = Session(job=job)
    with pytest.raises(ValueError, match="characters unsupported by Glue tags"):
        run(session, apply=True)
    assert session.writes == []


def test_tag_safe_punctuation_and_unicode_separators_are_preserved():
    name = " legacy-db_1.:/=+-@\u00a0数据库 "
    job = {**JOB, "Connections": {"Connections": [name]}}
    assert run(Session(job=job))["tagsToAdd"][PREFIX + "0"] == name


def test_job_without_connections_needs_no_connection_tags():
    job = {k: v for k, v in JOB.items() if k != "Connections"}
    assert run(Session(job=job))["tagsToAdd"] == {
        "AmazonDataZoneProject": "p1", "AmazonDataZoneMigratedJob": "true",
    }


def test_tag_size_is_checked_before_any_write():
    job = {**JOB, "Connections": {"Connections": ["x" * 257]}}
    session = Session(job=job)
    with pytest.raises(ValueError, match="256"):
        run(session, apply=True)
    assert session.writes == []


@pytest.mark.parametrize("apply", [False, True])
def test_tag_capacity_is_checked_before_any_write(apply):
    session = Session(tags={f"user-{i}": "value" for i in range(47)})
    with pytest.raises(ValueError, match="50"):
        run(session, apply=apply)
    assert session.writes == []


@pytest.mark.parametrize("existing_tags, user_tag_count", [
    ({}, 46),
    ({PREFIX + "0": "original-db"}, 47),
    ({"AmazonDataZoneProject": "old-project", "AmazonDataZoneDomain": "old-domain"}, 45),
    ({
        PREFIX + "0": "original-db",
        "AmazonDataZoneProject": "old-project",
        "AmazonDataZoneDomain": "old-domain",
        "AmazonDataZoneMigratedJob": "false",
    }, 46),
])
@pytest.mark.parametrize("system_tags", [{}, {"aws:createdBy": "system", "aws:owner": "system"}])
def test_exact_tag_capacity_counts_overwrites_and_excludes_system_tags(
        existing_tags, user_tag_count, system_tags):
    tags = {f"user-{i}": "value" for i in range(user_tag_count)}
    tags.update(existing_tags)
    tags.update(system_tags)
    session = Session(tags=tags)
    result = run(session, apply=True)
    assert result["applied"]
    assert [op for op, _ in session.writes] == ["put", "policy", "copy", "update", "tag"]
    added = session.writes[-1][1]["TagsToAdd"]
    assert added["AmazonDataZoneProject"] == "p1"
    assert added["AmazonDataZoneMigratedJob"] == "true"
    assert len({key for key in tags | added if not key.startswith("aws:")}) == 50


@pytest.mark.parametrize("name", ["x" * 255, "é" * 255, "数据库" * 85])
def test_maximum_connection_name_fits_in_tag(name):
    job = {**JOB, "Connections": {"Connections": [name]}}
    assert run(Session(job=job))["tagsToAdd"][PREFIX + "0"] == name


@pytest.mark.parametrize("count", [48, 49])
def test_connection_count_is_limited_by_tag_capacity(count):
    job = {**JOB, "Connections": {"Connections": [f"connection-{i}" for i in range(count)]}}
    session = Session(job=job)
    if count == 48:
        assert len(run(session, apply=True)["tagsToAdd"]) == 50
    else:
        with pytest.raises(ValueError, match="50"):
            run(session, apply=True)
        assert session.writes == []


def test_unicode_names_round_trip():
    job = {**JOB, "Connections": {"Connections": ["café", "数据库"]}}
    tags = run(Session(job=job))["tagsToAdd"]
    assert tags[PREFIX + "0"] == "café"
    assert tags[PREFIX + "1"] == "数据库"


def test_job_rollback_removes_connection_tags_recorded_in_snapshot():
    session = Session(tags={
        "AmazonDataZoneProject": "p1",
        "AmazonDataZoneMigratedJob": "true",
        PREFIX + "0": "legacy-db",
        PREFIX + "1": "another-db",
        "owner": "team",
    })
    saved = {"job": JOB, "priorJobTags": {
        "AmazonDataZoneProject": None,
        "AmazonDataZoneMigratedJob": None,
        PREFIX + "0": None,
        PREFIX + "1": None,
    }}
    result = rollback.rollback_from_snapshot(session, saved, apply=True)
    assert "AmazonDataZoneMigratedJob" in result["tagsRemoved"]
    assert {PREFIX + "0", PREFIX + "1"} <= set(result["tagsRemoved"])
    assert session.writes[-1][0] == "untag"
    assert {PREFIX + "0", PREFIX + "1"} <= set(session.writes[-1][1]["TagsToRemove"])
    assert "AmazonDataZoneMigratedJob" in session.writes[-1][1]["TagsToRemove"]
    assert session.tags == {"owner": "team"}


@pytest.mark.parametrize("original_tags", [
    {},
    {
        "AmazonDataZoneProject": "original-project",
        "AmazonDataZoneDomain": "original-domain",
        "AmazonDataZoneMigratedJob": "false",
        PREFIX + "0": "original-db",
    },
    {PREFIX + "0": "original-db", PREFIX + "1": "removed-db"},
    {"AmazonDataZoneDomain": "", "owner": "team"},
])
def test_migration_rollback_restores_original_job_tags(original_tags):
    session = Session(tags=dict(original_tags))
    run(session, apply=True)
    saved = json.loads(session.writes[0][1]["Body"])
    rollback.rollback_from_snapshot(session, saved, apply=True)
    assert session.tags == original_tags


@pytest.mark.parametrize("apply", [False, True])
def test_job_rollback_preserves_domain_when_not_recorded_as_changed(apply):
    current_tags = {
        "AmazonDataZoneDomain": "untouched-domain",
        "AmazonDataZoneProject": "p1",
        PREFIX + "0": "legacy-db",
    }
    session = Session(tags=dict(current_tags))
    saved = {
        "job": JOB,
        "priorJobTags": {"AmazonDataZoneProject": None, PREFIX + "0": None},
    }
    result = rollback.rollback_from_snapshot(session, saved, apply=apply)
    assert set(result["tagsRemoved"]) == {"AmazonDataZoneProject", PREFIX + "0"}
    if apply:
        assert session.tags == {"AmazonDataZoneDomain": "untouched-domain"}
    else:
        assert session.tags == current_tags
        assert session.writes == []


@pytest.mark.parametrize("apply", [False, True])
def test_rollback_without_tag_history_fails_before_writes(apply):
    session = Session(tags={"AmazonDataZoneDomain": "original", PREFIX + "0": "db"})
    with pytest.raises(KeyError, match="priorJobTags"):
        rollback.rollback_from_snapshot(session, {"job": JOB}, apply=apply)
    assert session.writes == []


@pytest.mark.parametrize("region,partition", [
    ("eu-north-1", "aws"), ("cn-north-1", "aws-cn"), ("us-gov-west-1", "aws-us-gov"),
])
def test_migration_and_rollback_use_sdk_partition(region, partition):
    session = Session()
    session.region_name = region
    assert migrate._job_arn(session, "job") == f"arn:{partition}:glue:{region}:111122223333:job/job"
    run(session, apply=True)
    saved = json.loads(session.writes[0][1]["Body"])
    rollback.rollback_from_snapshot(session, saved, apply=True)
    for operation, request in session.writes:
        if operation in ("tag", "untag"):
            assert request["ResourceArn"] == f"arn:{partition}:glue:{region}:111122223333:job/job"


def test_live_test_fallback_cleanup_restores_without_apply_output():
    from e2e.test_connection_migration_e2e import _migration_tags

    retained = {"owner": "team", "AmazonDataZoneDomain": "original-domain"}
    session = Session(tags={**retained, "AmazonDataZoneProject": "p1",
                            "AmazonDataZoneMigratedJob": "true", PREFIX + "0": "db"})
    saved = {"job": JOB, "priorJobTags": dict.fromkeys(_migration_tags(session.tags))}
    result = rollback.rollback_from_snapshot(session, saved, apply=True)
    assert result["applied"]
    assert session.writes[0][1]["JobUpdate"]["Command"] == JOB["Command"]
    assert session.tags == retained
    assert not _migration_tags(session.tags)
