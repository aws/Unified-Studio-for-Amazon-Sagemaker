"""Offline tests for connmigrate orchestration: real botocore clients + Stubber.

Stubber validates every request against the service model, so parameter names
and shapes sent to Glue / Secrets Manager / DataZone are checked, not mocked.
"""
from unittest.mock import Mock

import boto3
import pytest
from botocore.stub import ANY, Stubber

from migration.glue import connmigrate, naming

D, P, ENV = "dzd-1", "proj1", "env1"
ROLE = "arn:aws:iam::111122223333:role/service-role/project-user-role"
SECRET = "arn:aws:secretsmanager:us-east-2:111122223333:secret:db-AbCdEf"
SRC = "orders-db"
DZ_NAME = naming.datazone_connection_name(SRC, project_id=P)
SOURCE = {"Name": SRC, "ConnectionType": "MYSQL", "ConnectionSchemaVersion": 2,
          "ConnectionProperties": {"HOST": "h", "PORT": "3306", "DATABASE": "d", "ROLE_ARN": "arn:aws:iam::1:role/src"},
          "AuthenticationConfiguration": {"AuthenticationType": "BASIC", "SecretArn": SECRET}}


@pytest.fixture
def clients():
    s = boto3.Session(aws_access_key_id="x", aws_secret_access_key="x", region_name="us-east-2")
    c = {k: s.client(k) for k in ("glue", "secretsmanager", "datazone")}
    stubs = {k: Stubber(v) for k, v in c.items()}
    for st in stubs.values():
        st.activate()
    yield c, stubs
    for st in stubs.values():
        st.assert_no_pending_responses()


def _common(stubs, existing=(), tags=(), status="READY"):
    dz, glue, sm = stubs["datazone"], stubs["glue"], stubs["secretsmanager"]
    dz.add_response("list_connections", {"items": [_summary(n, i) for n, i, _ in existing]},
                    {"domainIdentifier": D, "projectIdentifier": P})
    dz.add_response("list_environments", {"items": [_env_summary()]}, {"domainIdentifier": D, "projectIdentifier": P})
    dz.add_response("get_environment", _env(), {"domainIdentifier": D, "identifier": ENV})
    glue.add_response("get_connection", {"Connection": SOURCE}, {"Name": SRC, "HidePassword": True})
    for n, i, desc in existing:
        if desc is None:
            dz.add_client_error("get_connection", "ResourceNotFoundException", "deleted",
                                expected_params={"domainIdentifier": D, "identifier": i})
        else:
            dz.add_response("get_connection", _conn(i, n, status, desc), {"domainIdentifier": D, "identifier": i})
    if tags is not None:
        sm.add_response("describe_secret", {"ARN": SECRET, "Tags": list(tags)}, {"SecretId": SECRET})


def _glue_free(stubs, *names):
    """Glue has no connection by these names (the clone would be named after them)."""
    for n in names:
        stubs["glue"].add_client_error("get_connection", "EntityNotFoundException", "not found",
                                       expected_params={"Name": n, "HidePassword": True})


def _env_summary():
    return {"id": ENV, "domainId": D, "projectId": P, "name": "tooling", "provider": "Amazon SageMaker",
            "createdBy": "u"}


def _env():
    return {**_env_summary(), "provisionedResources": [{"name": "userRoleArn", "value": ROLE, "type": "IAMRole"}]}


def _summary(name, cid):
    return {"connectionId": cid, "domainId": D, "domainUnitId": "du", "name": name, "type": "MYSQL",
            "physicalEndpoints": []}


def _conn(cid, name, status, desc="", err=None):
    gp = {"status": status, **({"errorMessage": err} if err else {})}
    return {"connectionId": cid, "domainId": D, "domainUnitId": "du", "name": name, "type": "MYSQL",
            "description": desc, "props": {"glueProperties": gp},
            "physicalEndpoints": [{"glueConnectionName": name}]}


def _run(c, **kw):
    return connmigrate.migrate_connection(glue=c["glue"], sm=c["secretsmanager"], dz=c["datazone"],
                                          domain_id=D, project_id=P, name=SRC, poll=0, **kw)


