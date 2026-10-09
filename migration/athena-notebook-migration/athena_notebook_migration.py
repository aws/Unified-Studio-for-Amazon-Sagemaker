#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with
# the License. A copy of the License is located at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions
# and limitations under the License.

"""
py:module: athena_notebook_migration

:synopsis: Migrates notebooks from Amazon Athena PySpark engine version 3 workgroups to Amazon SageMaker Unified Studio
:platform: macOS, Linux, Windows
"""

import argparse
import fnmatch
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import unquote

import boto3

log = logging.getLogger("athena2smus")

# AWS error codes that indicate transient throttling (safe to retry).
THROTTLE_CODES = {"ThrottlingException", "TooManyRequestsException",
                  "RequestLimitExceeded", "ThrottledException"}

# AWS error codes that indicate IAM permission issues (not retryable).
ACCESS_DENIED_CODES = {"AccessDeniedException", "UnauthorizedOperation",
                       "AccessDenied", "InvalidAccessKeyId"}

CREDENTIAL_ERROR_CODES = {"ExpiredToken", "ExpiredTokenException",
                          "UnrecognizedClientException", "InvalidClientTokenId"}

# Documentation link shown in the migration banner injected at the top of each notebook.
MIGRATION_DOC_URL = "https://docs.aws.amazon.com/athena/latest/ug/notebooks-spark-migration-v3-to-v35.html"

# Prompt users paste into the SMUS Data Agent chat to start the interactive upgrade.
UPGRADE_PROMPT = "Can you upgrade this Athena notebook to SMUS Data notebook?"

# Maximum seconds to wait for a single notebook import to reach SUCCESS.
DEFAULT_MAX_WAIT = 120

# Default poll interval in seconds when waiting for notebook import.
DEFAULT_POLL_INTERVAL = 4

# Upper bound for --concurrency.
MAX_CONCURRENCY = 10

# Plan and summary table column caps; longer names are shortened with an ellipsis (full names are in the report).
TABLE_MAX_WORKGROUP_W = 40
TABLE_MAX_NOTEBOOK_W = 50
TABLE_MAX_PROJECT_W = 24

# Plan actions that result in an import (everything else is a skip).
MIGRATE_ACTIONS = ("migrate", "overwrite (exists)", "migrate (missing in project)")

# Box-drawing characters for CX output
_THICK = "\u2501"  # ━
_THIN = "\u2500"   # ─
_ARROW = "\u2192"  # →
_CHECK = "\u2713"  # ✓
_WARN = "\u26a0"   # ⚠
_CROSS = "\u2717"  # ✗
_HOOK = "\u21b3"   # ↳
_ELLIPSIS = "\u2026"  # …
_BOX_TL = "\u250c"  # ┌
_BOX_TR = "\u2510"  # ┐
_BOX_BL = "\u2514"  # └
_BOX_BR = "\u2518"  # ┘
_BOX_V = "\u2502"   # │
_BOX_H = "\u2500"   # ─

_SPINNER = "\u23f3"  # ⏳
W = 80  # Console width


# --------------------------------------------------------------------------- #
# Console Output (CX) - clean, customer-facing
# --------------------------------------------------------------------------- #

def cx(msg=""):
    """Print a clean line to console (no timestamp, no level)."""
    print(msg)


def cx_thick_bar():
    cx(_THICK * W)


def cx_thin_bar():
    cx("  " + _THIN * (W - 4))


def cx_section_bar():
    cx(_THIN * W)


def cx_banner(title, subtitle=None):
    cx_thick_bar()
    cx(f"  {title}")
    if subtitle:
        cx(f"  {subtitle}")
    cx_thick_bar()


def cx_kv(key, value, indent=2):
    cx(f"{' ' * indent}{key + ':':<22}{value}")


def col_width(header, values, minimum, maximum=None):
    """Table column width: the widest value (header included), at least minimum, at most maximum."""
    w = max([minimum, len(header)] + [len(v) for v in values])
    return min(w, maximum) if maximum else w


def fit(value, width):
    """Shortens value to width, ending in an ellipsis when it doesn't fit."""
    return value if len(value) <= width else value[:width - 1] + _ELLIPSIS


def cx_step(n, total, label):
    cx(f"\n{_THIN * W}")
    cx(f"  Step {n}/{total}  {label}")
    cx(_THIN * W)


def cx_verdict(symbol, label, detail):
    cx(f"\n{_THICK * W}")
    line = f"  {symbol} {label}"
    if detail:
        line += f" {_THIN * 2} {detail}"
    cx(line)
    cx(_THICK * W)


def cx_progress(text, done=False):
    """Print a single-line progress indicator. Overwrites the current line when not done."""
    # ANSI escape: \033[K clears from cursor to end of line — eliminates ghost chars
    # regardless of terminal width or previous line length.
    clear_eol = "\033[K"
    if done:
        # Final state: print with newline
        sys.stdout.write(f"\r{text}{clear_eol}\n")
        sys.stdout.flush()
    else:
        # In-progress: overwrite current line (no newline)
        sys.stdout.write(f"\r{text}{clear_eol}")
        sys.stdout.flush()


def cx_box(lines, indent=5):
    """Print lines inside a unicode box."""
    max_w = max(len(l) for l in lines) if lines else 40
    cx(f"{' ' * indent}{_BOX_TL}{_BOX_H * (max_w + 2)}{_BOX_TR}")
    for l in lines:
        cx(f"{' ' * indent}{_BOX_V} {l.ljust(max_w)} {_BOX_V}")
    cx(f"{' ' * indent}{_BOX_BL}{_BOX_H * (max_w + 2)}{_BOX_BR}")


# --------------------------------------------------------------------------- #
# Logging / Error Formatting
# --------------------------------------------------------------------------- #

def set_logging(level_name, log_file=None):
    """
    Sets up dual logging:
    - File handler: verbose with timestamps (for debugging)
    - Console (stderr): minimal, only for warnings/errors not covered by CX output

    The CX output goes to stdout via cx() and is NOT part of the logging system.
    """
    level = getattr(logging, str(level_name).upper(), logging.INFO)
    logging.addLevelName(logging.WARNING, "WARN")
    fmt = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # File handler: captures everything at the requested level
    log.setLevel(level)
    log.handlers[:] = []

    if log_file:
        # UTF-8 regardless of OS locale, so non-ASCII notebook names log correctly on Windows (cp1252).
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(level)
        log.handlers.append(fh)

    # Console handler on stderr: only ERROR+ (CX output handles the rest on stdout)
    ch = logging.StreamHandler(sys.stderr)
    ch.setFormatter(fmt)
    # CRITICAL = never show on console; CX output handles all user-facing messaging
    ch.setLevel(logging.CRITICAL)
    log.handlers.append(ch)

    log.propagate = False


def format_aws_error(e):
    """Formats a botocore ClientError into a human-readable single-line string."""
    resp = getattr(e, "response", None) or {}
    err = resp.get("Error", {}) if isinstance(resp, dict) else {}
    meta = resp.get("ResponseMetadata", {}) if isinstance(resp, dict) else {}
    code = err.get("Code") or type(e).__name__
    message = err.get("Message") or "(service returned no message)"
    parts = [code]
    op = getattr(e, "operation_name", None)
    if op:
        parts.append(f"operation={op}")
    if meta.get("HTTPStatusCode"):
        parts.append(f"http={meta['HTTPStatusCode']}")
    if meta.get("RequestId"):
        parts.append(f"requestId={meta['RequestId']}")
    if code in ("ExpiredTokenException", "UnrecognizedClientException", "InvalidClientTokenId"):
        message += " (refresh your AWS credentials)"
    return f"{' | '.join(parts)} :: {message}"


def error_code(e):
    """Extracts the AWS error code from a botocore exception."""
    return ((getattr(e, "response", None) or {}).get("Error", {}) or {}).get("Code", type(e).__name__)


