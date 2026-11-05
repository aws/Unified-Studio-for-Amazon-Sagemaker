"""Property-based tests for Glue Connection -> DataZone glueConnectionInput.

See the adjacent README.md for dependencies and test commands.
"""
import json

import botocore.session
import pytest
from botocore.validate import ParamValidator
from hypothesis import given, strategies as st

from migration.glue import connections

_DZ = botocore.session.get_session().get_service_model("datazone")
_DZ_INPUT = _DZ.shape_for("GlueConnectionInput")
_DZ_TYPES = set(_DZ_INPUT.members["connectionType"].enum)

# Spec (independent of the implementation): supported source shapes -> DataZone type.
NATIVE = {
    "DOCUMENTDB": "DOCUMENTDB",
    "DYNAMODB": "DYNAMODB",
    "OPENSEARCH": "OPENSEARCH",
    "MYSQL": "MYSQL",            # MySQL + Aurora MySQL
    "POSTGRESQL": "POSTGRESQL",  # PostgreSQL + Aurora PostgreSQL
    "SQLSERVER": "SQLSERVER",
    "ORACLE": "ORACLE",
    "BIGQUERY": "BIGQUERY",
    "SNOWFLAKE": "SNOWFLAKE",
    "TERADATA": "TERADATA",
    "REDSHIFT": "REDSHIFT",
}
CRED_KEYS = {"USERNAME", "PASSWORD", "ENCRYPTED_PASSWORD", "SECRET_ID"}
PROJECT_ROLE = "arn:aws:iam::123456789012:role/service-role/project-user-role"
KMS_ARN = "arn:aws:kms:us-east-2:123456789012:key/0000aaaa-bb11-cc22-dd33-eeeeee444444"

_ascii = st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E), max_size=40)
_vals = _ascii.filter(bool)  # Glue/DataZone property values: min length 1
_names = st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E), min_size=1, max_size=255)
_arns = _ascii.map(lambda s: f"arn:aws:secretsmanager:us-east-2:123456789012:secret:{s}")


@st.composite
def glue_connections(draw):
    """Returns (V2 glue Connection dict, expected DataZone type, auth mode)."""
    ctype = draw(st.sampled_from(sorted(NATIVE)))
    dz_type = NATIVE[ctype]
    props = draw(st.dictionaries(
        st.sampled_from(["JDBC_ENFORCE_SSL", "CUSTOM_JDBC_CERT", "HOST", "PORT", "DATABASE", "ROLE_ARN"]),
        _vals, max_size=4))
    conn = {"Name": draw(_names), "ConnectionType": ctype, "ConnectionSchemaVersion": 2,
            "ConnectionProperties": props}
    mode = draw(st.sampled_from(["secret", "iam", "none"] if dz_type != "REDSHIFT" else ["secret", "none"]))
    if mode == "secret":
        conn["AuthenticationConfiguration"] = {
            "AuthenticationType": draw(st.sampled_from(["BASIC", "CUSTOM"])), "SecretArn": draw(_arns)}
        if draw(st.booleans()):
            conn["AuthenticationConfiguration"]["KmsKeyArn"] = KMS_ARN
    elif mode == "iam":
        conn["AuthenticationConfiguration"] = {"AuthenticationType": "IAM"}
    if draw(st.booleans()):
        conn["Description"] = draw(_ascii)
    if draw(st.booleans()):
        pcr = {"SubnetId": "subnet-" + draw(st.text("abcdef0123456789", min_size=8, max_size=17)),
               "SecurityGroupIdList": draw(st.lists(st.just("sg-0123456789abcdef0"), max_size=3)),
               "AvailabilityZone": "us-east-2a"}
        conn["PhysicalConnectionRequirements"] = {k: v for k, v in pcr.items() if draw(st.booleans())}
    if draw(st.booleans()):
        conn["MatchCriteria"] = draw(st.lists(_ascii, min_size=1, max_size=10))
    if draw(st.booleans()):
        conn["CompatibleComputeEnvironments"] = draw(
            st.lists(st.sampled_from(["SPARK", "ATHENA", "PYTHON"]), min_size=1, max_size=3, unique=True))
    for key in ("SparkProperties", "AthenaProperties", "PythonProperties"):
        if draw(st.booleans()):
            conn[key] = draw(st.dictionaries(_vals, _vals, max_size=3))
    return conn, dz_type, mode


def _translate(conn, role_arn=PROJECT_ROLE):
    return connections.to_datazone_input(conn, role_arn=role_arn)


@given(glue_connections())
def test_output_is_valid_datazone_input(case):
    conn, _, _ = case
    out = _translate(conn)
    report = ParamValidator().validate(out, _DZ_INPUT)
    assert not report.has_errors(), report.generate_report()
    assert out["connectionType"] in _DZ_TYPES
    assert len(out.get("matchCriteria", "")) <= 10


@given(glue_connections())
def test_connection_type_mapped(case):
    conn, dz_type, _ = case
    assert _translate(conn)["connectionType"] == dz_type


@given(glue_connections())
def test_no_glue_name_is_sent(case):
    conn, _, _ = case
    assert "name" not in _translate(conn)