@pytest.mark.parametrize("tags", [[], [{"Key": "AmazonDataZoneProject", "Value": "other-project"}]])
def test_creates_clone_with_project_role_after_tagging(clients, tags):
    c, stubs = clients
    _common(stubs, tags=tags)
    _glue_free(stubs, DZ_NAME)
    stubs["secretsmanager"].add_response("tag_resource", {}, {"SecretId": SECRET, "Tags": [
        {"Key": "for-use-with-all-datazone-projects", "Value": "true"}]})
    stubs["datazone"].add_response("create_connection", _conn("c1", DZ_NAME, "CREATING"), {
        "domainIdentifier": D, "environmentIdentifier": ENV, "name": DZ_NAME, "clientToken": ANY,
        "description": naming.source_marker(SRC) + f" Migrated from Glue connection {SRC}",
        # Without an explicit GLUE_CONNECTION mode DataZone also provisions an Athena catalog.
        "configurations": [{"classification": "ProvisioningConfiguration",
                            "properties": {"PROVISIONING_MODE": "GLUE_CONNECTION"}}],
        "props": {"glueProperties": {"glueConnectionInput": {
            "name": DZ_NAME, "connectionType": "MYSQL", "validateCredentials": False,
            "connectionProperties": {"HOST": "h", "PORT": "3306", "DATABASE": "d", "ROLE_ARN": ROLE},
            "authenticationConfiguration": {"authenticationType": "BASIC", "secretArn": SECRET}}}}})
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "CREATING"), {"domainIdentifier": D, "identifier": "c1"})
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "READY"), {"domainIdentifier": D, "identifier": "c1"})

    m = _run(c)
    assert (m.datazone_id, m.datazone_name, m.glue_name, m.reused) == ("c1", DZ_NAME, DZ_NAME, False)
    assert m.tag_change.prior == {"for-use-with-all-datazone-projects": None}


def test_reuses_owned_clone_without_creating_another(clients):
    c, stubs = clients
    _common(stubs, existing=[(DZ_NAME, "c1", naming.source_marker(SRC))], tags=[
        {"Key": "AmazonDataZoneProject", "Value": P},
        {"Key": "AmazonDataZoneDomain", "Value": D}])

    m = _run(c)

    assert (m.datazone_id, m.datazone_name, m.glue_name, m.reused) == ("c1", DZ_NAME, DZ_NAME, True)
    assert m.tag_change.prior == {}


@pytest.mark.parametrize("description", ["manual connection", naming.source_marker("other"), None])
def test_datazone_name_collision_fails_before_changing_secret_tags(clients, description):
    c, stubs = clients
    _common(stubs, existing=[(DZ_NAME, "foreign", description)], tags=None)
    if description is None:
        stubs["glue"].add_response("get_connection", {"Connection": {**SOURCE, "Name": DZ_NAME}},
                                  {"Name": DZ_NAME, "HidePassword": True})

    with pytest.raises(naming.ConnectionNameConflict) as exc:
        _run(c, shared_secret=True)

    assert DZ_NAME in str(exc.value)


def test_glue_name_collision_fails_before_changing_secret_tags(clients):
    c, stubs = clients
    _common(stubs, tags=None)
    stubs["glue"].add_response("get_connection", {"Connection": {**SOURCE, "Name": DZ_NAME}},
                               {"Name": DZ_NAME, "HidePassword": True})

    with pytest.raises(naming.ConnectionNameConflict) as exc:
        _run(c, shared_secret=True)

    assert DZ_NAME in str(exc.value)


def _tag_shared(stubs):
    stubs["secretsmanager"].add_response("tag_resource", {}, {"SecretId": SECRET, "Tags": [
        {"Key": "for-use-with-all-datazone-projects", "Value": "true"}]})


@pytest.mark.parametrize("status", ["READY", "CREATING", "UPDATE_FAILED", "DELETE_FAILED", "CREATE_FAILED"])
def test_lost_create_response_recovers_same_request_and_cleans_only_failed_clone(clients, monkeypatch, status):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    for _ in range(2):
        stubs["datazone"].add_response("create_connection", _conn("c1", DZ_NAME, "CREATING"))
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, status),
                                  {"domainIdentifier": D, "identifier": "c1"})
    if status == "CREATE_FAILED":
        stubs["datazone"].add_response("delete_connection", {"status": "DELETING"},
                                      {"domainIdentifier": D, "identifier": "c1"})
        stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "DELETING"),
                                      {"domainIdentifier": D, "identifier": "c1"})
        stubs["datazone"].add_client_error("get_connection", "ResourceNotFoundException", "deleted",
                                         expected_params={"domainIdentifier": D, "identifier": "c1"})
    original_create = c["datazone"].create_connection
    failure = TimeoutError("create response lost")
    requests = []

    def lose_first_response(**request):
        requests.append(request)
        response = original_create(**request)
        if len(requests) == 1:
            raise failure
        return response

    monkeypatch.setattr(c["datazone"], "create_connection", lose_first_response)
    with pytest.raises(TimeoutError) as exc:
        _run(c, shared_secret=True)

    assert exc.value is failure
    assert len(requests) == 2 and requests[0] == requests[1]
    assert any(SECRET in note and "retained" in note for note in failure.__notes__)
    assert not any("cleanup failed" in note for note in failure.__notes__)
    if status != "CREATE_FAILED":
        assert any("c1" in note and status in note and "retained" in note and "manual" in note
                   for note in failure.__notes__)