def with_retry(fn, *args, _tries=6, _base=1.6, **kwargs):
    """Executes an AWS API call with automatic retry on throttling."""
    for i in range(_tries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if error_code(e) in THROTTLE_CODES and i < _tries - 1:
                wait = _base ** i
                log.debug("Throttled on %s; retry %d in %.1fs", getattr(fn, "__name__", fn), i + 1, wait)
                time.sleep(wait)
                continue
            raise


# --------------------------------------------------------------------------- #
# AWS Session Builder
# --------------------------------------------------------------------------- #

def build_session(region, profile=None, role_arn=None):
    """Creates a boto3 Session, optionally assuming a cross-account role."""
    base = boto3.Session(profile_name=profile) if profile else boto3.Session()
    if role_arn:
        creds = base.client("sts", region_name=region).assume_role(
            RoleArn=role_arn, RoleSessionName="athena-smus-migrate")["Credentials"]
        return boto3.Session(aws_access_key_id=creds["AccessKeyId"],
                             aws_secret_access_key=creds["SecretAccessKey"],
                             aws_session_token=creds["SessionToken"], region_name=region)
    return boto3.Session(profile_name=profile, region_name=region) if profile \
        else boto3.Session(region_name=region)


# --------------------------------------------------------------------------- #
# AWS Service Helpers
# --------------------------------------------------------------------------- #

def project_s3_base(dz, domain_id, project_id):
    """Resolves the shared S3 staging path for a SMUS project."""
    envs = with_retry(dz.list_environments, domainIdentifier=domain_id,
                      projectIdentifier=project_id).get("items", [])
    envs.sort(key=lambda e: 0 if e.get("status") == "ACTIVE" else 1)
    fallback = None
    for env in envs:
        detail = with_retry(dz.get_environment, domainIdentifier=domain_id, identifier=env["id"])
        res = {r.get("name"): r.get("value") for r in detail.get("provisionedResources", [])}
        for k in ("s3BucketPath", "nonGitProjectRepositoryLocation"):
            if res.get(k):
                return res[k].rstrip("/")
        if not fallback and res.get("s3BucketArn"):
            fallback = "s3://" + res["s3BucketArn"].split(":::", 1)[-1].strip("/") + "/shared"
    return fallback


def project_athena_workgroup(dz, domain_id, project_id):
    """Resolves the Athena Spark workgroup for a SMUS project via its connections.

    The Spark workgroup lives in the project's Spark connection (type SPARK_CONNECT,
    typically named 'serverless.spark') under props.athenaProperties.workgroupName --
    NOT in the environment's provisionedResources. Returns the Spark workgroup name,
    or None if there is no Spark connection.
    """
    try:
        conns, token = [], None
        while True:
            kwargs = {"domainIdentifier": domain_id, "projectIdentifier": project_id}
            if token:
                kwargs["nextToken"] = token
            resp = with_retry(dz.list_connections, **kwargs)
            conns += resp.get("items", [])
            token = resp.get("nextToken")
            if not token:
                break
    except Exception as e:
        log.debug("Could not list connections for workgroup lookup: %s", format_aws_error(e))
        return None

    # Prefer a Spark-Connect connection, then any SPARK type, then a *.spark name.
    def _rank(c):
        t, n = (c.get("type") or ""), (c.get("name") or "")
        if t == "SPARK_CONNECT":
            return 0
        if t == "SPARK":
            return 1
        if n.endswith(".spark"):
            return 2
        return 9
    spark_conns = sorted((c for c in conns if _rank(c) < 9), key=_rank)

    for c in spark_conns:
        cid = c.get("connectionId") or c.get("id")
        if not cid:
            continue
        try:
            detail = with_retry(dz.get_connection, domainIdentifier=domain_id, identifier=cid)
        except Exception as e:
            log.debug("get_connection %s failed during workgroup lookup: %s", cid, format_aws_error(e))
            continue
        athena_props = (detail.get("props") or {}).get("athenaProperties") or {}
        wg = athena_props.get("workgroupName") or athena_props.get("workGroupName")
        if wg:
            return wg.rsplit("/", 1)[-1]
    return None


def list_notebooks(athena, workgroup):
    """Lists all notebook metadata in an Athena workgroup (handles pagination)."""
    out, token = [], None
    while True:
        kwargs = {"WorkGroup": workgroup}
        if token:
            kwargs["NextToken"] = token
        resp = with_retry(athena.list_notebook_metadata, **kwargs)
        out += resp.get("NotebookMetadataList", [])
        token = resp.get("NextToken")
        if not token:
            break
    return out


def all_spark_v3_workgroups(athena):
    """Auto-discovers all PySpark engine version 3 workgroups in the account."""
    names, token = [], None
    while True:
        try:
            resp = with_retry(athena.list_work_groups, **({"NextToken": token} if token else {}))
        except Exception as e:
            if error_code(e) in ACCESS_DENIED_CODES:
                log.warning("Cannot list workgroups: %s", format_aws_error(e))
                return names
            raise
        for wg in resp.get("WorkGroups", []):
            eff = wg.get("EngineVersion", {}).get("EffectiveEngineVersion", "")
            if "PySpark" in eff and eff.rstrip().endswith("3"):
                names.append(wg["Name"])
        token = resp.get("NextToken")
        if not token:
            break
    return names


def accessible_workgroups(athena, workgroups):
    """Filters a list of workgroups to only those the IAM role can access."""
    accessible, skipped = [], []
    for wg in workgroups:
        try:
            with_retry(athena.list_notebook_metadata, WorkGroup=wg, MaxResults=1)
            accessible.append(wg)
        except Exception as e:
            code = error_code(e)
            if code in ACCESS_DENIED_CODES:
                log.warning("Skipping workgroup '%s': %s", wg, format_aws_error(e))
                skipped.append(wg)
            elif code == "InvalidRequestException":
                log.warning("Skipping workgroup '%s': %s", wg, format_aws_error(e))
                skipped.append(wg)
            else:
                accessible.append(wg)
    return accessible, skipped


def existing_notebooks(dz, domain_id, project_id):
    """Lists notebooks already in a SMUS project (for duplicate detection)."""
    out, token = {}, None
    while True:
        kwargs = {"domainIdentifier": domain_id, "owningProjectIdentifier": project_id}
        if token:
            kwargs["nextToken"] = token
        resp = with_retry(dz.list_notebooks, **kwargs)
        for nb in resp.get("items", []):
            if nb.get("name"):
                out.setdefault(nb["name"], []).append(nb.get("id", ""))
        token = resp.get("nextToken")
        if not token:
            break
    return out


# --------------------------------------------------------------------------- #
# Execution-Role Permission Comparison
# --------------------------------------------------------------------------- #

def resolve_athena_role(athena, workgroup):
    """Resolves the execution role ARN configured on an Athena Spark workgroup."""
    cfg = with_retry(athena.get_work_group, WorkGroup=workgroup)["WorkGroup"].get("Configuration", {})
    return cfg.get("ExecutionRole")


def resolve_smus_role(dz, domain_id, project_id):
    """Best-effort resolution of the SMUS project environment's IAM execution role ARN."""
    roles = set()
    pat = re.compile(r"arn:aws:iam::\d+:role/[A-Za-z0-9_+=,.@/-]+")
    try:
        envs = with_retry(dz.list_environments, domainIdentifier=domain_id,
                          projectIdentifier=project_id).get("items", [])
    except Exception as e:
        log.warning("Could not list SMUS environments: %s", format_aws_error(e))
        return None
    for env in envs:
        try:
            detail = with_retry(dz.get_environment, domainIdentifier=domain_id, identifier=env["id"])
            roles.update(pat.findall(json.dumps(detail, default=str)))
        except Exception as e:
            log.debug("get_environment %s failed: %s", env.get("id"), format_aws_error(e))
    for r in sorted(roles):
        if "SageMaker" in r or "execution" in r.lower():
            return r
    return sorted(roles)[0] if roles else None


def _policy_doc(d):
    """Normalizes an IAM policy document to a dict."""
    if isinstance(d, dict):
        return d
    try:
        return json.loads(unquote(d))
    except Exception:
        return {"Statement": []}


def role_grants(iam, role_name):
    """Collects Allow (action, resource) grants from a role's policies."""
    grants = set()

    def _collect(doc):
        stmts = doc.get("Statement", [])
        if isinstance(stmts, dict):
            stmts = [stmts]
        for s in stmts:
            if s.get("Effect") != "Allow":
                continue
            actions = s.get("Action", [])
            actions = actions if isinstance(actions, list) else [actions]
            resources = s.get("Resource", ["*"])
            resources = resources if isinstance(resources, list) else [resources]
            for a in actions:
                for r in resources:
                    grants.add((a, r))

    for pn in with_retry(iam.list_role_policies, RoleName=role_name).get("PolicyNames", []):
        doc = _policy_doc(with_retry(iam.get_role_policy, RoleName=role_name, PolicyName=pn)["PolicyDocument"])
        _collect(doc)
    for ap in with_retry(iam.list_attached_role_policies, RoleName=role_name).get("AttachedPolicies", []):
        arn = ap["PolicyArn"]
        ver = with_retry(iam.get_policy, PolicyArn=arn)["Policy"]["DefaultVersionId"]
        doc = _policy_doc(with_retry(iam.get_policy_version, PolicyArn=arn,
                                     VersionId=ver)["PolicyVersion"]["Document"])
        _collect(doc)
    return grants


def _covered(action, resource, grants):
    """True if (action, resource) is covered by any Allow grant."""
    a = action.lower()
    for ga, gr in grants:
        if (ga == "*" or fnmatch.fnmatchcase(a, ga.lower())) and \
                (gr == "*" or fnmatch.fnmatchcase(resource, gr)):
            return True
    return False


_SOURCE_ONLY_RE = re.compile(r"athena:.*(Calculation|Session|Notebook|WorkGroup)", re.I)


def evaluate_role_gap(src_iam, dst_iam, source_role_arn, smus_role_arn, src_cache=None, smus_cache=None):
    """Computes permission gaps between Athena workgroup role and SMUS project role."""
    src_cache = src_cache if src_cache is not None else {}
    smus_cache = smus_cache if smus_cache is not None else {}
    if not source_role_arn or not smus_role_arn:
        return {"status": "unresolved", "missing": [], "broad": [],
                "note": ("source Athena execution role not resolved" if not source_role_arn
                         else "SMUS project execution role not resolved")}
    try:
        if source_role_arn not in src_cache:
            src_cache[source_role_arn] = role_grants(src_iam, source_role_arn.split("/")[-1])
        if smus_role_arn not in smus_cache:
            smus_cache[smus_role_arn] = role_grants(dst_iam, smus_role_arn.split("/")[-1])
    except Exception as e:
        note = ("missing IAM read permission (needs iam:GetRolePolicy, ListRolePolicies, "
                "ListAttachedRolePolicies, GetPolicy, GetPolicyVersion)"
                if error_code(e) in ACCESS_DENIED_CODES else format_aws_error(e))
        return {"status": "error", "missing": [], "broad": [], "note": note}
    src_grants, smus_grants = src_cache[source_role_arn], smus_cache[smus_role_arn]
    missing, broad = [], []
    for a, r in sorted(src_grants):
        if _SOURCE_ONLY_RE.search(a):
            continue
        if _covered(a, r, smus_grants):
            continue
        (broad if r == "*" else missing).append((a, r))
    return {"status": "gaps" if missing else "ok", "missing": missing, "broad": broad, "note": ""}


def render_role_check_cx(records, region):
    """
    Renders the execution-role permission check as clean CX output.
    Returns (total_gaps, remediation_commands_list).
    """
    role_gaps = {}
    total = 0
    for rec in records:
        if rec["status"] == "gaps":
            total += len(rec["missing"])
            g = role_gaps.setdefault(rec["smus_role"], {"missing": set(), "wgs": set()})
            g["missing"].update(rec["missing"])
            g["wgs"].add(rec["workgroup"])
            g.setdefault("source_roles", set()).add(rec.get("source_role") or "")

    if not role_gaps:
        cx(f"  {_CHECK}  Execution roles: no permission gaps detected")
        log.info("Role check PASS - no gaps found")
    else:
        for smus_role, g in role_gaps.items():
            role_name = smus_role.split("/")[-1]
            wg_list = ", ".join(sorted(g["wgs"]))
            src_roles = sorted(r.split("/")[-1] for r in g.get("source_roles", set()) if r)
            src_display = ", ".join(src_roles) if src_roles else "(unknown)"
            actions = sorted({a for a, _ in g["missing"]})
            resources = sorted({r for _, r in g["missing"]})
            cx(f"\n  {_WARN}  Additional permissions required for SMUS project execution role ({role_name})")
            cx(f"")
            cx(f"     The Athena workgroup execution role ({src_display}) used by")
            cx(f"     workgroup(s) {wg_list} has the following permissions that the")
            cx(f"     SMUS project execution role does not:")
            cx(f"")
            cx(f"     Missing actions:")
            for a in actions:
                cx(f"       {_THIN} {a}")
            cx(f"     On resources:")
            for r in resources:
                cx(f"       {_THIN} {r}")
            cx(f"")
            # Remediation command shown inline right here
            cx(f"")
            cx(f"     To fix, run the following command (as the SMUS project admin):")
            # Build and show the command inline in Step 1
            remediation_cmd = build_remediation_commands({smus_role: g})
            for cmd in remediation_cmd:
                cx("")
                cx_box(cmd["lines"])
            cx(f"")
            cx(f"     (Optional: you can fix these permissions now or after migration)")
            log.info("SMUS role %s missing %d permissions for workgroup(s): %s",
                     role_name, len(g["missing"]), wg_list)

    # Log the detailed comparison to file
    for rec in records:
        log.info("Role check: wg=%s project=%s src=%s smus=%s status=%s missing=%d",
                 rec["workgroup"], rec["project"], rec.get("source_role", "-"),
                 rec.get("smus_role", "-"), rec["status"], len(rec.get("missing", [])))

    return total, role_gaps


def build_remediation_commands(role_gaps):
    """Builds the put-role-policy commands for CX output."""
    commands = []
    for smus_role, g in role_gaps.items():
        role_name = smus_role.split("/")[-1]
        account = smus_role.split(":")[4] if smus_role.count(":") >= 4 else "<account>"
        actions = sorted({a for a, _ in g["missing"]})
        resources = sorted({r for _, r in g["missing"]})
        policy = {"Version": "2012-10-17",
                  "Statement": [{"Sid": "AthenaSMUSMigratedNotebookAccess", "Effect": "Allow",
                                 "Action": actions, "Resource": resources}]}
        def _json_list(key, values, last=False):
            # One value per line, so the box grows down rather than across.
            items = [f'        {json.dumps(v)}{"," if i < len(values) - 1 else ""}' for i, v in enumerate(values)]
            return [f'      "{key}": ['] + items + [f'      ]{"" if last else ","}']

        # Format the command nicely for the box
        cmd_lines = [
            f"aws iam put-role-policy \\",
            f"  --role-name {role_name} \\",
            f"  --policy-name athena-smus-migration-access \\",
            f"  --policy-document '{{",
            f'    "Version": "2012-10-17",',
            f'    "Statement": [{{',
            f'      "Sid": "AthenaSMUSMigratedNotebookAccess",',
            f'      "Effect": "Allow",',
            *_json_list("Action", actions),
            *_json_list("Resource", resources, last=True),
            f"    }}]",
            f"  }}'",
        ]
        commands.append({"role_name": role_name, "account": account, "lines": cmd_lines})
    return commands


# --------------------------------------------------------------------------- #
# Report Row Builder & Writers
# --------------------------------------------------------------------------- #

def _row(project_id, wg, name, athena_id, s3_uri, smus_id, status, detail="", duration_s=0):
    """Creates a standardized result row for the migration report."""
    return {"project_id": project_id, "workgroup": wg, "notebook_name": name,
            "athena_notebook_id": athena_id, "s3_uri": s3_uri, "smus_notebook_id": smus_id,
            "status": status, "detail": detail, "duration_s": duration_s}


def write_json(path, meta, rows):
    """Writes the structured JSON migration report atomically (temp file + rename)."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({**meta, "notebooks": rows}, f, indent=2, default=str)
    os.replace(tmp, path)
    log.debug("JSON report: %s", path)


def write_reports(base_path, meta, rows):
    """Writes all report formats."""
    write_json(base_path + ".json", meta, rows)


class IncrementalReport:
    """Thread-safe report rewritten after every notebook, so --resume works after an interrupted run."""

    def __init__(self, base_path, meta):
        self.base_path = base_path
        self.meta = {**meta, "complete": False}
        self.rows = []
        self._lock = threading.Lock()

    def add(self, row):
        with self._lock:
            self.rows.append(row)
            self._flush()

    def finish(self, extra_meta, complete=True):
        with self._lock:
            self.meta.update(extra_meta)
            self.meta["complete"] = complete
            self._flush()

    def _flush(self):
        try:
            write_reports(self.base_path, self.meta, self.rows)
        except OSError as e:
            log.warning("Could not write report %s.json: %s", self.base_path, e)


# --------------------------------------------------------------------------- #
# Per-Notebook Migration (thread-safe)
# --------------------------------------------------------------------------- #

def clear_notebook_outputs(payload):
    """Strips cell outputs and execution counts from an exported .ipynb payload."""
    try:
        nb = json.loads(payload)
    except Exception:
        return payload
    for c in nb.get("cells", []):
        if c.get("cell_type") == "code":
            c["outputs"] = []
            c["execution_count"] = None
        else:
            c.pop("outputs", None)
            c.pop("execution_count", None)
    return json.dumps(nb)


_SQL_MAGIC_RE = re.compile(r"^\s*%%sql\b[^\n]*\n?(?P<body>.*)$", re.DOTALL)


def convert_sql_magic_cells(payload):
    """Rewrites `%%sql` cell-magic code cells to `spark.sql(\"\"\"...\"\"\").show()`.

    Only whole-cell `%%sql` magics are converted (the cell magic must be the first
    line). Cells whose query contains a triple-quote are left unchanged to avoid
    producing broken Python. Returns (payload, converted_count).
    """
    try:
        notebook = json.loads(payload)
    except Exception:
        return payload, 0
    converted = 0
    for c in notebook.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        src = c.get("source", "")
        text = "".join(src) if isinstance(src, list) else src
        m = _SQL_MAGIC_RE.match(text)
        if not m:
            continue
        query = m.group("body").strip()
        if not query or '"""' in query:
            continue
        new_text = f'spark.sql("""\n{query}\n""").show()'
        # Store as a list of line-terminated strings, per nbformat convention.
        c["source"] = [ln + "\n" for ln in new_text.split("\n")[:-1]] + [new_text.split("\n")[-1]]
        converted += 1
    return json.dumps(notebook), converted


def prepend_migration_banner(payload, wg, project, nid, smus_workgroup=None):
    """Inserts a markdown banner cell at the top of an exported .ipynb payload."""
    try:
        notebook = json.loads(payload)
    except Exception:
        return payload
    migrated_on = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "### Imported from Amazon Athena to SageMaker Unified Studio\n",
        "\n",
        "This notebook was imported from Amazon Athena. Review and\n",
        "upgrade it with the Data Agent before running it in SMUS.\n",
        "\n",
        "#### Notebook details\n",
        f"- **Source Athena workgroup:** `{wg}`\n",
        f"- **Target SMUS project:** `{project}`\n",
        f"- **SMUS Athena workgroup:** `{smus_workgroup or 'n/a'}`\n",
        f"- **Source notebook ID:** `{nid}`\n",
        f"- **Migrated on:** {migrated_on}\n",
        "\n",
        "**Documentation:** [Migration & upgrade guide](" + MIGRATION_DOC_URL + ")\n",
        "\n",
        "#### Next step\n",
        "Paste a prompt like the one below (e.g.) into the Data Agent chat,\n",
        "then continue interactively:\n",
        "\n",
        "```\n",
        f"{UPGRADE_PROMPT}\n",
        "```",
    ]
    banner = {"cell_type": "markdown", "metadata": {"tags": ["athena-smus-migration-banner"]},
              "source": lines}
    notebook.setdefault("cells", []).insert(0, banner)
    return json.dumps(notebook)


