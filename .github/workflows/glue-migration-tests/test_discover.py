"""Tests for discover: role resolution, matcher buckets, normalization, paginated I/O.

Pure-logic tests call plan_discovery directly; I/O tests use botocore Stubber so
DataZone/Glue request shapes are validated against the service model.
"""
import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from migration.glue import discover, discover_cli

ACCT = "111122223333"
ROLE_A = f"arn:aws:iam::{ACCT}:role/service-role/AmazonSageMakerAdminIAMExecutionRole_4"
ROLE_B = f"arn:aws:iam::{ACCT}:role/service-role/AmazonSageMakerAdminIAMExecutionRole_8"
SCRIPT = {"Command": {"Name": "glueetl", "ScriptLocation": "s3://source/job.py"}}
PROJECT_ROLE = f"arn:aws:iam::{ACCT}:role/datazone_usr_role_abc_def"


def _pr(domain, project, role, name=None):
    return discover.ProjectRole(domain, project, name or project, role)


# ---- normalize_role_arn ----

def test_normalize_passes_through_full_arn():
    assert discover.normalize_role_arn(ROLE_A, ACCT) == ROLE_A


def test_normalize_bare_name_to_arn():
    assert discover.normalize_role_arn("MyRole", ACCT) == f"arn:aws:iam::{ACCT}:role/MyRole"


def test_normalize_bare_name_with_path():
    assert discover.normalize_role_arn("service-role/Foo", ACCT) == \
        f"arn:aws:iam::{ACCT}:role/service-role/Foo"


def test_normalize_respects_partition():
    assert discover.normalize_role_arn("MyRole", ACCT, partition="aws-cn") == \
        f"arn:aws-cn:iam::{ACCT}:role/MyRole"


# ---- build_role_index ----

def test_role_index_groups_projects_by_role():
    prs = [_pr("d1", "p1", ROLE_A), _pr("d1", "p2", ROLE_B), _pr("d2", "p3", ROLE_A)]
    index = discover.build_role_index(prs)
    assert {r.project_id for r in index[ROLE_A]} == {"p1", "p3"}
    assert [r.project_id for r in index[ROLE_B]] == ["p2"]


# ---- plan_discovery (the matcher) ----

def test_unique_match_is_migrated():
    prs = [_pr("d1", "p1", ROLE_A, name="Proj One")]
    jobs = [{**SCRIPT, "Name": "job1", "Role": ROLE_A}]
    plan = discover.plan_discovery(prs, jobs, account=ACCT)
    assert len(plan.matched) == 1
    m = plan.matched[0]
    assert (m.job_name, m.domain_id, m.project_id, m.project_name) == ("job1", "d1", "p1", "Proj One")
    assert plan.unmatched == [] and plan.ambiguous == []


def test_bare_name_role_matches_after_normalization():
    prs = [_pr("d1", "p1", f"arn:aws:iam::{ACCT}:role/ExecRole")]
    jobs = [{**SCRIPT, "Name": "job1", "Role": "ExecRole"}]
    plan = discover.plan_discovery(prs, jobs, account=ACCT)
    assert len(plan.matched) == 1 and plan.matched[0].project_id == "p1"


def test_no_match_is_unmatched_not_migrated():
    prs = [_pr("d1", "p1", ROLE_A)]
    jobs = [{**SCRIPT, "Name": "lonely", "Role": ROLE_B}]
    plan = discover.plan_discovery(prs, jobs, account=ACCT)
    assert plan.matched == []
    assert plan.unmatched == [{"jobName": "lonely", "jobRoleArn": ROLE_B}]


def test_multiple_projects_is_ambiguous_and_skipped():
    prs = [_pr("d1", "p1", ROLE_A), _pr("d2", "p2", ROLE_A)]
    jobs = [{**SCRIPT, "Name": "shared", "Role": ROLE_A}]
    plan = discover.plan_discovery(prs, jobs, account=ACCT)
    assert plan.matched == []
    assert len(plan.ambiguous) == 1
    a = plan.ambiguous[0]
    assert a.job_name == "shared"
    assert set(a.projects) == {("d1", "p1"), ("d2", "p2")}


def test_job_without_role_is_unmatched():
    plan = discover.plan_discovery([_pr("d1", "p1", ROLE_A)], [{**SCRIPT, "Name": "noRole"}], account=ACCT)
    assert plan.unmatched == [{"jobName": "noRole", "jobRoleArn": None}]