def test_unresolved_create_reports_manual_cleanup_and_preserves_error(clients, monkeypatch):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    failure = TimeoutError("create response lost")
    create = Mock(side_effect=failure)
    monkeypatch.setattr(c["datazone"], "create_connection", create)

    with pytest.raises(TimeoutError) as exc:
        _run(c, shared_secret=True)

    assert exc.value is failure
    assert create.call_count == 2
    assert any(DZ_NAME in note and "manual" in note and "verify consumers" in note
               for note in failure.__notes__)


@pytest.mark.parametrize("error_code,http_status,calls", [
    ("ValidationException", 400, 1),
    ("InternalServerException", 500, 2),
])
def test_only_uncertain_service_errors_replay_create(clients, monkeypatch, error_code, http_status, calls):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    stubs["datazone"].add_client_error("create_connection", error_code, "create failed",
                                       http_status_code=http_status)
    if calls == 2:
        stubs["datazone"].add_response("create_connection", _conn("c1", DZ_NAME, "CREATING"))
        stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "CREATING"),
                                      {"domainIdentifier": D, "identifier": "c1"})
    create = Mock(wraps=c["datazone"].create_connection)
    monkeypatch.setattr(c["datazone"], "create_connection", create)

    with pytest.raises(getattr(c["datazone"].exceptions, error_code)) as exc:
        _run(c, shared_secret=True)

    assert create.call_count == calls
    assert any(SECRET in note and "retained" in note for note in exc.value.__notes__)
    assert not any("cleanup failed" in note for note in exc.value.__notes__)


def test_new_create_after_cleanup_does_not_replay_deleted_connection(clients, monkeypatch):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    stubs["datazone"].add_response("create_connection", _conn("c1", DZ_NAME, "CREATING"))
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "CREATE_FAILED"),
                                  {"domainIdentifier": D, "identifier": "c1"})
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "CREATE_FAILED"),
                                  {"domainIdentifier": D, "identifier": "c1"})
    stubs["datazone"].add_response("delete_connection", {"status": "DELETED"},
                                  {"domainIdentifier": D, "identifier": "c1"})
    _common(stubs, tags=[{"Key": "for-use-with-all-datazone-projects", "Value": "true"}])
    _glue_free(stubs, DZ_NAME)
    stubs["datazone"].add_response("create_connection", _conn("c2", DZ_NAME, "CREATING"))
    stubs["datazone"].add_response("get_connection", _conn("c2", DZ_NAME, "READY"),
                                  {"domainIdentifier": D, "identifier": "c2"})
    create = Mock(wraps=c["datazone"].create_connection)
    monkeypatch.setattr(c["datazone"], "create_connection", create)

    with pytest.raises(RuntimeError, match="CREATE_FAILED"):
        _run(c, shared_secret=True)
    assert _run(c, shared_secret=True).datazone_id == "c2"

    tokens = [call.kwargs["clientToken"] for call in create.call_args_list]
    assert len(tokens) == 2 and tokens[0] != tokens[1]


@pytest.mark.parametrize("delete_status", ["DELETE_FAILED", "DELETING"])
def test_failed_delete_is_reported_without_masking_create_failure(clients, delete_status):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    stubs["datazone"].add_response("create_connection", _conn("c1", DZ_NAME, "CREATING"))
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "CREATE_FAILED", err="bad source"),
                                  {"domainIdentifier": D, "identifier": "c1"})
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "CREATE_FAILED", err="bad source"),
                                  {"domainIdentifier": D, "identifier": "c1"})
    stubs["datazone"].add_response("delete_connection", {"status": delete_status},
                                  {"domainIdentifier": D, "identifier": "c1"})
    if delete_status == "DELETING":
        stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "DELETING"),
                                      {"domainIdentifier": D, "identifier": "c1"})
        stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "DELETE_FAILED", err="cannot delete"),
                                      {"domainIdentifier": D, "identifier": "c1"})

    with pytest.raises(RuntimeError, match="CREATE_FAILED.*bad source") as exc:
        _run(c, shared_secret=True)

    assert any("delete DataZone connection c1" in note and "DELETE_FAILED" in note
               for note in exc.value.__notes__)


def test_delete_timeout_is_reported_and_sharing_grant_is_retained(clients, monkeypatch):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    stubs["datazone"].add_response("create_connection", _conn("c1", DZ_NAME, "CREATING"))
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "CREATE_FAILED"),
                                  {"domainIdentifier": D, "identifier": "c1"})
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "CREATE_FAILED"),
                                  {"domainIdentifier": D, "identifier": "c1"})
    stubs["datazone"].add_response("delete_connection", {"status": "DELETING"},
                                  {"domainIdentifier": D, "identifier": "c1"})
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "DELETING"),
                                  {"domainIdentifier": D, "identifier": "c1"})
    ticks = iter([0, 0, 901])
    monkeypatch.setattr(connmigrate.time, "monotonic", lambda: next(ticks))

    with pytest.raises(RuntimeError, match="CREATE_FAILED") as exc:
        _run(c, shared_secret=True)

    assert any("delete DataZone connection c1" in note and "900" in note
               for note in exc.value.__notes__)
    assert any(SECRET in note and "retained" in note for note in exc.value.__notes__)


