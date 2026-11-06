"""Glue V2 Connection -> DataZone CreateConnection glueConnectionInput (pure, no AWS calls).

Input is GetConnection(HidePassword=True)["Connection"] for a ConnectionSchemaVersion 2
connection. Credentials are never read or copied: the clone references the SAME
secret ARN (and KMS key) as the source.
"""
from __future__ import annotations

import copy



class UnsupportedConnection(ValueError):
    """The source connection cannot be migrated to DataZone."""


# Native Glue ConnectionType -> DataZone GlueConnectionType.
_NATIVE = {
    "DOCUMENTDB": "DOCUMENTDB",
    "DYNAMODB": "DYNAMODB",
    "OPENSEARCH": "OPENSEARCH",
    "MYSQL": "MYSQL",            # MySQL, Aurora MySQL
    "POSTGRESQL": "POSTGRESQL",  # PostgreSQL, Aurora PostgreSQL
    "SQLSERVER": "SQLSERVER",
    "ORACLE": "ORACLE",
    "BIGQUERY": "BIGQUERY",
    "SNOWFLAKE": "SNOWFLAKE",
    "TERADATA": "TERADATA",
    "REDSHIFT": "REDSHIFT",      # V2 only; V1 Redshift is JDBC + jdbc:redshift: URL
}
# V1-style inline/legacy credential properties: not expected on V2, never forwarded.
_CRED_KEYS = frozenset({"USERNAME", "PASSWORD", "ENCRYPTED_PASSWORD", "SECRET_ID"})
# The role Glue uses for the connection (secret + VPC validation). The source's own
# role is replaced by the project's user role; DataZone does not fill it in.
_ROLE_KEY = "ROLE_ARN"
_SECRET_AUTH = ("BASIC", "CUSTOM")
_PROPERTY_MAPS = (
    ("SparkProperties", "sparkProperties"),
    ("AthenaProperties", "athenaProperties"),
    ("PythonProperties", "pythonProperties"),
)
_PCR_MAP = (("SubnetId", "subnetId"), ("SecurityGroupIdList", "securityGroupIdList"),
            ("AvailabilityZone", "availabilityZone"))


def resolve_connection_type(conn: dict) -> str:
    # Only V2 connections (ConnectionSchemaVersion == 2) are supported. V1 connections,
    # including JDBC-typed Redshift/MySQL/etc., are out of scope.
    if conn.get("ConnectionSchemaVersion") != 2:
        raise UnsupportedConnection(
            f"only ConnectionSchemaVersion 2 is supported, got {conn.get('ConnectionSchemaVersion')!r}")
    ctype = conn.get("ConnectionType")
    if ctype in _NATIVE:
        return _NATIVE[ctype]
    raise UnsupportedConnection(f"ConnectionType not supported: {ctype!r}")


def secret_arn(conn: dict) -> str | None:
    """The Secrets Manager ARN the connection authenticates with, if any."""
    src = conn.get("AuthenticationConfiguration") or {}
    return src.get("SecretArn") if src.get("AuthenticationType") in _SECRET_AUTH else None


def _authentication(conn: dict, dz_type: str) -> dict | None:
    src = conn.get("AuthenticationConfiguration") or {}
    auth_type = src.get("AuthenticationType")
    if auth_type == "OAUTH2":
        raise UnsupportedConnection("OAUTH2 connections need re-authorization")
    if auth_type == "IAM" and dz_type == "REDSHIFT":
        raise UnsupportedConnection("Redshift with IAM authentication is not supported")
    if auth_type not in _SECRET_AUTH:
        return None  # no auth, or IAM (execution role)
    if not src.get("SecretArn"):
        raise UnsupportedConnection(f"{auth_type} authentication without a SecretArn is not supported")
    out = {"authenticationType": auth_type, "secretArn": src["SecretArn"]}
    if src.get("KmsKeyArn"):
        out["kmsKeyArn"] = src["KmsKeyArn"]
    return out


def to_datazone_input(conn: dict, *, role_arn: str | None = None) -> dict:
    """Build CreateConnection props.glueProperties.glueConnectionInput.

    role_arn: the project's user role, written as the clone's ROLE_ARN (Glue
    requires one for V2 connections). The result shares no mutable state with `conn`.
    """
    dz_type = resolve_connection_type(conn)
    props = conn.get("ConnectionProperties") or {}
    inline = _CRED_KEYS & set(props)
    if inline:
        raise UnsupportedConnection(f"inline credential properties are not supported: {sorted(inline)}")
    auth = _authentication(conn, dz_type)

    out: dict = {
        "connectionType": dz_type,
        "connectionProperties": {k: v for k, v in props.items() if k != _ROLE_KEY},
        "validateCredentials": False,
    }
    if role_arn:
        out["connectionProperties"][_ROLE_KEY] = role_arn
    if "Description" in conn:
        out["description"] = conn["Description"]
    if auth:
        out["authenticationConfiguration"] = auth
    pcr = conn.get("PhysicalConnectionRequirements") or {}
    pcr_out = {dz: copy.deepcopy(pcr[g]) for g, dz in _PCR_MAP if pcr.get(g)}
    if pcr_out:
        out["physicalConnectionRequirements"] = pcr_out
    if conn.get("MatchCriteria"):
        out["matchCriteria"] = conn["MatchCriteria"][0][:10]
    if conn.get("CompatibleComputeEnvironments"):
        out["validateForComputeEnvironments"] = list(conn["CompatibleComputeEnvironments"])
    for g, dz in _PROPERTY_MAPS:
        if g in conn:
            out[dz] = dict(conn[g])
    return out