def test_to_json_round_trips_all_buckets():
    prs = [_pr("d1", "p1", ROLE_A, name="One"), _pr("d2", "p2", ROLE_B, name="Two"),
           _pr("d3", "p3", ROLE_B, name="Three")]
    jobs = [{**SCRIPT, "Name": "match", "Role": ROLE_A},        # unique -> matched
            {**SCRIPT, "Name": "amb", "Role": ROLE_B},          # p2 + p3 -> ambiguous
            {**SCRIPT, "Name": "none", "Role": f"arn:aws:iam::{ACCT}:role/other"}]  # unmatched
    plan = discover.plan_discovery(prs, jobs, account=ACCT)
    j = plan.to_json()
    assert len(j["projectRoles"]) == 3
    assert [m["jobName"] for m in j["matched"]] == ["match"]
    assert [a["jobName"] for a in j["ambiguous"]] == ["amb"]
    assert [u["jobName"] for u in j["unmatched"]] == ["none"]


# ---- paginated I/O via Stubber ----

@pytest.fixture
def dz():
    s = boto3.Session(aws_access_key_id="x", aws_secret_access_key="x", region_name="us-east-2")
    c = s.client("datazone")
    st = Stubber(c)
    st.activate()
    yield c, st
    st.assert_no_pending_responses()


@pytest.fixture
def glue():
    s = boto3.Session(aws_access_key_id="x", aws_secret_access_key="x", region_name="us-east-2")
    c = s.client("glue")
    st = Stubber(c)
    st.activate()
    yield c, st
    st.assert_no_pending_responses()


def _domain(did, status="AVAILABLE"):
    return {"id": did, "name": did, "arn": f"arn:aws:datazone:us-east-2:{ACCT}:domain/{did}",
            "managedAccountId": ACCT, "status": status, "createdAt": "2024-01-01T00:00:00Z"}


def _iam_item(name="project.iam", domain="d1", project="p1", cid="c1"):
    return {"connectionId": cid, "domainId": domain, "domainUnitId": "u1",
            "projectId": project, "environmentId": "e1", "name": name,
            "physicalEndpoints": [], "type": "IAM"}


def _stub_role(st, domain="d1", project="p1", role=PROJECT_ROLE):
    item = _iam_item(domain=domain, project=project)
    st.add_response("list_connections", {"items": [item]},
                    {"domainIdentifier": domain, "projectIdentifier": project, "type": "IAM"})
    st.add_response("get_connection", {**item, "environmentUserRole": role},
                    {"domainIdentifier": domain, "identifier": "c1"})


def _project(pid, domain="d1"):
    return {"domainId": domain, "id": pid, "name": pid.upper(), "createdBy": "u"}


def test_list_account_domains_paginates_and_filters_status(dz):
    c, st = dz
    st.add_response("list_domains", {"items": [_domain("d1")], "nextToken": "t"}, {})
    st.add_response("list_domains",
                    {"items": [_domain("d2"), _domain("d3", status="DELETED")]}, {"nextToken": "t"})
    domains = discover.list_account_domains(c)
    assert [d["id"] for d in domains] == ["d1", "d2"]  # DELETED dropped


def test_list_domain_projects_paginates(dz):
    c, st = dz
    item = lambda pid: {"domainId": "d1", "id": pid, "name": pid, "createdBy": "u"}
    st.add_response("list_projects", {"items": [item("p1")], "nextToken": "t"},
                    {"domainIdentifier": "d1"})
    st.add_response("list_projects", {"items": [item("p2")]},
                    {"domainIdentifier": "d1", "nextToken": "t"})
    projects = discover.list_domain_projects(c, "d1")
    assert [p["id"] for p in projects] == ["p1", "p2"]


@pytest.mark.parametrize("name", ["project.iam", "default.iam"])
def test_resolve_project_role_uses_default_iam_without_reading_environments(dz, name):
    c, st = dz
    item = _iam_item(name=name)
    st.add_response("list_connections", {"items": [_iam_item(name="unrelated.iam", cid="c2"), item]},
                    {"domainIdentifier": "d1", "projectIdentifier": "p1", "type": "IAM"})
    st.add_response("get_connection", {**item, "environmentUserRole": PROJECT_ROLE},
                    {"domainIdentifier": "d1", "identifier": "c1"})
    # Any old broad environment lookup would make an unexpected AWS request.
    assert discover.resolve_project_role(c, "d1", "p1") == PROJECT_ROLE