@pytest.mark.parametrize("apply", [False, True])
@pytest.mark.parametrize("collision", ["datazone", "glue", "not-ready"])
def test_batch_checks_all_targets_before_writes(clients, monkeypatch, apply, collision):
    c, stubs = clients
    second = "second-db"
    second_clone = naming.datazone_connection_name(second, project_id=P)
    stubs["datazone"].add_response("list_environments", {"items": [_env_summary()]},
                                  {"domainIdentifier": D, "projectIdentifier": P})
    stubs["datazone"].add_response("get_environment", _env(),
                                  {"domainIdentifier": D, "identifier": ENV})
    for source in (SOURCE, {**SOURCE, "Name": second}):
        stubs["glue"].add_response("get_connection", {"Connection": source},
                                  {"Name": source["Name"], "HidePassword": True})
    items = [] if collision == "glue" else [_summary(second_clone, "c2")]
    stubs["datazone"].add_response("list_connections", {"items": items},
                                  {"domainIdentifier": D, "projectIdentifier": P})
    _glue_free(stubs, DZ_NAME)
    stubs["secretsmanager"].add_response("describe_secret", {"ARN": SECRET, "Tags": []},
                                        {"SecretId": SECRET})
    if collision == "glue":
        stubs["glue"].add_response("get_connection", {"Connection": {**SOURCE, "Name": second_clone}},
                                  {"Name": second_clone, "HidePassword": True})
    else:
        desc = naming.source_marker(second) if collision == "not-ready" else "manual connection"
        status = "CREATING" if collision == "not-ready" else "READY"
        stubs["datazone"].add_response("get_connection", _conn("c2", second_clone, status, desc),
                                      {"domainIdentifier": D, "identifier": "c2"})
    create, tag = Mock(), Mock()
    monkeypatch.setattr(c["datazone"], "create_connection", create)
    monkeypatch.setattr(c["secretsmanager"], "tag_resource", tag)
    expected = RuntimeError if collision == "not-ready" else naming.ConnectionNameConflict

    with pytest.raises(expected) as exc:
        connmigrate.migrate_connections(glue=c["glue"], sm=c["secretsmanager"], dz=c["datazone"],
                                       names=[SRC, second], domain_id=D, project_id=P,
                                       apply=apply, shared_secret=True)

    if collision == "not-ready":
        message = str(exc.value)
        assert "c2" in message and second_clone in message and "CREATING" in message
        assert "inspect" in message and "wait" in message and "retry" in message
        assert "verify consumers before any manual cleanup" in message
    create.assert_not_called()
    tag.assert_not_called()


@pytest.mark.parametrize("domain_tag", [
    {"Key": "AmazonDataZoneDomain", "Value": D},
    {"Key": "AmazonDataZoneDomain"},
])
def test_batch_applies_reusing_ready_clone(clients, domain_tag):
    c, stubs = clients
    tags = [{"Key": "AmazonDataZoneProject", "Value": P}, domain_tag]
    stubs["datazone"].add_response("list_environments", {"items": [_env_summary()]},
                                  {"domainIdentifier": D, "projectIdentifier": P})
    stubs["datazone"].add_response("get_environment", _env(),
                                  {"domainIdentifier": D, "identifier": ENV})
    stubs["glue"].add_response("get_connection", {"Connection": SOURCE},
                              {"Name": SRC, "HidePassword": True})
    stubs["datazone"].add_response("list_connections", {"items": [_summary(DZ_NAME, "c1")]},
                                  {"domainIdentifier": D, "projectIdentifier": P})
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "READY", naming.source_marker(SRC)),
                                  {"domainIdentifier": D, "identifier": "c1"})
    stubs["secretsmanager"].add_response("describe_secret", {"ARN": SECRET, "Tags": tags},
                                        {"SecretId": SECRET})
    _common(stubs, existing=[(DZ_NAME, "c1", naming.source_marker(SRC))], tags=tags)

    result = connmigrate.migrate_connections(glue=c["glue"], sm=c["secretsmanager"], dz=c["datazone"],
                                           names=[SRC, SRC], domain_id=D, project_id=P, apply=True)

    assert result["applied"] is True
    assert len(result["connections"]) == 1
    assert result["connections"][0]["datazoneId"] == "c1"
    assert result["connections"][0]["reused"] is True