def migrate_one(clients, domain, project, base, wg, nb, opts, existing, resume_done, counter=None,
                smus_workgroup=None):
    """
    Migrates a single notebook: export -> stage -> import -> verify.
    Returns a result row dict.
    """
    athena, dz, s3 = clients
    nid = nb["NotebookId"]
    name = nb.get("Name", nid)
    bucket, _, prefix = base.replace("s3://", "").partition("/")
    key = "/".join(x for x in [prefix, "athena-migration", wg, f"{nid}.ipynb"] if x)
    uri = f"s3://{bucket}/{key}"

    # Progress prefix for CX output
    px = ""
    if counter:
        px = f"  [{counter[0]:>{len(str(counter[1]))}}/{counter[1]}] "
        counter[0] += 1
    
    dots = "." * max(1, 44 - len(name))

    existing_ids = existing.get(name, [])
    if (wg, nid) in resume_done:
        log.info("[%s] %s: SKIP (already migrated per --resume)", wg, name)
        return _row(project, wg, name, nid, uri, resume_done[(wg, nid)], "SKIPPED_RESUME")

    if existing_ids and not opts["overwrite"]:
        log.info("[%s] %s: SKIP (already in project as %s)", wg, name, existing_ids[0])
        return _row(project, wg, name, nid, "", existing_ids[0], "SKIPPED_EXISTS")

    if opts["dry_run"]:
        log.info("[%s] %s: DRY-RUN would stage -> %s", wg, name, uri)
        return _row(project, wg, name, nid, uri, "", "DRYRUN")

    t0 = time.time()
    retained = " (existing copy retained)" if opts["overwrite"] and existing_ids else ""
    try:
        cx_progress(f"{px}{name} {dots} {_SPINNER} preparing...")
        # Overwrite: existing copies are deleted only AFTER the new import succeeds (see below),
        # so a failed re-import never loses the previously migrated notebook.
        payload = with_retry(athena.export_notebook, NotebookId=nid).get("Payload", "")
        if not payload:
            log.warning("[%s] %s: SKIPPED - empty notebook", wg, name)
            cx_progress(f"{px}{name} {dots} {_WARN} skipped (empty)", done=True)
            return _row(project, wg, name, nid, "", "", "SKIPPED_EMPTY", "empty notebook")

        before = len(payload.encode("utf-8"))
        payload = clear_notebook_outputs(payload)
        after = len(payload.encode("utf-8"))
        cleared = after < before

        payload, _ = convert_sql_magic_cells(payload)

        payload = prepend_migration_banner(payload, wg, project, nid, smus_workgroup)

        with_retry(s3.put_object, Bucket=bucket, Key=key, Body=payload.encode("utf-8"),
                   ContentType="application/x-ipynb+json")

        cx_progress(f"{px}{name} {dots} {_SPINNER} importing...")
        imported = with_retry(dz.start_notebook_import, domainIdentifier=domain,
                              owningProjectIdentifier=project, name=name,
                              sourceLocation={"s3": uri},
                              clientToken=uuid.uuid4().hex)["notebookId"]
        log.info("[%s] %s: import started (%s) - waiting for completion", wg, name, imported)

        status, waited = "IMPORT_IN_PROGRESS", 0
        while waited < opts["max_wait"]:
            status = with_retry(dz.get_notebook, domainIdentifier=domain, identifier=imported).get("status", "")
            if status == "ACTIVE" or "FAIL" in status:
                break
            time.sleep(opts["poll"])
            waited += opts["poll"]

        secs = int(time.time() - t0)
        if status != "ACTIVE":
            log.error("[%s] %s: import did not succeed (status=%s)", wg, name, status)
            cx_progress(f"{px}{name} {dots} {_CROSS} FAILED ({status}, {secs}s)", done=True)
            return _row(project, wg, name, nid, uri, imported, status or "TIMEOUT",
                        f"import status {status}" + retained, secs)

        detail = ""
        if opts["overwrite"] and existing_ids:
            stale = []
            for old in existing_ids:
                try:
                    with_retry(dz.delete_notebook, domainIdentifier=domain, identifier=old)
                    log.info("[%s] %s: deleted previous copy %s (overwrite)", wg, name, old)
                except Exception as e:
                    stale.append(old)
                    log.warning("[%s] %s: new copy %s imported but previous copy %s could not be deleted: %s",
                                wg, name, imported, old, format_aws_error(e))
            if stale:
                detail = f"previous copy not deleted (duplicate): {', '.join(stale)}"

        log.info("[%s] %s: SUCCESS in %ds -> %s", wg, name, secs, imported)
        cx_progress(f"{px}{name} {dots} {_CHECK} done ({secs}s)", done=True)
        return _row(project, wg, name, nid, uri, imported, "SUCCESS", detail, secs)

    except Exception as e:
        log.error("[%s] %s: FAILED. AWS error: %s", wg, name, format_aws_error(e))
        log.debug("Traceback:", exc_info=True)
        cx_progress(f"{px}{name} {dots} {_CROSS} FAILED ({error_code(e)})", done=True)
        return _row(project, wg, name, nid, uri, "", f"ERROR:{error_code(e)}",
                    format_aws_error(e) + retained, int(time.time() - t0))