def test_resolve_project_role_finds_default_iam_on_later_page(dz):
    c, st = dz
    st.add_response("list_connections", {"items": [_iam_item(name="custom.iam")], "nextToken": "t"},
                    {"domainIdentifier": "d1", "projectIdentifier": "p1", "type": "IAM"})
    item = _iam_item(name="default.iam")
    st.add_response("list_connections", {"items": [item]},
                    {"domainIdentifier": "d1", "projectIdentifier": "p1",
                     "type": "IAM", "nextToken": "t"})
    st.add_response("get_connection", {**item, "environmentUserRole": ROLE_A},
                    {"domainIdentifier": "d1", "identifier": "c1"})
    assert discover.resolve_project_role(c, "d1", "p1") == ROLE_A


def test_resolve_project_role_none_when_only_unrelated_iam_exists(dz):
    c, st = dz
    st.add_response("list_connections", {"items": [_iam_item(name="custom.iam")]},
                    {"domainIdentifier": "d1", "projectIdentifier": "p1", "type": "IAM"})
    assert discover.resolve_project_role(c, "d1", "p1") is None


@pytest.mark.parametrize("role", [None, "", f"arn:aws:iam::{ACCT}:user/someone", "some-role"])
def test_resolve_project_role_rejects_missing_or_invalid_role(dz, role):
    c, st = dz
    item = _iam_item()
    st.add_response("list_connections", {"items": [item]},
                    {"domainIdentifier": "d1", "projectIdentifier": "p1", "type": "IAM"})
    detail = {**item, **({"environmentUserRole": role} if role is not None else {})}
    st.add_response("get_connection", detail, {"domainIdentifier": "d1", "identifier": "c1"})
    assert discover.resolve_project_role(c, "d1", "p1") is None


def test_list_glue_jobs_paginates(glue):
    c, st = glue
    st.add_response("get_jobs", {"Jobs": [{**SCRIPT, "Name": "j1", "Role": ROLE_A}], "NextToken": "t"}, {})
    st.add_response("get_jobs", {"Jobs": [{**SCRIPT, "Name": "j2", "Role": ROLE_B}]}, {"NextToken": "t"})
    jobs = discover.list_glue_jobs(c)
    assert [j["Name"] for j in jobs] == ["j1", "j2"]


def test_collect_project_roles_end_to_end(dz):
    c, st = dz
    st.add_response("list_domains", {"items": [_domain("d1")]}, {})
    st.add_response("list_projects",
                    {"items": [{"domainId": "d1", "id": "p1", "name": "P1", "createdBy": "u"},
                               {"domainId": "d1", "id": "p2", "name": "P2", "createdBy": "u"}]},
                    {"domainIdentifier": "d1"})
    _stub_role(st)
    st.add_response("list_connections", {"items": []},
                    {"domainIdentifier": "d1", "projectIdentifier": "p2", "type": "IAM"})
    roles, without = discover.collect_project_roles(c)
    assert [r.project_id for r in roles] == ["p1"]
    assert roles[0].role_arn == PROJECT_ROLE
    assert without == [{"domainId": "d1", "projectId": "p2", "projectName": "P2"}]


@pytest.mark.parametrize("operation", ["list_projects", "list_connections", "get_connection"])
@pytest.mark.parametrize("code", ["AccessDeniedException", "AccessDenied", "UnauthorizedException"])
def test_collect_excludes_denied_domain_and_continues(dz, caplog, operation, code):
    c, st = dz
    st.add_response("list_domains", {"items": [_domain("d1"), _domain("d2")]}, {})
    if operation == "list_projects":
        st.add_response("list_projects", {"items": [_project("p1")], "nextToken": "t"},
                        {"domainIdentifier": "d1"})
        params = {"domainIdentifier": "d1", "nextToken": "t"}
    else:
        st.add_response("list_projects", {"items": [_project(p) for p in ("p1", "p2", "p3")]},
                        {"domainIdentifier": "d1"})
        _stub_role(st)
        st.add_response("list_connections", {"items": []},
                        {"domainIdentifier": "d1", "projectIdentifier": "p2", "type": "IAM"})
        params = {"domainIdentifier": "d1", "projectIdentifier": "p3", "type": "IAM"}
        if operation == "get_connection":
            st.add_response("list_connections", {"items": [_iam_item(project="p3")]}, params)
            params = {"domainIdentifier": "d1", "identifier": "c1"}
    st.add_client_error(operation, service_error_code=code, http_status_code=403,
                        expected_params=params)
    st.add_response("list_projects", {"items": [_project("p4", "d2")]},
                    {"domainIdentifier": "d2"})
    _stub_role(st, domain="d2", project="p4", role=ROLE_B)
    roles, without = discover.collect_project_roles(c)
    assert roles == [_pr("d2", "p4", ROLE_B, name="P4")]
    assert without == []
    assert "d1" in caplog.text and code in caplog.text