@pytest.mark.parametrize("apply", [False, True])
def test_batch_rejects_collisions_between_requested_targets_before_writes(clients, monkeypatch, apply):
    c, stubs = clients
    names = ["same-source-prefix-aaa-1406", "same-source-prefix-aaa-50076"]
    clone_name = naming.datazone_connection_name(names[0], project_id=P)
    assert clone_name == naming.datazone_connection_name(names[1], project_id=P)
    stubs["datazone"].add_response("list_environments", {"items": [_env_summary()]},
                                  {"domainIdentifier": D, "projectIdentifier": P})
    stubs["datazone"].add_response("get_environment", _env(),
                                  {"domainIdentifier": D, "identifier": ENV})
    for name in names:
        stubs["glue"].add_response("get_connection", {"Connection": {**SOURCE, "Name": name}},
                                  {"Name": name, "HidePassword": True})
    stubs["datazone"].add_response("list_connections", {"items": []},
                                  {"domainIdentifier": D, "projectIdentifier": P})
    _glue_free(stubs, clone_name)
    stubs["secretsmanager"].add_response("describe_secret", {"ARN": SECRET, "Tags": []},
                                        {"SecretId": SECRET})
    create, tag = Mock(), Mock()
    monkeypatch.setattr(c["datazone"], "create_connection", create)
    monkeypatch.setattr(c["secretsmanager"], "tag_resource", tag)

    with pytest.raises(naming.ConnectionNameConflict, match=clone_name):
        connmigrate.migrate_connections(glue=c["glue"], sm=c["secretsmanager"], dz=c["datazone"],
                                       names=names, domain_id=D, project_id=P,
                                       apply=apply, shared_secret=True)

    create.assert_not_called()
    tag.assert_not_called()


@pytest.mark.parametrize("description,status", [
    (None, "READY"),
    (naming.source_marker(SRC), "DELETED"),
])
def test_deleted_summary_does_not_block_recreation_when_glue_name_is_free(clients, description, status):
    c, stubs = clients
    _common(stubs, existing=[(DZ_NAME, "old", description)], status=status)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    stubs["datazone"].add_response("create_connection", _conn("new", DZ_NAME, "CREATING"))
    stubs["datazone"].add_response("get_connection", _conn("new", DZ_NAME, "READY"),
                                  {"domainIdentifier": D, "identifier": "new"})

    migrated = _run(c, shared_secret=True)

    assert migrated.datazone_id == "new"
    assert migrated.reused is False


def test_deleted_summary_does_not_hide_a_live_owned_clone(clients):
    c, stubs = clients
    _common(stubs, existing=[(DZ_NAME, "old", None), (DZ_NAME, "live", naming.source_marker(SRC))],
            tags=[{"Key": "AmazonDataZoneProject", "Value": P},
                  {"Key": "AmazonDataZoneDomain", "Value": D}])

    migrated = _run(c)

    assert migrated.datazone_id == "live"
    assert migrated.reused is True


@pytest.mark.parametrize("status", [None, "DELETED"])
def test_owned_clone_input_skips_deleted_predecessor(clients, status):
    c, stubs = clients
    summaries = [
        {**_summary(DZ_NAME, cid), "physicalEndpoints": [{"glueConnectionName": DZ_NAME}]}
        for cid in ("old", "live")
    ]
    stubs["datazone"].add_response("list_connections", {"items": summaries},
                                  {"domainIdentifier": D, "projectIdentifier": P})
    if status is None:
        stubs["datazone"].add_client_error("get_connection", "ResourceNotFoundException", "deleted",
                                           expected_params={"domainIdentifier": D, "identifier": "old"})
    else:
        stubs["datazone"].add_response("get_connection", _conn("old", DZ_NAME, status, naming.source_marker(SRC)),
                                      {"domainIdentifier": D, "identifier": "old"})
    stubs["datazone"].add_response("get_connection", _conn("live", DZ_NAME, "READY", naming.source_marker(SRC)),
                                  {"domainIdentifier": D, "identifier": "live"})
    stubs["glue"].add_response("get_connection", {"Connection": {**SOURCE, "Name": DZ_NAME}},
                              {"Name": DZ_NAME, "HidePassword": True})
    stubs["secretsmanager"].add_response("describe_secret", {"ARN": SECRET, "Tags": [
        {"Key": "AmazonDataZoneProject", "Value": P},
        {"Key": "AmazonDataZoneDomain", "Value": D}]}, {"SecretId": SECRET})

    migrated = connmigrate.migrate_connection(glue=c["glue"], sm=c["secretsmanager"], dz=c["datazone"],
                                            domain_id=D, project_id=P, name=DZ_NAME, poll=0)

    assert migrated.datazone_id == "live"
    assert migrated.glue_name == DZ_NAME
    assert migrated.reused is True