# --------------------------------------------------------------------------- #
# Notebook Filters
# --------------------------------------------------------------------------- #

_GLOB_CHARS = set("*?[")


def name_matches(name, pattern):
    """Case-insensitive glob match; a pattern without wildcards is a substring match.

    Deliberately not a regex: '.' is literal and no user input is compiled, so there is
    no catastrophic backtracking (ReDoS) and no raw re.error on bad input.
    """
    name, pattern = name.casefold(), pattern.casefold()
    if not _GLOB_CHARS & set(pattern):
        return pattern in name
    return fnmatch.fnmatchcase(name, pattern)


_REGEX_HINTS = ("^", "$", "\\", ".*", ".+", "{")


def regex_filter_hint(pattern):
    """Returns a suggestion if --name-filter looks like a regex (it is matched literally), else None."""
    if not pattern or not any(h in pattern for h in _REGEX_HINTS):
        return None
    if pattern.startswith("^") and pattern.endswith("$") and not any(h in pattern[1:-1] for h in _REGEX_HINTS):
        return f"--notebooks {pattern[1:-1]}"
    glob = pattern.strip("^$").replace(".*", "*").replace(".+", "?*").replace("\\", "")
    return f"--name-filter '{glob}'"


def passes_filters(nb, opts):
    """Applies user-specified filters to determine if a notebook should be included."""
    if opts["name_filter"] and not name_matches(nb.get("Name", ""), opts["name_filter"]):
        return False
    # --notebooks accepts Athena notebook IDs or exact notebook names.
    if opts["ids"] and nb["NotebookId"] not in opts["ids"] and nb.get("Name") not in opts["ids"]:
        return False
    if opts["since_date"]:
        lm = nb.get("LastModifiedTime")
        if isinstance(lm, datetime) and lm.date() < opts["since_date"]:
            return False
    return True


def parse_notebook_selectors(value):
    """Parses the comma-separated --notebooks value into a set of IDs/names (None if not given)."""
    if not value:
        return None
    selectors = {v.strip() for v in value.split(",") if v.strip()}
    return selectors or None


def parse_since(value):
    """argparse type for --since: a real calendar date in YYYY-MM-DD form."""
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid date '{value}': expected a valid date in YYYY-MM-DD form (e.g. 2026-09-01)")


