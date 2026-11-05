"""Exercise project PassRole grants through the job migration entry point."""
import copy
import json

import pytest
from botocore.exceptions import ClientError

from test_preserved_connections import JOB, Session, run
from migration.glue import cli


def test_dry_run_previews_exact_role_and_service_without_writes():
    session = Session()
    plan = run(session)["passRole"]
    assert plan["projectRoleArn"] == "arn:aws:iam::111122223333:role/project/exec"
    assert plan["policyDocument"] == {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow", "Action": "iam:PassRole",
            "Resource": "arn:aws:iam::111122223333:role/legacy",
            "Condition": {"StringEquals": {"iam:PassedToService": "glue.amazonaws.com"}},
        }],
    }
    assert plan["needsUpdate"]
    assert session.writes == []


def test_apply_preserves_other_policies_and_retries_without_policy_writes():
    session = Session()
    unrelated = {"Version": "2012-10-17", "Statement": []}
    session.policies["exec", "existing"] = unrelated
    first = run(session, apply=True)
    assert session.policies["exec", "existing"] == unrelated
    assert session.policies["exec", first["passRole"]["policyName"]] == first["passRole"]["policyDocument"]
    session.writes.clear()
    retry = run(session, apply=True)
    assert not retry["passRole"]["needsUpdate"]
    assert not retry["applied"]
    assert session.writes == []


def test_migrating_another_role_keeps_first_grant():
    session = Session()
    run(session, apply=True)
    first = copy.deepcopy(session.policies)
    session.job["Role"] = "arn:aws:iam::111122223333:role/another"
    run(session, apply=True)
    assert len(session.policies) == 2
    assert first.items() <= session.policies.items()


def test_bare_job_role_is_resolved_with_its_iam_path():
    session = Session(job={**JOB, "Role": "legacy"})

    def get_role(RoleName):
        assert RoleName == "legacy"
        return {"Role": {"Arn": "arn:aws:iam::111122223333:role/service-role/legacy"}}

    session.get_role = get_role
    plan = run(session)["passRole"]
    assert plan["policyDocument"]["Statement"][0]["Resource"].endswith("/service-role/legacy")


@pytest.mark.parametrize("role", [
    "arn:aws:iam::999999999999:role/other-account",
    "arn:aws:iam::111122223333:role/*",
])
def test_invalid_job_role_cannot_grant_broader_access(role):
    session = Session(job={**JOB, "Role": role})
    with pytest.raises(ValueError):
        run(session, apply=True)
    assert session.writes == []


def test_missing_project_role_fails_before_any_write():
    session = Session()
    session.list_connections = lambda **kw: {"items": []}
    with pytest.raises(LookupError):
        run(session, apply=True)
    assert session.writes == []


def test_conflicting_policy_is_not_overwritten():
    session = Session()
    policy_name = run(session)["passRole"]["policyName"]
    conflicting = {"Version": "2012-10-17", "Statement": []}
    session.policies["exec", policy_name] = conflicting
    with pytest.raises(ValueError, match="policy"):
        run(session, apply=True)
    assert session.policies["exec", policy_name] == conflicting
    assert session.writes == []


@pytest.mark.parametrize("operation", ["get_role_policy", "put_role_policy"])
def test_iam_denial_prevents_job_changes(operation):
    session = Session()

    def denied(**kw):
        raise ClientError({"Error": {"Code": "AccessDenied"}}, operation)

    setattr(session, operation, denied)
    with pytest.raises(ClientError, match="AccessDenied"):
        run(session, apply=True)
    assert all(op == "put" for op, _ in session.writes)  # snapshot may already exist


def test_cli_previews_repairs_and_then_skips_existing_job(monkeypatch, capsys):
    session = Session(tags={"AmazonDataZoneProject": "p1"})
    monkeypatch.setattr(cli.session_mod, "build_session", lambda **kw: session)
    args = ["--job-name", "job", "--domain-id", "dzd-1", "--project-id", "p1"]
    for flags, heading, changed in [
        ([], "DRY-RUN", False), (["--apply"], "APPLIED", True),
        (["--apply"], "SKIPPED", False),
    ]:
        assert cli.main(args + flags) == 0
        banner, body = capsys.readouterr().out.split("\n", 1)
        assert heading in banner
        assert json.loads(body)["applied"] == changed
    assert [op for op, _ in session.writes] == ["policy"]