@pytest.mark.parametrize("apply", [False, True])
@pytest.mark.parametrize("tags,expected", [
    ([{"Key": "AmazonDataZoneProject", "Value": P}], {"AmazonDataZoneDomain": D}),
    ([], {"for-use-with-all-datazone-projects": "true"}),
    ([{"Key": "AmazonDataZoneProject", "Value": "other-project"}],
     {"for-use-with-all-datazone-projects": "true"}),
])
def test_owned_clone_input_reconciles_tags_planned_by_batch(clients, apply, tags, expected):
    c, stubs = clients
    source = {**SOURCE, "Name": DZ_NAME}
    summary = {**_summary(DZ_NAME, "c1"), "physicalEndpoints": [{"glueConnectionName": DZ_NAME}]}
    stubs["datazone"].add_response("list_environments", {"items": [_env_summary()]},
                                  {"domainIdentifier": D, "projectIdentifier": P})
    stubs["datazone"].add_response("get_environment", _env(),
                                  {"domainIdentifier": D, "identifier": ENV})
    stubs["glue"].add_response("get_connection", {"Connection": source},
                              {"Name": DZ_NAME, "HidePassword": True})
    for _ in range(2 if apply else 1):
        stubs["datazone"].add_response("list_connections", {"items": [summary]},
                                      {"domainIdentifier": D, "projectIdentifier": P})
        stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "READY", naming.source_marker(SRC)),
                                      {"domainIdentifier": D, "identifier": "c1"})
        stubs["secretsmanager"].add_response("describe_secret", {"ARN": SECRET, "Tags": tags},
                                            {"SecretId": SECRET})
    if apply:
        stubs["glue"].add_response("get_connection", {"Connection": source},
                                  {"Name": DZ_NAME, "HidePassword": True})
        stubs["secretsmanager"].add_response("tag_resource", {}, {
            "SecretId": SECRET, "Tags": [{"Key": k, "Value": v} for k, v in expected.items()]})

    result = connmigrate.migrate_connections(
        glue=c["glue"], sm=c["secretsmanager"], dz=c["datazone"],
        names=[DZ_NAME], domain_id=D, project_id=P, apply=apply)

    if apply:
        assert result["applied"] is True
        migrated = result["connections"][0]
        assert (migrated["datazoneId"], migrated["glueName"], migrated["reused"]) == ("c1", DZ_NAME, True)
        assert migrated["tagChange"]["prior"] == {k: None for k in expected}
    else:
        assert result["connections"][0]["secretTagsToAdd"] == expected


def test_failed_migration_keeps_sharing_adopted_by_concurrent_clone(monkeypatch):
    tags = {}
    completed = []
    second = "second-db"
    glue = Mock()
    glue.exceptions.EntityNotFoundException = connmigrate.SourceConnectionNotFound

    def read_source(*, Name, HidePassword):
        assert HidePassword is True
        if Name not in (SRC, second):
            raise connmigrate.SourceConnectionNotFound(Name)
        return {"Connection": {**SOURCE, "Name": Name}}

    glue.get_connection.side_effect = read_source
    secrets = [Mock(), Mock()]
    for sm in secrets:
        sm.describe_secret.side_effect = lambda **kw: {
            "Tags": [{"Key": k, "Value": v} for k, v in tags.items()]}
        sm.tag_resource.side_effect = lambda **kw: tags.update(
            {t["Key"]: t["Value"] for t in kw["Tags"]})
        sm.untag_resource.side_effect = lambda **kw: [tags.pop(k, None) for k in kw["TagKeys"]]
    clients = [Mock(), Mock()]
    for cid, dz in zip(("failed", "successful"), clients):
        dz.list_connections.return_value = {"items": []}
        dz.list_environments.return_value = {"items": [_env_summary()]}
        dz.get_environment.return_value = _env()
        dz.create_connection.return_value = {"connectionId": cid}
        dz.get_connection.return_value = _conn(cid, DZ_NAME, "CREATE_FAILED" if cid == "failed" else "READY")
        dz.delete_connection.return_value = {"status": "DELETED"}
    failure = RuntimeError("first clone failed after second adopted access")

    def wait(dz, domain_id, connection_id, **kw):
        if connection_id == "failed":
            completed.append(connmigrate.migrate_connection(
                glue=glue, sm=secrets[1], dz=clients[1], domain_id=D, project_id=P,
                name=second, shared_secret=True, poll=0))
            raise failure
        return _conn(connection_id, naming.datazone_connection_name(second, project_id=P), "READY")

    monkeypatch.setattr(connmigrate, "wait_datazone_connection_ready", wait)
    with pytest.raises(RuntimeError) as exc:
        connmigrate.migrate_connection(
            glue=glue, sm=secrets[0], dz=clients[0], domain_id=D, project_id=P,
            name=SRC, shared_secret=True, poll=0)

    assert exc.value is failure
    assert completed[0].datazone_id == "successful"
    assert completed[0].tag_change.prior == {}
    assert tags["for-use-with-all-datazone-projects"] == "true"
    secrets[0].untag_resource.assert_not_called()
    clients[0].delete_connection.assert_called_once_with(domainIdentifier=D, identifier="failed")
    clients[1].delete_connection.assert_not_called()
    assert any(SECRET in note and "retained" in note and "manual" in note for note in failure.__notes__)