def load_resume(path):
    """Reads a prior report and returns {(workgroup, athena_notebook_id): smus_notebook_id} for migrated rows.

    SKIPPED_RESUME rows count as migrated so a report from a resumed run can itself be resumed.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"--resume {path}: not a valid report JSON ({e.msg} at line {e.lineno})")
    rows = data.get("notebooks", []) if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"--resume {path}: not a migration report (missing 'notebooks' list)")
    done = {}
    for r in rows:
        if isinstance(r, dict) and r.get("status") in ("ACTIVE", "SUCCESS", "SKIPPED_RESUME") and r.get("smus_notebook_id"):
            done[(r.get("workgroup"), r.get("athena_notebook_id"))] = r["smus_notebook_id"]
    return done


def unmatched_selectors(selectors, notebooks):
    """Returns --notebooks values (IDs or names) that matched none of the listed notebooks."""
    seen = set()
    for nb in notebooks:
        seen.add(nb.get("NotebookId"))
        seen.add(nb.get("Name"))
    return sorted(s for s in selectors if s not in seen)


def load_config(path):
    """Loads and validates the --config JSON file. Raises ValueError with a clear message."""
    def _no_duplicates(pairs):
        obj = {}
        for k, v in pairs:
            if k in obj:
                raise ValueError(f"--config {path}: duplicate key '{k}' (each workgroup may be mapped only once)")
            obj[k] = v
        return obj

    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f, object_pairs_hook=_no_duplicates)
    except json.JSONDecodeError as e:
        raise ValueError(f"--config {path}: invalid JSON ({e.msg} at line {e.lineno}, column {e.colno})")

    if not isinstance(config, dict):
        raise ValueError(f"--config {path}: top level must be a JSON object, got {type(config).__name__}")
    if "domain_id" in config and not isinstance(config["domain_id"], str):
        raise ValueError(f"--config {path}: 'domain_id' must be a string, got {type(config['domain_id']).__name__}")
    if "region" in config:
        cx(f"\n  {_WARN}  --config {path}: 'region' is ignored; the Region comes from --region.")
    map_key = next((k for k in ("athena_workgroup_to_smus_project_map", "workgroup_project_map") if k in config), None)
    if not map_key:
        raise ValueError(f"--config {path}: missing 'workgroup_project_map' "
                         "(object of Athena workgroup name -> SMUS project ID)")
    mapping = config[map_key]
    if not isinstance(mapping, dict):
        raise ValueError(f"--config {path}: '{map_key}' must be an object of workgroup -> project ID, "
                         f"got {type(mapping).__name__}")
    if not mapping:
        raise ValueError(f"--config {path}: '{map_key}' is empty")
    for wg, proj in mapping.items():
        if not isinstance(proj, str) or not proj.strip():
            raise ValueError(f"--config {path}: project ID for workgroup '{wg}' must be a non-empty string")
    return config


def resolve_targets(args, config):
    """Resolves migration targets from CLI args or config file."""
    if config:
        domain = config.get("domain_id") or args.domain_id
        pairs = [(wg, proj) for wg, proj in config.get("athena_workgroup_to_smus_project_map", config.get("workgroup_project_map", {})).items()]
        return domain, args.region, pairs
    return args.domain_id, args.region, [(wg, args.project_id) for wg in (args.workgroups or [])]


# --------------------------------------------------------------------------- #
# Operating Modes
# --------------------------------------------------------------------------- #

def confirm(prompt):
    """Displays an interactive confirmation prompt."""
    try:
        return input(f"\n  ? {prompt} [y/N]: ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def do_inventory(session, region, workgroups, all_wg_flag, report_base, log_file=None):
    """Inventory mode (read-only): list all PySpark engine version 3 workgroups and their notebooks."""
    athena = session.client("athena")

    if all_wg_flag or not workgroups:
        workgroups = all_spark_v3_workgroups(athena)
        if not workgroups:
            cx_banner(f"Athena PySpark engine version 3 Notebook Inventory  {_THIN * 2}  {region}")
            cx(f"\n  No PySpark engine version 3 workgroups found in region {region}.")
            log.info("Inventory: no PySpark engine version 3 workgroups found in region %s", region)
            write_reports(report_base, {"mode": "inventory", "region": region, "workgroups": [],
                                        "counts": {"workgroups": 0, "notebooks": 0}}, [])
            cx(f"\n  {chr(128196)} Report: {report_base}.json")
            cx(f"  {chr(128203)} Log:    {log_file}")
            return True

    workgroups, skipped = accessible_workgroups(athena, workgroups)
    if not workgroups:
        cx(f"\n  {_CROSS} No accessible workgroups found. Check IAM permissions.")
        log.error("Inventory: no accessible workgroups (skipped: %s)", ", ".join(skipped) or "-")
        cx(f"\n  {chr(128203)} Log:    {log_file}")
        return False

    # Collect data
    rows, grand = [], 0
    wg_counts = []
    for wg in workgroups:
        try:
            nbs = list_notebooks(athena, wg)
        except Exception as e:
            if error_code(e) in ACCESS_DENIED_CODES:
                log.warning("Workgroup '%s': access denied, skipping. %s", wg, format_aws_error(e))
                continue
            log.error("Workgroup '%s': %s", wg, format_aws_error(e))
            continue
        grand += len(nbs)
        wg_counts.append((wg, len(nbs)))
        log.info("Inventory: workgroup '%s' has %d notebook(s)", wg, len(nbs))
        for nb in nbs:
            rows.append({"workgroup": wg, "notebook_name": nb.get("Name", ""),
                         "athena_notebook_id": nb.get("NotebookId", ""),
                         "last_modified": str(nb.get("LastModifiedTime", ""))[:19]})
            log.info("  [%s] %s (%s) last modified %s", wg, rows[-1]["notebook_name"],
                     rows[-1]["athena_notebook_id"], rows[-1]["last_modified"])

    # CX Output
    cx_banner(f"Athena PySpark engine version 3 Notebook Inventory  {_THIN * 2}  {region}")
    cx(f"\n  Found {len(workgroups)} PySpark engine version 3 workgroup(s) {_THIN * 2} {grand} notebooks total")
    if skipped:
        cx(f"  ({len(skipped)} workgroup(s) skipped due to access issues)")

    # Same column sizing as the plan / summary tables (capped, ellipsis past the cap).
    wg_w = col_width("WORKGROUP", [wg for wg, _ in wg_counts], 30, TABLE_MAX_WORKGROUP_W)
    cx(f"\n  {'WORKGROUP':<{wg_w}} NOTEBOOKS")
    cx(f"  {_THIN * wg_w} {_THIN * 9}")
    for wg, count in wg_counts:
        cx(f"  {fit(wg, wg_w):<{wg_w}} {count}")
    clipped = any(len(wg) > wg_w for wg, _ in wg_counts)

    if rows:
        cx(f"\n{_THIN * W}")
        cx("  Detail")
        cx(_THIN * W)
        dwg_w = col_width("WORKGROUP", [r["workgroup"] for r in rows], 26, TABLE_MAX_WORKGROUP_W)
        nb_w = col_width("NOTEBOOK", [r["notebook_name"] for r in rows], 30, TABLE_MAX_NOTEBOOK_W)
        cx(f"\n  {'WORKGROUP':<{dwg_w}} {'NOTEBOOK':<{nb_w}} LAST MODIFIED")
        cx(f"  {_THIN * dwg_w} {_THIN * nb_w} {_THIN * 19}")
        for r in rows:
            cx(f"  {fit(r['workgroup'], dwg_w):<{dwg_w}} {fit(r['notebook_name'], nb_w):<{nb_w}} {r['last_modified']}")
        clipped = clipped or any(len(r["workgroup"]) > dwg_w or len(r["notebook_name"]) > nb_w for r in rows)

    if clipped:
        cx(f"\n  Long names are shortened ({_ELLIPSIS}); see the report for full names.")

    cx_verdict(_CHECK, f"{grand} notebooks across {len(workgroups)} workgroups ready for migration", "")
    cx(f"\n  {chr(8505)}  To migrate, run:")
    # More than 6 workgroups: suggest auto-discovery instead of a long list.
    wg_flag = "--workgroups " + " ".join(workgroups) if len(workgroups) <= 6 else "--all-workgroups"
    cx(f"     python3 athena_notebook_migration.py \\")
    cx(f"       {wg_flag} \\")
    cx(f"       --domain-id <your-domain-id> \\")
    cx(f"       --project-id <your-project-id> \\")
    cx(f"       --region {region}")

    write_reports(report_base, {"mode": "inventory", "region": region,
                                "workgroups": [{"workgroup": w, "notebooks": c} for w, c in wg_counts],
                                "skipped_workgroups": skipped,
                                "counts": {"workgroups": len(wg_counts), "notebooks": grand}}, rows)
    log.info("Inventory: %d notebook(s) across %d workgroup(s)", grand, len(wg_counts))
    cx(f"\n  {chr(128196)} Report: {report_base}.json")
    cx(f"  {chr(128203)} Log:    {log_file}")
    return True


def do_migrate(src_session, dst_session, domain, region, pairs, args, report_base, log_file=None):
    """Migration mode: export, stage, and import notebooks from Athena to SMUS."""
    started = time.time()
    athena = src_session.client("athena")
    dz, s3 = dst_session.client("datazone"), dst_session.client("s3")
    clients = (athena, dz, s3)

    # Mode description
    mode_parts = []
    if args.dry_run:
        mode_parts.append("Dry run (no changes)")
    else:
        mode_parts.append("Migration")
    if args.overwrite:
        mode_parts.append("overwrite enabled")
    mode_desc = " (" + ", ".join(mode_parts[1:]) + ")" if len(mode_parts) > 1 else ""

    wg_names = [w for w, _ in pairs]
    title = "Athena " + _ARROW + " SageMaker Unified Studio  " + _THIN * 2 + "  Notebook Migration"
    if args.dry_run:
        title += "  " + _THIN * 2 + "  DRY RUN"

    cx_banner(title)
    cx("")
    cx_kv("Domain", domain)
    projects = sorted({p for _, p in pairs})
    if len(projects) == 1:
        cx_kv("Project", projects[0])
    else:
        cx_kv("Projects", f"{len(projects)} ({', '.join(projects)})")
    cx_kv("Region", region)
    cx_kv("Mode", mode_parts[0] + mode_desc)

    try:
        sa = src_session.client("sts").get_caller_identity()["Account"]
        da = dst_session.client("sts").get_caller_identity()["Account"]
        cx_kv("Source account", sa)
        cx_kv("Destination account", da)
        log.info("Source account: %s | Destination account: %s", sa, da)
    except Exception:
        pass

    # --- STEP 1: Validating migration access ---
    cx_step(1, 3, "Validating migration access")

    # Collect all validation results; show compact summary at the end
    step1_errors = []  # list of (label, detail, fix_hint)

    # 1) Validate AWS account identity
    try:
        caller_account = src_session.client("sts").get_caller_identity()["Account"]
        log.info("Caller account: %s", caller_account)
    except Exception as e:
        caller_account = None
        step1_errors.append(("AWS account", f"Could not verify identity ({error_code(e)})",
                             "Refresh your AWS credentials and re-run."))
        log.error("STS GetCallerIdentity failed: %s", format_aws_error(e))

    # Short-circuit: if credentials are dead, skip everything else
    if not caller_account:
        cx("")
        err = next(e for e in step1_errors if e[0] == "AWS account")
        cx(f"  {_CROSS}  {'AWS account':<22}{err[1]}")
        cx(f"{'':>27}{_ARROW} {err[2]}")
        cx(f"  {_THIN}  {'Athena source':<22}skipped (no credentials)")
        cx(f"  {_THIN}  {'SMUS destination':<22}skipped (no credentials)")
        cx(f"\n  {_CROSS}  Migration prerequisites validation failed. Fix the issue(s) and re-run.")
        cx(f"\n  {chr(128203)} Log:    {log_file}")
        log.error("Step 1 failed: credentials invalid or expired")
        sys.exit(1)

    # 2) Validate domain (only reached if credentials are valid)
    try:
        with_retry(dz.get_domain, identifier=domain)
        log.info("Domain %s validated", domain)
    except Exception as e:
        http_code = (getattr(e, "response", None) or {}).get("ResponseMetadata", {}).get("HTTPStatusCode", "?")
        if error_code(e) in ACCESS_DENIED_CODES or http_code == 403:
            fix = f"A 403 on GetDomain usually means WRONG REGION. Re-run with --region set to the domain's actual region."
        else:
            fix = f"Check the domain ID in the SageMaker Unified Studio console."
        step1_errors.append(("SMUS destination", f"Domain '{domain}' not accessible ({error_code(e)}, HTTP {http_code})", fix))

    # 3) Expand workgroups and validate accessibility
    expanded = []
    for wg, proj in pairs:
        if wg == "__ALL_WORKGROUPS__":
            discovered = all_spark_v3_workgroups(athena)
            accessible, skipped = accessible_workgroups(athena, discovered)
            for w in accessible:
                expanded.append((w, proj))
        else:
            expanded.append((wg, proj))

    excl = set(args.exclude_workgroups or [])
    expanded = [(w, p) for (w, p) in expanded if w not in excl]

    # Verify each workgroup is readable (and test export once). A workgroup that is denied or not
    # found is skipped with a warning and reported as a failed row; the others still migrate.
    athena_status = None
    unavailable = {}  # workgroup -> (reason shown in the plan, detail for the report)
    if not expanded:
        step1_errors.append(("Athena source", "No workgroups to migrate (all excluded or inaccessible)",
                             "Check --workgroups names or --region matches the source."))
    else:
        wg_names = sorted({w for w, _ in expanded})
        export_ok = False
        for wg_name in wg_names:
            try:
                nbs = with_retry(athena.list_notebook_metadata, WorkGroup=wg_name, MaxResults=1).get("NotebookMetadataList", [])
                if nbs and not export_ok:
                    with_retry(athena.export_notebook, NotebookId=nbs[0]["NotebookId"])
                    export_ok = True
            except Exception as e:
                code = error_code(e)
                if code in CREDENTIAL_ERROR_CODES:
                    step1_errors.append(("Athena source", f"Credentials expired or invalid ({code})",
                                         "Refresh your AWS credentials and re-run."))
                    log.error("Athena credential error on workgroup '%s': %s", wg_name, str(e))
                    break
                if code in ACCESS_DENIED_CODES:
                    unavailable[wg_name] = ("access denied", format_aws_error(e))
                elif code == "InvalidRequestException":
                    unavailable[wg_name] = ("not found", format_aws_error(e))
                else:
                    log.debug("Access check on %s failed (non-access error, continuing): %s", wg_name, format_aws_error(e))
                    continue
                log.warning("Skipping workgroup '%s' (%s): %s", wg_name, unavailable[wg_name][0], format_aws_error(e))
        readable = [w for w in wg_names if w not in unavailable]
        if not any(e[0] == "Athena source" for e in step1_errors):
            if not readable:
                step1_errors.append(("Athena source", f"No listed workgroup is accessible ({len(unavailable)} denied or not found)",
                                     "Check the workgroup names, --source-region, and athena:ListNotebookMetadata / "
                                     "athena:ExportNotebook permissions."))
            else:
                athena_status = f"{len(readable)} workgroup(s) accessible" + (", notebook export verified" if export_ok else "")
                if unavailable:
                    athena_status += f"; {len(unavailable)} skipped"

    # 4) Validate project(s) and resolve S3 staging
    opts = {"dry_run": args.dry_run, "overwrite": args.overwrite,
            "name_filter": args.name_filter or None,
            "ids": parse_notebook_selectors(args.notebooks),
            "since_date": args.since, "poll": DEFAULT_POLL_INTERVAL, "max_wait": 120}

    proj_base, proj_existing, proj_smus_wg = {}, {}, {}
    smus_status = None
    total_existing = 0
    for proj in {p for _, p in expanded}:
        try:
            with_retry(dz.get_project, domainIdentifier=domain, identifier=proj)
        except Exception as e:
            step1_errors.append(("SMUS destination", f"Project '{proj}' not accessible ({error_code(e)})",
                                 "Verify the project ID or add your identity to the project members."))
            continue
        base = project_s3_base(dz, domain, proj)
        if not base:
            step1_errors.append(("SMUS destination", f"No active environment found for project '{proj}'",
                                 "Ensure the project has an ACTIVE environment with provisioned resources."))
            continue
        proj_base[proj] = base
        proj_smus_wg[proj] = project_athena_workgroup(dz, domain, proj)
        try:
            proj_existing[proj] = existing_notebooks(dz, domain, proj)
            nb_count = sum(len(v) for v in proj_existing[proj].values())
            total_existing += nb_count
        except Exception as e:
            step1_errors.append(("SMUS destination", f"Cannot list notebooks in project '{proj}' ({error_code(e)})",
                                 "Grant datazone:ListNotebooks permission to your IAM identity."))
            log.error("ListNotebooks failed for project %s: %s", proj, str(e))
            nb_count = 0
        log.info("Project %s -> S3 base %s (%d existing notebooks)", proj, base, nb_count)

    if not any(e[0] == "SMUS destination" for e in step1_errors) and proj_base:
        smus_status = f"Domain and project validated ({total_existing} existing notebooks)"

    # --- Render compact Step 1 CX ---
    cx("")
    # Line 1: AWS account
    if caller_account:
        cx(f"  {_CHECK}  {'AWS account':<22}{caller_account}")
    else:
        err = next(e for e in step1_errors if e[0] == "AWS account")
        cx(f"  {_CROSS}  {'AWS account':<22}{err[1]}")
        cx(f"{'':>27}{_ARROW} {err[2]}")

    # Line 2: Athena source
    if athena_status:
        cx(f"  {_CHECK}  {'Athena source':<22}{athena_status}")
    elif any(e[0] == "Athena source" for e in step1_errors):
        err = next(e for e in step1_errors if e[0] == "Athena source")
        cx(f"  {_CROSS}  {'Athena source':<22}{err[1]}")
        cx(f"{'':>27}{_ARROW} {err[2]}")
    else:
        cx(f"  {_CHECK}  {'Athena source':<22}workgroups accessible")
    for w, (reason, _) in sorted(unavailable.items()):
        cx(f"{'':>27}{_WARN} skipping '{w}' ({reason})")

    # Line 3: SMUS destination
    if smus_status:
        cx(f"  {_CHECK}  {'SMUS destination':<22}{smus_status}")
    elif any(e[0] == "SMUS destination" for e in step1_errors):
        err = next(e for e in step1_errors if e[0] == "SMUS destination")
        cx(f"  {_CROSS}  {'SMUS destination':<22}{err[1]}")
        cx(f"{'':>27}{_ARROW} {err[2]}")
    else:
        cx(f"  {_THIN}  {'SMUS destination':<22}skipped (earlier failure)")

    # Verdict line
    blocking_errors = [e for e in step1_errors if e[0] in ("AWS account", "SMUS destination", "Athena source")]
    if blocking_errors:
        cx(f"\n  {_CROSS}  Migration prerequisites validation failed. Fix the issue(s) and re-run.")
        cx(f"\n  {chr(128203)} Log:    {log_file}")
        log.error("Step 1 failed: %s", "; ".join(e[1] for e in blocking_errors))
        sys.exit(1)
    else:
        cx(f"\n  {_CHECK}  Migration prerequisites validated successfully")

    # --- Execution role comparison (non-blocking warning) ---
    role_records = []
    role_gaps = {}
    src_iam, dst_iam = src_session.client("iam"), dst_session.client("iam")
    smus_role_by_proj = {p: resolve_smus_role(dz, domain, p) for p in {pp for _, pp in expanded}}
    src_role_by_wg = {}
    for wg in {w for w, _ in expanded}:
        try:
            src_role_by_wg[wg] = resolve_athena_role(athena, wg)
        except Exception:
            src_role_by_wg[wg] = None
    src_cache, smus_cache = {}, {}
    for wg, proj in expanded:
        rec = {"domain": domain, "project": proj, "workgroup": wg,
               "source_role": src_role_by_wg.get(wg), "smus_role": smus_role_by_proj.get(proj)}
        rec.update(evaluate_role_gap(src_iam, dst_iam, rec["source_role"], rec["smus_role"],
                                     src_cache, smus_cache))
        role_records.append(rec)
    _, role_gaps = render_role_check_cx(role_records, region)


    # --- STEP 2: Plan ---
    cx_step(2, 3, "Planning migration")

    resume_done = load_resume(args.resume) if args.resume else {}
    hint = regex_filter_hint(opts["name_filter"])
    if hint:
        cx(f"\n  {_WARN}  --name-filter is not a regular expression; ^ $ . \\ are matched literally.")
        cx(f"     Did you mean: {hint}")
        log.warning("--name-filter %r looks like a regex (matched literally); suggested: %s", opts["name_filter"], hint)
    if args.resume:
        cx(f"\n  Resume mode: {len(resume_done)} notebook(s) marked done in the report "
           f"(each is re-checked against the destination project)")

    tasks = []
    plan_rows = []  # For the pre-confirmation table
    all_listed = []  # every listed notebook (pre-filter), to report unmatched --notebooks values
    duplicated = []  # (workgroup, name, copies) already present more than once in the project
    for wg, proj in expanded:
        if wg in unavailable:
            reason, detail = unavailable[wg]
            tasks.append(("__ERROR__", wg, proj, detail))
            plan_rows.append({"wg": wg, "name": "-", "action": f"ERROR ({reason})", "project": proj})
            continue
        try:
            listed = list_notebooks(athena, wg)
            all_listed.extend(listed)
            nbs = [nb for nb in listed if passes_filters(nb, opts)]
        except Exception as e:
            if error_code(e) in ACCESS_DENIED_CODES:
                tasks.append(("__ERROR__", wg, proj, f"Access denied"))
                plan_rows.append({"wg": wg, "name": "-", "action": "ERROR (access denied)", "project": proj})
                continue
            tasks.append(("__ERROR__", wg, proj, format_aws_error(e)))
            plan_rows.append({"wg": wg, "name": "-", "action": f"ERROR ({error_code(e)})", "project": proj})
            continue
        log.info("Workgroup '%s' -> project %s : %d notebook(s) after filters", wg, proj, len(nbs))
        project_ids = {i for ids in proj_existing.get(proj, {}).values() for i in ids}
        for nb in nbs:
            tasks.append((nb, wg, proj, None))
            name = nb.get("Name", nb["NotebookId"])
            existing_ids = proj_existing.get(proj, {}).get(name, [])
            key = (wg, nb["NotebookId"])
            resumed_missing = False
            if key in resume_done and resume_done[key] not in project_ids:
                # Report says SUCCESS but the notebook is gone from the project: migrate it again.
                log.warning("[%s] %s: report marks it migrated as %s, but it is not in project %s; re-migrating",
                            wg, name, resume_done[key], proj)
                del resume_done[key]
                resumed_missing = True
            if key in resume_done:
                action = "skip (already done)"
            elif existing_ids and not opts["overwrite"]:
                action = "skip (exists)" if len(existing_ids) == 1 else f"skip (exists, {len(existing_ids)} copies)"
                if len(existing_ids) > 1:
                    duplicated.append((wg, name, len(existing_ids)))
            elif existing_ids and opts["overwrite"]:
                action = "overwrite (exists)"
            else:
                action = "migrate (missing in project)" if resumed_missing else "migrate"
            plan_rows.append({"wg": wg, "name": name, "action": action, "project": proj})

    real = [t for t in tasks if t[0] != "__ERROR__"]
    total_count = len(real)
    migrate_count = sum(1 for pr in plan_rows if pr["action"] in MIGRATE_ACTIONS)
    plan_skip_count = total_count - migrate_count

    # Pre-confirmation table
    multi_proj = len({p for _, p in expanded}) > 1
    # Same column sizing as the post-migration summary (capped, ellipsis past the cap).
    wg_w = col_width("WORKGROUP", [pr["wg"] for pr in plan_rows], 26, TABLE_MAX_WORKGROUP_W)
    nb_w = col_width("NOTEBOOK", [pr["name"] for pr in plan_rows], 32, TABLE_MAX_NOTEBOOK_W)
    proj_w = col_width("PROJECT", [pr.get("project", "-") for pr in plan_rows], 16, TABLE_MAX_PROJECT_W)
    clipped = any(len(pr["wg"]) > wg_w or len(pr["name"]) > nb_w
                  or (multi_proj and len(pr.get("project", "-")) > proj_w) for pr in plan_rows)
    if multi_proj:
        cx(f"\n  {'PROJECT':<{proj_w}} {'WORKGROUP':<{wg_w}} {'NOTEBOOK':<{nb_w}} ACTION")
        cx(f"  {_THIN * (proj_w - 1)} {_THIN * (wg_w - 1)} {_THIN * (nb_w - 1)} {_THIN * 18}")
    else:
        cx(f"\n  {'WORKGROUP':<{wg_w}} {'NOTEBOOK':<{nb_w}} ACTION")
        cx(f"  {_THIN * (wg_w - 1)} {_THIN * (nb_w - 1)} {_THIN * 18}")
    for pr in plan_rows:
        wg_display = fit(pr["wg"], wg_w)
        nb_display = fit(pr["name"], nb_w)
        if multi_proj:
            cx(f"  {fit(pr.get('project', '-'), proj_w):<{proj_w}} {wg_display:<{wg_w}} {nb_display:<{nb_w}} {pr['action']}")
        else:
            cx(f"  {wg_display:<{wg_w}} {nb_display:<{nb_w}} {pr['action']}")
    pad = f"{'':>{proj_w}} " if multi_proj else ""
    cx(f"  {pad}{'':>{wg_w}} {'':>{nb_w}} {_THIN * 18}")
    cx(f"  {pad}{'':>{wg_w}} {'':>{nb_w}} Total: {total_count} notebook(s)")
    if clipped:
        cx(f"\n  Long names are shortened ({_ELLIPSIS}); see the report for full names.")

    if duplicated:
        # e.g. an --overwrite run interrupted after the new copy imported but before the old one was deleted
        cx(f"\n  {_WARN}  {len(duplicated)} notebook(s) have more than one copy in the destination project:")
        for wg, name, copies in duplicated:
            cx(f"       {_THIN} [{wg}] {name} ({copies} copies)")
        cx(f"     Re-run with --overwrite to replace them with a single fresh copy.")
        log.warning("Duplicate copies in project: %s", ", ".join(f"{n} x{c}" for _, n, c in duplicated))

    unmatched = unmatched_selectors(opts["ids"], all_listed) if opts["ids"] else []
    if unmatched:
        cx(f"\n  {_WARN}  {len(unmatched)} --notebooks value(s) matched no notebook in the selected workgroup(s):")
        for u in unmatched:
            cx(f"       {_THIN} {u}")
        cx(f"     --notebooks accepts Athena notebook IDs or exact notebook names.")
        log.warning("--notebooks values with no match: %s", ", ".join(unmatched))

    if not args.dry_run and total_count == 0:
        cx(f"\n  Nothing to migrate {_THIN * 2} no notebooks matched the selected workgroup(s) and filters.")
    elif not args.dry_run and migrate_count == 0:
        cx(f"\n  Nothing to migrate {_THIN * 2} all selected notebooks are skipped.")
    elif not args.dry_run and not args.yes:
        skipped_note = f" ({plan_skip_count} will be skipped)" if plan_skip_count else ""
        if not confirm(f"Proceed to migrate {migrate_count} notebook(s){skipped_note}?"):
            cx(f"\n  Aborted {_THIN * 2} no changes made.")

            cx(f"  Tip: pass --yes to skip this prompt in CI/automation.")

            log.info("Aborted by user")
            sys.exit(3)

    # --- STEP 3: Migrate ---
    if not args.dry_run:
        cx_step(3, 3, "Migrating")

    # The report is rewritten after every notebook so an interrupted run can be resumed.
    report = IncrementalReport(report_base, {
        "mode": "migrate", "domain_id": domain, "region": region, "dry_run": args.dry_run,
        "targets": [{"workgroup": w, "project_id": p} for w, p in expanded],
        "started_utc": datetime.fromtimestamp(started, timezone.utc).isoformat()})

    rows = []
    for t in tasks:
        if t[0] == "__ERROR__":
            _, wg, proj, det = t
            rows.append(_row(proj, wg, "-", "", "", "", "ERROR:ListFailed", det))
            report.add(rows[-1])

    counter = [1, total_count]  # mutable counter for progress

    def run(t):
        nb, wg, proj, _ = t
        row = migrate_one(clients, domain, proj, proj_base[proj], wg, nb, opts,
                          proj_existing.get(proj, {}), resume_done, counter,
                          smus_workgroup=proj_smus_wg.get(proj))
        report.add(row)
        return row

    try:
        if args.concurrency > 1 and real:
            ex = ThreadPoolExecutor(max_workers=args.concurrency)
            try:
                futures = [ex.submit(run, t) for t in real]
                for _ in as_completed(futures):
                    pass
                rows.extend(f.result() for f in futures)  # keep plan order in the summary
            finally:
                ex.shutdown(wait=True, cancel_futures=True)
        else:
            for t in real:
                rows.append(run(t))
    except KeyboardInterrupt:
        report.finish({"interrupted_utc": datetime.now(timezone.utc).isoformat()}, complete=False)
        log.warning("Interrupted; partial report written with %d notebook(s)", len(report.rows))
        cx(f"\n\n  {_WARN}  Interrupted {_THIN * 2} {len(report.rows)} notebook(s) recorded in the report.")
        cx(f"     Continue with: add --resume {report_base}.json to your command")
        cx(f"\n  {chr(128196)} Report: {report_base}.json")
        cx(f"  {chr(128203)} Log:    {log_file}")
        raise

    # --- Summary Table ---
    if not args.dry_run:
        cx(f"\n{'':>2}{_THIN * (W - 4)}")
        cx(f"  Summary")
        cx(f"{'':>2}{_THIN * (W - 4)}")

        # Determine columns based on multi-project
        multi_proj_summary = len({r["project_id"] for r in rows if r["project_id"]}) > 1

        # Width-adaptive columns: size each column to its widest value (header
        # included) so typical workgroup / notebook names are shown in full, but cap
        # WORKGROUP / NOTEBOOK so a 128-char workgroup or 255-char notebook name can't
        # blow up every row. Longer values end in an ellipsis; the report has them in full.
        # RESULT and TIME stay fixed -- their content is constant.
        wg_w = col_width("WORKGROUP", [r["workgroup"] for r in rows], 24, TABLE_MAX_WORKGROUP_W)
        nb_w = col_width("NOTEBOOK", [r["notebook_name"] for r in rows], 26, TABLE_MAX_NOTEBOOK_W)
        clipped = any(len(r["workgroup"]) > wg_w or len(r["notebook_name"]) > nb_w for r in rows)
        smus_w = col_width("SMUS NOTEBOOK ID", [r["smus_notebook_id"] or "-" for r in rows], 16)
        res_w, time_w = 10, 5

        if multi_proj_summary:
            proj_w = col_width("PROJECT", [r["project_id"] or "-" for r in rows], 12, TABLE_MAX_PROJECT_W)
            clipped = clipped or any(len(r["project_id"] or "-") > proj_w for r in rows)
            cx(f"\n  {'RESULT':<{res_w}} {'PROJECT':<{proj_w}} {'WORKGROUP':<{wg_w}} {'NOTEBOOK':<{nb_w}} {'SMUS NOTEBOOK ID':<{smus_w}} {'TIME':<{time_w}}")
            cx(f"  {_THIN * (res_w - 1)} {_THIN * (proj_w - 1)} {_THIN * (wg_w - 1)} {_THIN * (nb_w - 1)} {_THIN * (smus_w - 1)} {_THIN * (time_w - 1)}")
        else:
            cx(f"\n  {'RESULT':<{res_w}} {'WORKGROUP':<{wg_w}} {'NOTEBOOK':<{nb_w}} {'SMUS NOTEBOOK ID':<{smus_w}} {'TIME':<{time_w}}")
            cx(f"  {_THIN * (res_w - 1)} {_THIN * (wg_w - 1)} {_THIN * (nb_w - 1)} {_THIN * (smus_w - 1)} {_THIN * (time_w - 1)}")

        for r in rows:
            st = r["status"]
            if st == "SUCCESS":
                sym = f"{_CHECK} Success"
            elif st.startswith("SKIP") or st == "DRYRUN":
                sym = "  Skip"
            else:
                sym = f"{_CROSS} Fail"
            time_s = f"{r['duration_s']}s" if r["status"] == "SUCCESS" else "-"
            nb_name = fit(r["notebook_name"], nb_w)
            smus_id = r["smus_notebook_id"] or "-"
            wg = fit(r["workgroup"], wg_w)

            if multi_proj_summary:
                proj = fit(r["project_id"] or "-", proj_w)
                cx(f"  {sym:<{res_w}} {proj:<{proj_w}} {wg:<{wg_w}} {nb_name:<{nb_w}} {smus_id:<{smus_w}} {time_s:<{time_w}}")
            else:
                cx(f"  {sym:<{res_w}} {wg:<{wg_w}} {nb_name:<{nb_w}} {smus_id:<{smus_w}} {time_s:<{time_w}}")

        if clipped:
            cx(f"\n  Long names are shortened ({_ELLIPSIS}); see the report for full names.")

    # --- Summary ---
    ok = sum(1 for r in rows if r["status"] == "SUCCESS")
    fail = sum(1 for r in rows if r["status"].startswith("ERROR") or r["status"] in ("TIMEOUT", "UNKNOWN")
               or ("FAIL" in r["status"] and not r["status"].startswith("SKIP")))
    skipped_count = sum(1 for r in rows if r["status"].startswith("SKIP") or r["status"] == "DRYRUN")
    finished = time.time()
    elapsed = int(finished - started)

    # Verdict line
    if args.dry_run:
        cx_verdict(f"{_CHECK}", "DRY RUN COMPLETE",
                   f"{migrate_count} notebooks would be migrated ({plan_skip_count} skipped)")
    elif fail == 0 and ok > 0:
        cx_verdict(_CHECK, "SUCCESS",
                   f"{ok} migrated {_THIN * 2} {skipped_count} skipped {_THIN * 2} {fail} failed  ({elapsed}s)")
    elif fail == 0 and ok == 0 and total_count == 0:
        cx_verdict(_CHECK, "NO-OP", "no notebooks matched the selected workgroup(s) and filters")
    elif fail == 0 and ok == 0:
        cx_verdict(_CHECK, "NO-OP",
                   f"all notebooks already migrated ({skipped_count} skipped)")
    else:
        cx_verdict(_WARN, "PARTIAL SUCCESS",
                   f"{ok} migrated {_THIN * 2} {skipped_count} skipped {_THIN * 2} {fail} failed  ({elapsed}s)")

    # Failures detail
    failed_rows = [r for r in rows if r["status"].startswith("ERROR") or
                   r["status"] in ("TIMEOUT",) or ("FAIL" in r["status"] and not r["status"].startswith("SKIP"))]
    if failed_rows:
        cx(f"\n  Failures:")
        for r in failed_rows:
            cx(f"    {_CROSS} [{r['workgroup']}] {r['notebook_name']} {_ARROW} {r.get('detail', '')[:60]}")

    # Permission reminder (command was shown in Step 1, just remind here)
    pending_smus_roles = sorted({rec["smus_role"] for rec in role_records
                                 if rec.get("status") == "gaps" and rec.get("smus_role")})
    if pending_smus_roles:
        role_list = ", ".join(r.split("/")[-1] for r in pending_smus_roles)
        cx(f"\n  {_WARN}  Reminder: Grant the missing permissions on {role_list}")
        cx(f"     (see Step 1 above for the exact command)")
        cx(f"     Without this, notebooks will fail with AccessDenied when executed in SMUS.")

    # Next steps
    steps = []
    if args.dry_run:
        steps.append(f"To execute the migration, re-run the same command without the --dry-run flag")
    if not args.dry_run and ok > 0:
        steps.append("Open your migrated notebooks in SageMaker Unified Studio and run them")
    if fail > 0:
        steps.append(f"Retry failed notebooks: add --resume {report_base}.json to your command")
    if skipped_count > 0 and not args.overwrite and not args.dry_run:
        steps.append("Use --overwrite to replace the skipped notebooks with fresh copies")

    if steps:
        cx(f"\n  {chr(8505)}  Next steps:")
        for i, s in enumerate(steps, 1):
            cx(f"     {i}. {s}")

    cx(f"\n  {chr(128196)} Report: {report_base}.json")
    cx(f"  {chr(128203)} Log:    {log_file}")
    cx("")

    meta = {"finished_utc": datetime.fromtimestamp(finished, timezone.utc).isoformat(),
            "elapsed_seconds": elapsed,
            "counts": {"migrated": ok, "failed": fail, "skipped": skipped_count, "total": len(rows)}}

    # Log the full summary to file (verbose)
    log.info("SUMMARY: %d migrated, %d failed, %d skipped, %d total, %ds elapsed",
             ok, fail, skipped_count, len(rows), elapsed)
    for r in rows:
        log.info("  [%s] %s: %s -> %s (%ds)", r["workgroup"], r["notebook_name"],
                 r["status"], r["smus_notebook_id"] or "-", r["duration_s"])

    report.rows = rows  # plan order (the incremental copy is in completion order)
    report.finish(meta)
    return fail == 0


# --------------------------------------------------------------------------- #
# Argument Parsing and Validation
# --------------------------------------------------------------------------- #

def parse_args(args):
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="athena_notebook_migration.py",
        # Exact flag names only: a prefix like --over must not silently enable --overwrite.
        allow_abbrev=False,
        description="Migrates notebooks from Amazon Athena PySpark engine version 3 workgroups "
                    "to Amazon SageMaker Unified Studio projects.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  # Discover what needs to be migrated
  %(prog)s --inventory --region us-west-2

  # Preview migration (no changes made)
  %(prog)s --dry-run --workgroups my-workgroup --domain-id dzd-xxx --project-id abc123 --region us-west-2

  # Migrate a single workgroup
  %(prog)s --workgroups my-workgroup --domain-id dzd-xxx --project-id abc123 --region us-west-2

  # Migrate all workgroups in the account
  %(prog)s --all-workgroups --domain-id dzd-xxx --project-id abc123 --region us-west-2

  # Multi-project migration via config file
  %(prog)s --config map.json --region us-west-2
""")

    # Required (for migration mode)
    parser.add_argument("--domain-id", help="SageMaker Unified Studio domain ID (e.g. dzd-xxxxx)", required=False)
    parser.add_argument("--project-id", help="Target SageMaker Unified Studio project ID", required=False)
    parser.add_argument("--workgroups", nargs="+", help="Athena workgroup name(s) to migrate", required=False)
    parser.add_argument("--all-workgroups", default=False, action='store_true',
                        help="Auto-discover and migrate ALL PySpark engine version 3 workgroups")
    parser.add_argument("--config", help="JSON config file mapping workgroups to project IDs (workgroup_project_map)", required=False)
    parser.add_argument("--region", required=True, help="Destination (SageMaker Unified Studio) region (required)")

    # Authentication
    parser.add_argument("--profile", help="AWS profile for destination account", required=False)
    parser.add_argument("--role-arn", help="IAM role ARN to assume for destination account", required=False)
    parser.add_argument("--source-profile", help="AWS profile for source (Athena) account", required=False)
    parser.add_argument("--source-role-arn", help="IAM role ARN to assume for source account", required=False)
    parser.add_argument("--source-region", help="Source (Athena) region (defaults to --region)", required=False)

    # Behavior
    parser.add_argument("--dry-run", default=False, action='store_true',
                        help="Preview only — no S3 writes, no imports")
    parser.add_argument("--overwrite", default=False, action='store_true',
                        help="Re-import notebooks that already exist in the project; the old copy is deleted only after the new import succeeds")
    parser.add_argument("--yes", default=False, action='store_true',
                        help="Skip interactive confirmation prompt")
    parser.add_argument("--concurrency", type=int, default=1,
                        help=f"Parallel notebook imports (default: 1, max: {MAX_CONCURRENCY})")
    parser.add_argument("--resume", metavar="REPORT_JSON",
                        help="Continue from a prior report JSON: skip notebooks it shows as migrated "
                             "(if they still exist in the project), retry the rest", required=False)

    # Filters
    parser.add_argument("--name-filter", required=False,
                        help="Case-insensitive notebook name filter: a substring (e.g. 'sales'), "
                             "or a glob when it contains * ? [ ] (e.g. 'retail*'). Not a regex.")
    parser.add_argument("--notebooks", required=False,
                        help="Comma-separated Athena notebook IDs or exact notebook names to include")
    parser.add_argument("--since", type=parse_since, required=False,
                        help="Only notebooks modified on/after this date (YYYY-MM-DD)")
    parser.add_argument("--exclude-workgroups", nargs="+", help="Workgroup names to exclude", required=False)

    # Modes
    parser.add_argument("--inventory", default=False, action='store_true',
                        help="List workgroups and notebooks only; do not migrate")

    # Output
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Log verbosity (default: INFO)")
    parser.add_argument("--output-dir", default=".", help="Directory for logs and reports (default: .)")
    parser.add_argument("--log-file", help="Override log file path", required=False)
    parser.add_argument("--report-file", help="Override report base path", required=False)

    return parser.parse_args(args)