@given(glue_connections())
def test_non_credential_fields_preserved(case):
    conn, _, _ = case
    out = _translate(conn)
    expected = {**conn["ConnectionProperties"], "ROLE_ARN": PROJECT_ROLE}
    assert out["connectionProperties"] == expected
    assert out.get("description") == conn.get("Description")
    for g, d in (("SparkProperties", "sparkProperties"), ("AthenaProperties", "athenaProperties"),
                 ("PythonProperties", "pythonProperties")):
        assert out.get(d) == conn.get(g)
    assert out.get("validateForComputeEnvironments") == conn.get("CompatibleComputeEnvironments")
    assert out["validateCredentials"] is False
    pcr = {k: v for k, v in (conn.get("PhysicalConnectionRequirements") or {}).items() if v}
    want = {d: pcr[g] for g, d in (("SubnetId", "subnetId"), ("SecurityGroupIdList", "securityGroupIdList"),
                                   ("AvailabilityZone", "availabilityZone")) if g in pcr}
    assert out.get("physicalConnectionRequirements") == (want or None)


@given(glue_connections())
def test_source_role_never_forwarded(case):
    conn, _, _ = case
    assert "ROLE_ARN" not in _translate(conn, role_arn=None)["connectionProperties"]


@given(glue_connections())
def test_output_does_not_alias_input(case):
    conn, _, _ = case
    before = json.dumps(conn, sort_keys=True)
    out = _translate(conn)
    for v in out.values():
        if isinstance(v, dict):
            v["__mutated__"] = "x"
            for inner in v.values():
                if isinstance(inner, list):
                    inner.append("x")
        elif isinstance(v, list):
            v.append("x")
    assert json.dumps(conn, sort_keys=True) == before


@given(glue_connections())
def test_match_criteria_is_first_entry_truncated(case):
    conn, _, _ = case
    out = _translate(conn)
    if conn.get("MatchCriteria"):
        assert out["matchCriteria"] == conn["MatchCriteria"][0][:10]
    else:
        assert "matchCriteria" not in out


@given(glue_connections())
def test_auth_passes_secret_through(case):
    conn, _, mode = case
    auth = _translate(conn).get("authenticationConfiguration")
    if mode == "secret":
        src = conn["AuthenticationConfiguration"]
        want = {"authenticationType": src["AuthenticationType"], "secretArn": src["SecretArn"]}
        if "KmsKeyArn" in src:
            want["kmsKeyArn"] = src["KmsKeyArn"]
        assert auth == want
        assert connections.secret_arn(conn) == src["SecretArn"]
    else:
        assert auth is None
        assert connections.secret_arn(conn) is None


@given(glue_connections())
def test_deterministic(case):
    conn, _, _ = case
    assert _translate(conn) == _translate(conn)


@pytest.mark.parametrize("key", sorted(CRED_KEYS))
def test_inline_credentials_rejected(key):
    conn = {"Name": "a", "ConnectionType": "MYSQL", "ConnectionSchemaVersion": 2,
            "ConnectionProperties": {key: "x"}}
    with pytest.raises(connections.UnsupportedConnection):
        _translate(conn)


@pytest.mark.parametrize("atype", ["BASIC", "CUSTOM"])
def test_secret_auth_without_secret_rejected(atype):
    conn = {"Name": "a", "ConnectionType": "MYSQL", "ConnectionSchemaVersion": 2,
            "ConnectionProperties": {}, "AuthenticationConfiguration": {"AuthenticationType": atype}}
    with pytest.raises(connections.UnsupportedConnection):
        _translate(conn)


@pytest.mark.parametrize("conn", [
    {"Name": "a", "ConnectionType": "AZURESQL", "ConnectionSchemaVersion": 2, "ConnectionProperties": {}},
    {"Name": "a", "ConnectionType": "KAFKA", "ConnectionSchemaVersion": 2, "ConnectionProperties": {}},
    {"Name": "a", "ConnectionType": "NETWORK", "ConnectionSchemaVersion": 2, "ConnectionProperties": {}},
    {"Name": "a", "ConnectionType": "MONGODB", "ConnectionSchemaVersion": 2, "ConnectionProperties": {}},
    {"Name": "a", "ConnectionType": "SALESFORCE", "ConnectionSchemaVersion": 2, "ConnectionProperties": {}},
    {"Name": "a", "ConnectionType": "JDBC", "ConnectionSchemaVersion": 2, "ConnectionProperties": {}},
    {"Name": "a", "ConnectionType": "JDBC", "ConnectionSchemaVersion": 2, "ConnectionProperties": {"JDBC_CONNECTION_URL": "jdbc:redshift://h/d"}},
    {"Name": "a", "ConnectionType": "JDBC", "ConnectionSchemaVersion": 2, "ConnectionProperties": {"JDBC_CONNECTION_URL": "jdbc:mysql://h/d"}},
    {"Name": "a", "ConnectionType": "SNOWFLAKE", "ConnectionSchemaVersion": 2, "ConnectionProperties": {},
     "AuthenticationConfiguration": {"AuthenticationType": "OAUTH2",
                                     "SecretArn": "arn:aws:secretsmanager:us-east-2:1:secret:s"}},
    # V1 connections (missing or version 1) are unsupported.
    {"Name": "a", "ConnectionType": "MYSQL", "ConnectionProperties": {}},
    {"Name": "a", "ConnectionType": "REDSHIFT", "ConnectionSchemaVersion": 1, "ConnectionProperties": {}},
    {"Name": "a", "ConnectionType": "JDBC", "ConnectionSchemaVersion": 1,
     "ConnectionProperties": {"JDBC_CONNECTION_URL": "jdbc:redshift://h:5439/d"}},
    {"Name": "a", "ConnectionType": "REDSHIFT", "ConnectionSchemaVersion": 2, "ConnectionProperties": {},
     "AuthenticationConfiguration": {"AuthenticationType": "IAM"}},
])
def test_unsupported_rejected(conn):
    with pytest.raises(connections.UnsupportedConnection):
        connections.to_datazone_input(conn)
