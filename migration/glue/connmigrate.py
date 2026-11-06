"""Glue Studio connection -> SMUS project connection migration (AWS I/O).

Separate from `migrate.migrate_job`: that path never calls into this module.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace

from botocore.exceptions import ClientError

from migration.glue import connections, naming, secret_tags


class SourceConnectionNotFound(LookupError):
    """The named Glue connection does not exist."""


@dataclass(frozen=True)
class ConnectionPlan:
    source_name: str
    secret_arn: str | None
    glue_input: dict  # DataZone props.glueProperties.glueConnectionInput


def read_source_connection(glue, name: str) -> dict:
    """GetConnection with HidePassword=True: secret values are never fetched."""
    try:
        return glue.get_connection(Name=name, HidePassword=True)["Connection"]
    except glue.exceptions.EntityNotFoundException as e:
        raise SourceConnectionNotFound(f"Glue connection {name!r} not found") from e


def plan_connection(glue, name: str, *, role_arn: str | None = None) -> ConnectionPlan:
    conn = read_source_connection(glue, name)
    return ConnectionPlan(source_name=conn["Name"], secret_arn=connections.secret_arn(conn),
                          glue_input=connections.to_datazone_input(conn, role_arn=role_arn))


class ToolingEnvironmentNotFound(LookupError):
    """The project has no environment that exposes a user role (tooling environment)."""


@dataclass(frozen=True)
class MigratedConnection:
    source_name: str
    datazone_id: str
    datazone_name: str
    glue_name: str          # the Glue connection DataZone created (the clone)
    reused: bool            # True when an earlier run already created it
    tag_change: secret_tags.TagChange | None

    def to_json(self) -> dict:
        return {"sourceName": self.source_name, "datazoneId": self.datazone_id,
                "datazoneName": self.datazone_name, "glueName": self.glue_name, "reused": self.reused,
                "tagChange": self.tag_change.to_json() if self.tag_change else None}

@dataclass(frozen=True)
class ToolingEnvironment:
    id: str
    user_role_arn: str


def resolve_tooling_environment(dz, domain_id: str, project_id: str) -> ToolingEnvironment:
    """The project environment that carries the project user role.

    DataZone CreateConnection has no projectIdentifier; a connection belongs to the
    project through this environment.
    """
    token = None
    while True:
        kw = {"nextToken": token} if token else {}
        page = dz.list_environments(domainIdentifier=domain_id, projectIdentifier=project_id, **kw)
        for env in page.get("items", []):
            detail = dz.get_environment(domainIdentifier=domain_id, identifier=env["id"])
            for r in detail.get("provisionedResources") or []:
                if r.get("name") == "userRoleArn" and r.get("value"):
                    return ToolingEnvironment(env["id"], r["value"])
        token = page.get("nextToken")
        if not token:
            raise ToolingEnvironmentNotFound(f"no tooling environment in project {project_id}")


def _glue_name_of(conn: dict) -> str | None:
    for ep in conn.get("physicalEndpoints") or []:
        if ep.get("glueConnectionName"):
            return ep["glueConnectionName"]
    return None


def _status(conn: dict) -> tuple[str | None, str | None]:
    gp = (conn.get("props") or {}).get("glueProperties") or {}
    return gp.get("status"), gp.get("errorMessage")


def _project_connections(dz, domain_id: str, project_id: str) -> list:
    """Every connection summary in the project (ListConnections, all pages)."""
    out, token = [], None
    while True:
        kw = {"nextToken": token} if token else {}
        page = dz.list_connections(domainIdentifier=domain_id, projectIdentifier=project_id, **kw)
        out += page.get("items", [])
        token = page.get("nextToken")
        if not token:
            return out


def _get_live(dz, domain_id: str, cid: str) -> dict | None:
    """GetConnection, or None for a deleted connection ListConnections still returns
    (DataZone keeps listing it after its Glue connection is gone)."""
    try:
        conn = dz.get_connection(domainIdentifier=domain_id, identifier=cid)
        return None if _status(conn)[0] == "DELETED" else conn
    except dz.exceptions.ResourceNotFoundException:
        return None


def _glue_name_taken(glue, name: str) -> bool:
    try:
        glue.get_connection(Name=name, HidePassword=True)
        return True
    except glue.exceptions.EntityNotFoundException:
        return False


def _ready(conn: dict, label: str) -> dict:
    status, err = _status(conn)
    if status != "READY":
        raise RuntimeError(
            f"DataZone connection {conn['connectionId']} ({label!r}) is not READY "
            f"(observed state: {status or 'unknown'}; error: {err}); inspect the connection, "
            f"wait if provisioning is still active and retry when READY; "
            f"verify consumers before any manual cleanup")
    return conn


def _own_clone(dz, domain_id: str, conns: list, name: str) -> "MigratedConnection | None":
    """Avoid cloning a migration-created project connection a second time."""
    for c in conns:
        if name in (ep.get("glueConnectionName") for ep in c.get("physicalEndpoints") or []):
            conn = _get_live(dz, domain_id, c["connectionId"])
            if conn and naming.is_clone_description(conn.get("description")):
                _ready(conn, c["name"])
                return MigratedConnection(name, c["connectionId"], c["name"], name, True, None)
    return None


def _resolve_clone(dz, glue, domain_id: str, project_id: str, name: str,
                   conns: list) -> tuple[naming.ResolvedName, dict | None]:
    clone_name = naming.datazone_connection_name(name, project_id=project_id)
    existing, conn = {}, None
    for c in conns:
        if c["name"] != clone_name:
            continue
        candidate = _get_live(dz, domain_id, c["connectionId"])
        if candidate:
            conn = candidate
            desc = conn.get("description") or ""
            existing[clone_name] = name if naming.source_marker(name) in desc else None
            break
    if conn is None and _glue_name_taken(glue, clone_name):
        existing[clone_name] = None
    resolved = naming.resolve_datazone_connection_name(name, existing, project_id=project_id)
    if resolved.reuse:
        conn = _ready(conn, resolved.name)
    return resolved, conn


# Same mode the SMUS console sends. Without it DataZone also builds an Athena federated
# catalog (CloudFormation stack + Lambda), which the clone doesn't need.
_PROVISIONING = [{"classification": "ProvisioningConfiguration",
                  "properties": {"PROVISIONING_MODE": "GLUE_CONNECTION"}}]


def _description(glue_name: str) -> str:
    return f"{naming.source_marker(glue_name)} Migrated from Glue connection {glue_name}"[:128]


def wait_datazone_connection_ready(dz, domain_id: str, connection_id: str, *,
                                   timeout: float = 900, poll: float = 10) -> dict:
    """DataZone creates the Glue clone (and its catalog) asynchronously."""
    deadline = time.monotonic() + timeout
    while True:
        conn = dz.get_connection(domainIdentifier=domain_id, identifier=connection_id)
        status, err = _status(conn)
        if status == "READY":
            return conn
        if status and status.endswith("FAILED"):
            raise RuntimeError(f"DataZone connection {connection_id} {status}: {err}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"DataZone connection {connection_id} not READY after {timeout}s ({status})")
        time.sleep(poll)


def _delete_connection(dz, domain_id: str, connection_id: str, *,
                       timeout: float = 900, poll: float = 10) -> None:
    try:
        response = dz.delete_connection(domainIdentifier=domain_id, identifier=connection_id)
    except dz.exceptions.ResourceNotFoundException:
        return
    status = response.get("status")
    if status == "DELETED":
        return
    if status == "DELETE_FAILED":
        raise RuntimeError(f"DataZone connection {connection_id} DELETE_FAILED")
    deadline = time.monotonic() + timeout
    while True:
        conn = _get_live(dz, domain_id, connection_id)
        if conn is None:
            return
        status, err = _status(conn)
        if status == "DELETE_FAILED":
            raise RuntimeError(f"DataZone connection {connection_id} DELETE_FAILED: {err}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"DataZone connection {connection_id} not deleted after {timeout}s ({status})")
        time.sleep(poll)


def _undo_partial(err, dz, sm, domain_id, created, tag_change, *, poll: float = 10) -> None:
    """Best-effort cleanup after a failed create; never masks the original error."""
    steps = []
    if created:
        cid, state = created["connectionId"], "unknown"
        try:
            live = _get_live(dz, domain_id, cid)
            state = (_status(live)[0] or "unknown") if live else "DELETED"
        except (Exception, KeyboardInterrupt) as state_err:
            err.add_note(f"could not read DataZone connection {cid} cleanup state ({state_err})")
        # Only terminal creation failure rules out a READY clone another caller adopted.
        if state == "CREATE_FAILED":
            steps.append(("delete DataZone connection " + cid,
                          lambda: _delete_connection(dz, domain_id, cid, poll=poll)))
        elif state != "DELETED":
            err.add_note(
                f"DataZone connection {cid} retained (observed state: {state}); "
                f"it may be in use by another caller; verify consumers before manual cleanup")
    if tag_change and tag_change.prior:
        steps.append((f"restore tags on {tag_change.secret_arn} to {tag_change.prior}",
                      lambda: secret_tags.restore_secret_tags(sm, tag_change, error=err)))
    for what, step in steps:
        try:
            step()
            if isinstance(err, KeyboardInterrupt) and what.startswith("delete "):
                err.add_note(f"cleanup completed: {what}")
        except (Exception, KeyboardInterrupt) as cleanup_err:  # noqa: BLE001 - reported on the original error
            err.add_note(f"cleanup failed, do it manually: {what} ({cleanup_err})")


def migrate_connection(*, glue, sm, dz, domain_id: str, project_id: str, name: str,
                       shared_secret: bool = False, poll: float = 10) -> MigratedConnection:
    """Clone Glue connection `name` into the project. Idempotent; the source is untouched.

    Order matters: Glue validates secret access while DataZone creates the clone,
    so the secret is tagged BEFORE CreateConnection. Failed creates restore metadata;
    sharing grants and clones without confirmed CREATE_FAILED state are retained with
    manual cleanup guidance to protect concurrent users.
    """
    conns = _project_connections(dz, domain_id, project_id)
    own = _own_clone(dz, domain_id, conns, name)
    if own:
        arn = connections.secret_arn(read_source_connection(glue, name))
        change = secret_tags.tag_secret(sm, arn, domain_id=domain_id, project_id=project_id,
                                       shared=shared_secret) if arn else None
        return replace(own, tag_change=change)
    env = resolve_tooling_environment(dz, domain_id, project_id)
    plan = plan_connection(glue, name, role_arn=env.user_role_arn)
    resolved, conn = _resolve_clone(dz, glue, domain_id, project_id, name, conns)
    tag_change = None
    if plan.secret_arn:
        tag_change = secret_tags.tag_secret(sm, plan.secret_arn, domain_id=domain_id, project_id=project_id,
                                            shared=shared_secret)
    if resolved.reuse:
        return MigratedConnection(name, conn["connectionId"], resolved.name, _glue_name_of(conn),
                                  True, tag_change)
    created = None
    request = dict(
        domainIdentifier=domain_id, environmentIdentifier=env.id, name=resolved.name,
        description=_description(name),
        configurations=_PROVISIONING,
        # DataZone has been seen to name the clone after the DataZone connection
        # whatever is sent; send that name so both agree. The read-back wins.
        props={"glueProperties": {"glueConnectionInput": {"name": resolved.name, **plan.glue_input}}},
        # Replays share a token; a new attempt after cleanup must create a new connection.
        clientToken=uuid.uuid4().hex)
    try:
        created = dz.create_connection(**request)
        conn = wait_datazone_connection_ready(dz, domain_id, created["connectionId"], poll=poll)
    except (Exception, KeyboardInterrupt) as err:
        if created is None and (not isinstance(err, ClientError) or
                                err.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 500) >= 500):
            try:
                created = dz.create_connection(**request)
            except (Exception, KeyboardInterrupt) as recovery_err:
                err.add_note(
                    f"create outcome unknown; inspect owned DataZone connection "
                    f"{resolved.name!r} and verify consumers before manual cleanup "
                    f"(clientToken={request['clientToken']}; {recovery_err})")
        _undo_partial(err, dz, sm, domain_id, created, tag_change, poll=poll)
        raise
    return MigratedConnection(name, created["connectionId"], resolved.name, _glue_name_of(conn),
                              False, tag_change)


def migrate_connections(*, glue, sm, dz, names: list[str], domain_id: str,
                        project_id: str, apply: bool = False, shared_secret: bool = False) -> dict:
    """Clone a set of connections independently of job migration.

    Validate all inputs before creating anything. Completed clones are retained if
    a later create fails: they may already be in use, and reruns reuse them.
    """
    names = list(dict.fromkeys(names))
    result = {"applied": False, "connections": []}
    if not names:
        return result
    env = resolve_tooling_environment(dz, domain_id, project_id)
    plans = [plan_connection(glue, name, role_arn=env.user_role_arn) for name in names]
    conns = _project_connections(dz, domain_id, project_id)
    targets = set()
    for name, plan in zip(names, plans):
        if not _own_clone(dz, domain_id, conns, name):
            target = naming.datazone_connection_name(name, project_id=project_id)
            if target in targets:
                raise naming.ConnectionNameConflict(
                    f"multiple source connections resolve to target {target!r}")
            targets.add(target)
            _resolve_clone(dz, glue, domain_id, project_id, name, conns)
        secret_tags_to_add = {}
        if plan.secret_arn:
            tags = secret_tags._current_tags(sm, plan.secret_arn)
            secret_tags_to_add = secret_tags.plan_tags(
                tags, domain_id=domain_id, project_id=project_id, shared=shared_secret)
        result["connections"].append({
            "sourceName": plan.source_name, "glueConnectionInput": plan.glue_input,
            "secretArn": plan.secret_arn, "secretTagsToAdd": secret_tags_to_add})
    if not apply:
        return result
    result["connections"] = []
    for name in names:
        try:
            migrated = migrate_connection(glue=glue, sm=sm, dz=dz, domain_id=domain_id,
                                           project_id=project_id, name=name,
                                           shared_secret=shared_secret)
        except (Exception, KeyboardInterrupt) as err:
            if result["connections"]:
                kept = [c["glueName"] for c in result["connections"]]
                err.add_note(f"completed clones retained: {kept}; rerun to reuse them")
            raise
        result["connections"].append(migrated.to_json())
    result["applied"] = True
    return result