def verify_args(args):
    """Verifies parsed arguments for correctness."""
    if args.all_workgroups and args.workgroups:
        raise ValueError("Cannot use both --workgroups and --all-workgroups.")

    if not args.inventory:
        if not args.config:
            if args.all_workgroups:
                if not args.domain_id:
                    raise ValueError("Provide --domain-id with --all-workgroups.")
                if not args.project_id:
                    raise ValueError("Provide --project-id with --all-workgroups.")
            elif not args.workgroups:
                raise ValueError("Provide --workgroups, --all-workgroups, or --config.")

    if args.resume and not os.path.exists(args.resume):
        raise ValueError(f"--resume file not found: {args.resume}")
    if args.config and not os.path.exists(args.config):
        raise ValueError(f"--config file not found: {args.config}")
    if not 1 <= args.concurrency <= MAX_CONCURRENCY:
        raise ValueError(f"--concurrency must be between 1 and {MAX_CONCURRENCY}.")
    if os.path.exists(args.output_dir) and not os.path.isdir(args.output_dir):
        raise ValueError(f"--output-dir '{args.output_dir}' exists and is not a directory.")
    for flag, path in (("--log-file", args.log_file), ("--report-file", args.report_file)):
        if not path:
            continue
        if os.path.isdir(path):
            raise ValueError(f"{flag} '{path}' is a directory; pass a file path.")
        parent = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(parent):
            raise ValueError(f"{flag} '{path}': directory '{parent}' does not exist.")