def test_collect_no_domains_when_domain_listing_is_denied(dz, caplog):
    c, st = dz
    st.add_client_error("list_domains", service_error_code="AccessDeniedException",
                        http_status_code=403, expected_params={})
    assert discover.collect_project_roles(c) == ([], [])
    assert "AccessDeniedException" in caplog.text


@pytest.mark.parametrize("code", ["ThrottlingException", "ResourceNotFoundException"])
def test_collect_does_not_hide_non_permission_errors(dz, code):
    c, st = dz
    st.add_response("list_domains", {"items": [_domain("d1")]}, {})
    st.add_client_error("list_projects", service_error_code=code, expected_params={"domainIdentifier": "d1"})
    with pytest.raises(ClientError) as error:
        discover.collect_project_roles(c)
    assert error.value.response["Error"]["Code"] == code


@pytest.mark.parametrize("apply", [False, True])
def test_cli_only_plans_and_applies_accessible_domains(dz, glue, monkeypatch, capsys, apply):
    c, st = dz
    gc, gst = glue
    st.add_response("list_domains", {"items": [_domain("d1"), _domain("d2")]}, {})
    st.add_client_error("list_projects", service_error_code="AccessDeniedException",
                        http_status_code=403, expected_params={"domainIdentifier": "d1"})
    st.add_response("list_projects", {"items": [_project("p4", "d2")]},
                    {"domainIdentifier": "d2"})
    _stub_role(st, domain="d2", project="p4", role=ROLE_B)
    gst.add_response("get_jobs", {"Jobs": [{**SCRIPT, "Name": "accessible", "Role": ROLE_B},
                                          {**SCRIPT, "Name": "denied", "Role": ROLE_A},
                                          {"Name": "stream", "Role": ROLE_B, "Command": {
                                              "Name": "gluestreaming", "ScriptLocation": "s3://source/job.py"}}]}, {})
    class Session(boto3.Session):
        def client(self, service):
            if service == "glue":
                return gc
            class Sts:
                def get_caller_identity(self):
                    return {"Account": ACCT}
            return Sts()
    monkeypatch.setattr(discover_cli.session_mod, "build_session", lambda **kw: Session())
    monkeypatch.setattr(discover_cli.session_mod, "datazone_client", lambda *a: c)
    migrations = []
    def migrate_job(session, **kw):
        migrations.append((kw["job_name"], kw["domain_id"], kw["project_id"]))
        return {"applied": True}
    monkeypatch.setattr(discover_cli.migrate, "migrate_job", migrate_job)
    assert discover_cli.main(["--apply"] if apply else []) == 0
    assert migrations == ([("accessible", "d2", "p4")] if apply else [])
    output = capsys.readouterr().out
    assert '"domainId": "d1"' not in output
    assert '"domainId": "d2"' in output


@pytest.mark.parametrize("job_type", [
    {"Command": {"Name": "gluestreaming", "ScriptLocation": "s3://source/job.py"}},
    {"Command": {"Name": "glueray", "ScriptLocation": "s3://source/job.py"}},
    {"Command": {"Name": "unknown", "ScriptLocation": "s3://source/job.py"}},
    {"Command": {}},
    {"Command": {"Name": "glueetl", "ScriptLocation": None}},
    {"Command": {"Name": "glueetl", "ScriptLocation": "s3://source/job.scala"}},
    {"CodeGenConfigurationNodes": {"node": {}}},
    {"JobMode": "VISUAL"},
    {"JobMode": "NOTEBOOK"},
    {"DefaultArguments": {"--job-language": "scala"}},
    {"NonOverridableArguments": {"--job-language": "scala"}},
])
def test_discovery_skips_unsupported_jobs_even_when_role_matches(job_type):
    job = {**SCRIPT, "Name": "unsupported", "Role": ROLE_A, **job_type}
    plan = discover.plan_discovery([_pr("d1", "p1", ROLE_A)], [job], account=ACCT)
    assert plan.matched == []
    assert plan.to_json()["unsupported"] == ["unsupported"]


@pytest.mark.parametrize("command", ["glueetl", "pythonshell"])
def test_discovery_accepts_python_script_jobs(command):
    job = {"Name": "python", "Role": ROLE_A, "JobMode": "SCRIPT",
           "Command": {"Name": command, "ScriptLocation": "s3://source/job.py"}}
    plan = discover.plan_discovery([_pr("d1", "p1", ROLE_A)], [job], account=ACCT)
    assert [m.job_name for m in plan.matched] == ["python"]
