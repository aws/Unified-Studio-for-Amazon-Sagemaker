"""Plan and grant the project's permission to pass a job role to Glue."""
from __future__ import annotations

import hashlib
import json
import re

from botocore.exceptions import ClientError

from . import discover


def plan(iam, datazone, domain_id: str, project_id: str, job_role: str) -> dict:
    project_role = discover.resolve_project_role(datazone, domain_id, project_id)
    if not project_role:
        raise LookupError(f"No project execution role found for project {project_id}")
    if not job_role.startswith("arn:"):
        job_role = iam.get_role(RoleName=job_role.rsplit("/", 1)[-1])["Role"]["Arn"]
    prefix = project_role.split(":role/", 1)[0] + ":role/"
    if (not job_role.startswith(prefix)
            or not re.fullmatch(r"[A-Za-z0-9+=,.@_/-]+", job_role[len(prefix):])):
        raise ValueError("Job role must be an exact IAM role ARN in the project's account")

    # Separate policies avoid read/modify/write races between different job roles.
    policy_name = "SMUSGlueJobPassRole-" + hashlib.sha256(job_role.encode()).hexdigest()[:20]
    document = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow", "Action": "iam:PassRole", "Resource": job_role,
            "Condition": {"StringEquals": {"iam:PassedToService": "glue.amazonaws.com"}},
        }],
    }
    role_name = project_role.rsplit("/", 1)[-1]
    try:
        existing = iam.get_role_policy(RoleName=role_name, PolicyName=policy_name)["PolicyDocument"]
    except ClientError as error:
        if error.response["Error"]["Code"] != "NoSuchEntity":
            raise
        existing = None
    if existing is not None and existing != document:
        raise ValueError(f"Conflicting IAM policy {policy_name} on {project_role}; inspect before retrying")
    return {
        "projectRoleArn": project_role, "roleName": role_name,
        "policyName": policy_name, "policyDocument": document,
        "needsUpdate": existing is None,
    }


def apply(iam, grant: dict) -> None:
    if grant["needsUpdate"]:
        iam.put_role_policy(
            RoleName=grant["roleName"], PolicyName=grant["policyName"],
            PolicyDocument=json.dumps(grant["policyDocument"]),
        )