# --------------------------------------------------------------------------- #
# Main Entrypoint
# --------------------------------------------------------------------------- #

def make_console_safe(streams=None):
    """Replaces characters the console encoding can't show (e.g. cp1252 on Windows) instead of crashing."""
    for stream in streams if streams is not None else (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass  # not a text stream that supports reconfigure (e.g. redirected in tests)


def main(args):
    """Main entrypoint for the migration tool."""
    log_file = None
    make_console_safe()
    try:
        args = parse_args(args)
        verify_args(args)

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        os.makedirs(args.output_dir, exist_ok=True)
        log_file = args.log_file or os.path.join(args.output_dir, f"athena-smus-migration-{ts}.log")
        report_base = args.report_file or os.path.join(args.output_dir, f"athena-smus-migration-report-{ts}")

        # Setup logging: file gets everything, console only gets errors
        set_logging(args.log_level, log_file)

        config = load_config(args.config) if args.config else None

        dest_region = args.region
        dst_session = build_session(dest_region, args.profile, args.role_arn)
        if args.source_profile or args.source_role_arn or args.source_region:
            src_session = build_session(args.source_region or dest_region,
                                        args.source_profile, args.source_role_arn)
        else:
            src_session = dst_session

        if args.inventory:
            ok = do_inventory(src_session, args.source_region or args.region,
                              args.workgroups, args.all_workgroups, report_base, log_file=log_file)
            sys.exit(0 if ok else 1)

        domain, region, pairs = resolve_targets(args, config)
        if args.all_workgroups:
            pairs = [("__ALL_WORKGROUPS__", args.project_id)]

        if not domain or not pairs or any(p is None for _, p in pairs):
            raise ValueError("Provide --domain-id, --project-id and --workgroups "
                             "(or --all-workgroups or --config).")

        ok = do_migrate(src_session, dst_session, domain, dest_region, pairs, args, report_base, log_file=log_file)
        sys.exit(0 if ok else 1)

    except ValueError as error:
        cx(f"\n  {_CROSS} {error}")
        cx(f"\n  Run with --help for usage.")
        sys.exit(2)
    except KeyboardInterrupt:
        cx(f"\n\n  Interrupted by user.")
        sys.exit(3)
    except SystemExit:
        raise
    except Exception as error:
        log.error(str(error))
        log.debug("Traceback:", exc_info=True)
        cx(f"\n  {_CROSS}  Unexpected error: {error}")
        if log_file:
            cx(f"\n  {chr(128203)} Log:    {log_file}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