@pytest.mark.parametrize("cleanup_state", ["CREATING", "CREATE_FAILED"])
def test_readiness_interrupt_cleans_only_failed_clone_and_preserves_cancellation(clients, monkeypatch, cleanup_state):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    stubs["datazone"].add_response("create_connection", _conn("c1", DZ_NAME, "CREATING"))
    for status in ("CREATING", cleanup_state):
        stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, status),
                                      {"domainIdentifier": D, "identifier": "c1"})
    if cleanup_state == "CREATE_FAILED":
        stubs["datazone"].add_response("delete_connection", {"status": "DELETED"},
                                      {"domainIdentifier": D, "identifier": "c1"})
    failure = KeyboardInterrupt("poll cancelled")
    monkeypatch.setattr(connmigrate.time, "sleep", Mock(side_effect=failure))

    with pytest.raises(KeyboardInterrupt) as exc:
        _run(c, shared_secret=True)

    assert exc.value is failure
    assert any(SECRET in note and "retained" in note for note in failure.__notes__)
    if cleanup_state == "CREATE_FAILED":
        assert "cleanup completed: delete DataZone connection c1" in failure.__notes__
    else:
        assert any("c1" in note and "CREATING" in note and "retained" in note and "manual" in note
                   for note in failure.__notes__)


@pytest.mark.parametrize("cleanup_error", [InterruptedError("cleanup interrupted"), KeyboardInterrupt("cleanup cancelled")])
def test_terminal_failed_clone_cleanup_interrupt_preserves_original_error(clients, monkeypatch, cleanup_error):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    stubs["datazone"].add_response("create_connection", _conn("c1", DZ_NAME, "CREATING"))
    for _ in range(2):
        stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "CREATE_FAILED", err="bad source"),
                                      {"domainIdentifier": D, "identifier": "c1"})
    delete = Mock(side_effect=cleanup_error)
    monkeypatch.setattr(c["datazone"], "delete_connection", delete)

    with pytest.raises(RuntimeError, match="CREATE_FAILED.*bad source") as exc:
        _run(c, shared_secret=True)

    delete.assert_called_once_with(domainIdentifier=D, identifier="c1")
    assert any("delete DataZone connection c1" in note and str(cleanup_error) in note
               for note in exc.value.__notes__)
    assert any(SECRET in note and "retained" in note for note in exc.value.__notes__)


@pytest.mark.parametrize("failure", [TimeoutError("poll response lost"), KeyboardInterrupt("poll cancelled")])
def test_failed_poll_retains_same_ready_clone_reused_by_another_invocation(clients, monkeypatch, failure):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    stubs["datazone"].add_response("create_connection", _conn("c1", DZ_NAME, "CREATING"))
    stubs["datazone"].add_response("get_connection", _conn("c1", DZ_NAME, "READY"),
                                  {"domainIdentifier": D, "identifier": "c1"})
    second_dz = boto3.Session(aws_access_key_id="x", aws_secret_access_key="x",
                             region_name="us-east-2").client("datazone")
    completed = []
    original_get = c["datazone"].get_connection

    def poll_after_adoption(**request):
        if not completed:
            completed.append(_run({**c, "datazone": second_dz}, shared_secret=True))
            raise failure
        return original_get(**request)

    delete = Mock()
    monkeypatch.setattr(c["datazone"], "get_connection", poll_after_adoption)
    monkeypatch.setattr(c["datazone"], "delete_connection", delete)
    with Stubber(second_dz) as second_stub:
        _common({**stubs, "datazone": second_stub},
                existing=[(DZ_NAME, "c1", naming.source_marker(SRC))],
                tags=[{"Key": "for-use-with-all-datazone-projects", "Value": "true"}])
        with pytest.raises(type(failure)) as exc:
            _run(c, shared_secret=True)
        second_stub.assert_no_pending_responses()

    assert exc.value is failure
    assert completed[0].datazone_id == "c1" and completed[0].reused is True
    delete.assert_not_called()
    assert any("c1" in note and "READY" in note and "retained" in note and "manual" in note
               for note in failure.__notes__)


