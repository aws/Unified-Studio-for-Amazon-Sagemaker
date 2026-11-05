"""Auto-discover which Glue script jobs belong in which SMUS project, by role.

The feedback-driven driver on top of `migrate.migrate_job`:

  1. List every DataZone domain in the account (region-scoped).
  2. For each domain, list its projects.
  3. Resolve each project's execution role from its default IAM connection's
     environmentUserRole, using the SMUS toolkit's connection selection.
  4. List the account's Glue jobs; a job's `Role` (normalized to a full ARN) that
     equals a project's execution role identifies a possible target project.
  5. A role mapping to exactly one project => a match: migrate the job there.
     Zero projects => unmatched (left alone). Two or more => ambiguous (skipped).

This module is pure orchestration + pure logic: the matcher `plan_discovery` has
no AWS calls, so it is fully unit-testable, and the I/O helpers wrap paginated
DataZone/Glue reads. Execution (the actual migrate) is the CLI's job.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from botocore.exceptions import ClientError

from .datazone_resolve import resolve_project_iam_connection

_ROLE_ARN = re.compile(r"^arn:aws[\w-]*:iam::\d{12}:role/.+$")
_PERMISSION_ERRORS = {"AccessDeniedException", "AccessDenied", "UnauthorizedException"}
_LOG = logging.getLogger(__name__)


def normalize_role_arn(role: str, account: str, partition: str = "aws") -> str:
    """A Glue job's Role may be a bare name or a full ARN; return the full ARN.

    A bare name may include a path (e.g. `service-role/Foo`); it is preserved.
    """
    if role.startswith("arn:"):
        return role
    return f"arn:{partition}:iam::{account}:role/{role.lstrip('/')}"


# ---- AWS I/O (paginated reads) ----

def list_account_domains(dz) -> list[dict]:
    """Every AVAILABLE DataZone domain in the account/region (ListDomains, all pages)."""
    out, token = [], None
    while True:
        page = dz.list_domains(**({"nextToken": token} if token else {}))
        out += [d for d in page.get("items", []) if d.get("status") in (None, "AVAILABLE")]
        token = page.get("nextToken")
        if not token:
            return out


def list_domain_projects(dz, domain_id: str) -> list[dict]:
    """Every project in a domain (ListProjects, all pages)."""
    out, token = [], None
    while True:
        kw = {"domainIdentifier": domain_id}
        if token:
            kw["nextToken"] = token
        page = dz.list_projects(**kw)
        out += page.get("items", [])
        token = page.get("nextToken")
        if not token:
            return out


def resolve_project_role(dz, domain_id: str, project_id: str) -> str | None:
    """The default IAM connection's project execution role, if it is a role ARN."""
    connection = resolve_project_iam_connection(dz, domain_id, project_id)
    role = (connection or {}).get("environmentUserRole") or ""
    return role if _ROLE_ARN.fullmatch(role) else None


def list_glue_jobs(glue) -> list[dict]:
    """Every Glue job (get_jobs, all pages). Each item is the full job def."""
    out, token = [], None
    while True:
        page = glue.get_jobs(**({"NextToken": token} if token else {}))
        out += page.get("Jobs", [])
        token = page.get("NextToken")
        if not token:
            return out


# ---- pure data model + matcher (no AWS calls) ----

@dataclass(frozen=True)
class ProjectRole:
    domain_id: str
    project_id: str
    project_name: str
    role_arn: str  # the project execution role


@dataclass(frozen=True)
class JobMatch:
    job_name: str
    job_role_arn: str
    domain_id: str
    project_id: str
    project_name: str


@dataclass(frozen=True)
class AmbiguousJob:
    job_name: str
    job_role_arn: str
    # every (domain, project) whose execution role equals this job's role
    projects: tuple[tuple[str, str], ...]


@dataclass
class DiscoveryPlan:
    project_roles: list[ProjectRole] = field(default_factory=list)
    matched: list[JobMatch] = field(default_factory=list)
    unmatched: list[dict] = field(default_factory=list)   # {jobName, jobRoleArn}
    unsupported: list[str] = field(default_factory=list)
    ambiguous: list[AmbiguousJob] = field(default_factory=list)
    projects_without_role: list[dict] = field(default_factory=list)  # {domainId, projectId, projectName}

    def to_json(self) -> dict:
        return {
            "projectRoles": [
                {"domainId": r.domain_id, "projectId": r.project_id,
                 "projectName": r.project_name, "roleArn": r.role_arn}
                for r in self.project_roles],
            "matched": [
                {"jobName": m.job_name, "jobRoleArn": m.job_role_arn, "domainId": m.domain_id,
                 "projectId": m.project_id, "projectName": m.project_name}
                for m in self.matched],
            "unmatched": list(self.unmatched),
            "unsupported": list(self.unsupported),
            "ambiguous": [
                {"jobName": a.job_name, "jobRoleArn": a.job_role_arn,
                 "projects": [{"domainId": d, "projectId": p} for d, p in a.projects]}
                for a in self.ambiguous],
            "projectsWithoutRole": list(self.projects_without_role),
        }