@pytest.mark.parametrize("state_error", [
    None, TimeoutError("state response lost"), InterruptedError("state read interrupted"),
    KeyboardInterrupt("state read cancelled")])
def test_unknown_clone_state_is_retained_without_masking_poll_failure(clients, monkeypatch, state_error):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    stubs["datazone"].add_response("create_connection", _conn("c1", DZ_NAME, "CREATING"))
    failure = TimeoutError("poll response lost")
    unknown = {**_conn("c1", DZ_NAME, "CREATING"), "props": {}}
    monkeypatch.setattr(c["datazone"], "get_connection", Mock(side_effect=[failure, state_error or unknown]))
    delete = Mock()
    monkeypatch.setattr(c["datazone"], "delete_connection", delete)

    with pytest.raises(TimeoutError) as exc:
        _run(c, shared_secret=True)

    assert exc.value is failure
    delete.assert_not_called()
    assert any("c1" in note and "unknown" in note and "retained" in note and "manual" in note
               for note in failure.__notes__)
    if state_error:
        assert any(str(state_error) in note for note in failure.__notes__)
    assert any(SECRET in note and "retained" in note for note in failure.__notes__)


def test_batch_interrupt_reports_previously_completed_clones(clients, monkeypatch):
    c, stubs = clients
    names = [SRC, "second-db"]
    stubs["datazone"].add_response("list_environments", {"items": [_env_summary()]},
                                  {"domainIdentifier": D, "projectIdentifier": P})
    stubs["datazone"].add_response("get_environment", _env(),
                                  {"domainIdentifier": D, "identifier": ENV})
    stubs["datazone"].add_response("list_connections", {"items": []},
                                  {"domainIdentifier": D, "projectIdentifier": P})
    for name in names:
        source = {**SOURCE, "Name": name, "AuthenticationConfiguration": {"AuthenticationType": "IAM"}}
        stubs["glue"].add_response("get_connection", {"Connection": source},
                                  {"Name": name, "HidePassword": True})
    for name in names:
        _glue_free(stubs, naming.datazone_connection_name(name, project_id=P))
    failure = KeyboardInterrupt("second clone cancelled")
    migrated = connmigrate.MigratedConnection(SRC, "c1", DZ_NAME, DZ_NAME, False, None)
    monkeypatch.setattr(connmigrate, "migrate_connection", Mock(side_effect=[migrated, failure]))

    with pytest.raises(KeyboardInterrupt) as exc:
        connmigrate.migrate_connections(
            glue=c["glue"], sm=c["secretsmanager"], dz=c["datazone"],
            names=names, domain_id=D, project_id=P, apply=True)

    assert exc.value is failure
    assert any(DZ_NAME in note and "completed clones retained" in note for note in failure.__notes__)


def test_create_recovery_interrupt_reports_unknown_outcome_without_masking_failure(clients, monkeypatch):
    c, stubs = clients
    _common(stubs)
    _glue_free(stubs, DZ_NAME)
    _tag_shared(stubs)
    failure = TimeoutError("response lost")
    monkeypatch.setattr(c["datazone"], "create_connection",
                        Mock(side_effect=[failure, KeyboardInterrupt("recovery cancelled")]))

    with pytest.raises(TimeoutError) as exc:
        _run(c, shared_secret=True)

    assert exc.value is failure
    assert any("create outcome unknown" in note and "recovery cancelled" in note for note in failure.__notes__)
    assert any(SECRET in note and "retained" in note for note in failure.__notes__)


def test_readiness_ignores_wall_clock_jump(monkeypatch):
    dz = Mock()
    dz.get_connection.side_effect = [
        _conn("c1", DZ_NAME, status) for status in ("CREATING", "CREATING", "READY")]
    wall_clock = iter([0, 90001])
    elapsed = iter([0, 1, 2])
    monkeypatch.setattr(connmigrate.time, "time", lambda: next(wall_clock))
    monkeypatch.setattr(connmigrate.time, "monotonic", lambda: next(elapsed))

    assert connmigrate.wait_datazone_connection_ready(dz, D, "c1", timeout=10, poll=0)["connectionId"] == "c1"
    assert dz.get_connection.call_count == 3


def test_readiness_times_out_after_monotonic_deadline(monkeypatch):
    dz = Mock()
    dz.get_connection.return_value = _conn("c1", DZ_NAME, "CREATING")
    elapsed = Mock(side_effect=[0, 11])
    monkeypatch.setattr(connmigrate.time, "time", Mock(side_effect=[0, 11]))
    monkeypatch.setattr(connmigrate.time, "monotonic", elapsed)

    with pytest.raises(TimeoutError, match="not READY after 10s"):
        connmigrate.wait_datazone_connection_ready(dz, D, "c1", timeout=10, poll=0)
    assert elapsed.call_count == 2