def build_role_index(project_roles: list[ProjectRole]) -> dict[str, list[ProjectRole]]:
    """Execution role ARN -> the project(s) that run as it.

    More than one project per ARN makes a job ambiguous.
    """
    index: dict[str, list[ProjectRole]] = {}
    for pr in project_roles:
        index.setdefault(pr.role_arn, []).append(pr)
    return index


def plan_discovery(project_roles: list[ProjectRole], jobs: list[dict], *,
                   account: str, partition: str = "aws") -> DiscoveryPlan:
    """Pure matcher: bucket jobs into matched / unmatched / ambiguous by role.

    jobs: Full Glue job definitions. Only Python script ETL/shell jobs are matched.
    A job with no Role is treated as unmatched.
    """
    index = build_role_index(project_roles)
    plan = DiscoveryPlan(project_roles=list(project_roles))
    for job in jobs:
        name = job.get("Name")
        command = job.get("Command") or {}
        arguments = {**(job.get("DefaultArguments") or {}),
                     **(job.get("NonOverridableArguments") or {})}
        if (command.get("Name") not in ("glueetl", "pythonshell")
                or not (command.get("ScriptLocation") or "").endswith(".py")
                or arguments.get("--job-language", "python") != "python"
                or job.get("CodeGenConfigurationNodes")
                or job.get("JobMode", "SCRIPT") != "SCRIPT"):
            plan.unsupported.append(name)
            continue
        raw_role = job.get("Role")
        if not raw_role:
            plan.unmatched.append({"jobName": name, "jobRoleArn": None})
            continue
        role_arn = normalize_role_arn(raw_role, account, partition)
        targets = index.get(role_arn, [])
        if not targets:
            plan.unmatched.append({"jobName": name, "jobRoleArn": role_arn})
        elif len(targets) == 1:
            t = targets[0]
            plan.matched.append(JobMatch(name, role_arn, t.domain_id, t.project_id, t.project_name))
        else:
            plan.ambiguous.append(AmbiguousJob(
                name, role_arn, tuple((t.domain_id, t.project_id) for t in targets)))
    return plan


def collect_project_roles(dz, *, domain_filter: str | None = None,
                          project_filter: str | None = None) -> tuple[list[ProjectRole], list[dict]]:
    """Enumerate accessible domains/projects and resolve their execution roles.

    Returns (project_roles, projects_without_role). Optional filters narrow to a
    single domain and/or project. Permission denials exclude the entire domain,
    including partial results already collected from it; other errors propagate.
    """
    project_roles: list[ProjectRole] = []
    without: list[dict] = []
    try:
        domains = list_account_domains(dz)
    except ClientError as error:
        code = error.response["Error"]["Code"]
        if code not in _PERMISSION_ERRORS:
            raise
        _LOG.warning("Skipping domain discovery: %s on ListDomains", code)
        return [], []
    if domain_filter:
        domains = [d for d in domains if d.get("id") == domain_filter]
    for domain in domains:
        domain_id = domain.get("id")
        if not domain_id:
            continue
        domain_roles, domain_without = [], []
        try:
            projects = list_domain_projects(dz, domain_id)
            if project_filter:
                projects = [p for p in projects if p.get("id") == project_filter]
            for project in projects:
                project_id = project.get("id")
                project_name = project.get("name") or project_id
                if not project_id:
                    continue
                role = resolve_project_role(dz, domain_id, project_id)
                if role:
                    domain_roles.append(ProjectRole(domain_id, project_id, project_name, role))
                else:
                    domain_without.append({"domainId": domain_id, "projectId": project_id,
                                           "projectName": project_name})
        except ClientError as error:
            code = error.response["Error"]["Code"]
            if code not in _PERMISSION_ERRORS:
                raise
            _LOG.warning("Skipping domain %s: %s on %s", domain_id, code, error.operation_name)
            continue
        project_roles.extend(domain_roles)
        without.extend(domain_without)
    return project_roles, without
