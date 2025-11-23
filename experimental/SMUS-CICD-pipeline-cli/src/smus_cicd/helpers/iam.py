"""IAM role management for SMUS projects."""

import logging
import os
from datetime import datetime
from typing import List, Optional

import boto3
import typer

logger = logging.getLogger("smus_cicd.iam")


def _load_trust_policy(account_id: str) -> str:
    """Load and customize trust policy template."""
    resources_dir = os.path.join(os.path.dirname(__file__), "..", "resources")
    trust_policy_path = os.path.join(resources_dir, "project_role_trust_policy.json")

    with open(trust_policy_path, "r") as f:
        trust_policy = f.read()

    return trust_policy.replace("{ACCOUNT_ID}", account_id)


def _load_pass_role_policy(role_arn: str) -> str:
    """Load and customize PassRole policy template."""
    resources_dir = os.path.join(os.path.dirname(__file__), "..", "resources")
    policy_path = os.path.join(resources_dir, "project_role_pass_role_policy.json")

    with open(policy_path, "r") as f:
        policy = f.read()

    return policy.replace("{ROLE_ARN}", role_arn)


def create_or_update_project_role(
    role_name: str,
    policy_arns: List[str],
    account_id: str,
    region: str,
    role_arn: Optional[str] = None,
) -> str:
    """Create new role or update existing role with policies.

    Args:
        role_name: Name for the new role (used only if role_arn is None)
        policy_arns: List of policy ARNs to attach (AWS managed or customer managed)
        account_id: AWS account ID for trust policy
        region: AWS region
        role_arn: Optional existing role ARN to update

    Returns:
        Role ARN (created or provided)
    """
    iam = boto3.client("iam", region_name=region)

    if role_arn:
        # Update existing role - attach additional policies
        existing_role_name = role_arn.split("/")[-1]
        typer.echo(f"✓ Using existing role: {role_arn}")

        if policy_arns:
            _attach_policies(iam, existing_role_name, policy_arns)

        # Ensure inline PassRole policy exists
        pass_role_policy = _load_pass_role_policy(role_arn)
        iam.put_role_policy(
            RoleName=existing_role_name,
            PolicyName="SelfPassRolePolicy",
            PolicyDocument=pass_role_policy,
        )
        typer.echo(f"✅ Ensured inline PassRole policy on {existing_role_name}")

        return role_arn

    # Check if role already exists
    try:
        response = iam.get_role(RoleName=role_name)
        existing_role_arn = response["Role"]["Arn"]

        # Check if role was created by SMUS CLI
        tags = response["Role"].get("Tags", [])
        is_smus_managed = any(
            tag["Key"] == "CreatedBy" and tag["Value"] == "SMUS-CICD" for tag in tags
        )

        if is_smus_managed:
            # Update existing SMUS-managed role (don't delete/recreate)
            typer.echo(f"✓ SMUS-managed role exists: {existing_role_arn}")
            if policy_arns:
                _attach_policies(iam, role_name, policy_arns)
            pass_role_policy = _load_pass_role_policy(existing_role_arn)
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName="SelfPassRolePolicy",
                PolicyDocument=pass_role_policy,
            )
            typer.echo(f"✅ Updated policies on {role_name}")
            return existing_role_arn
        else:
            # Role exists but not managed by SMUS - don't touch it
            typer.echo(f"✓ Role exists (not SMUS-managed): {existing_role_arn}")
            return existing_role_arn

    except iam.exceptions.NoSuchEntityException:
        pass

    # Create new role
    trust_policy = _load_trust_policy(account_id)

    logger.info(f"Creating IAM role: {role_name} at {datetime.utcnow().isoformat()}")

    response = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=trust_policy,
        Description="SMUS project role created by SMUS CLI",
        Tags=[
            {"Key": "CreatedBy", "Value": "SMUS-CICD"},
            {"Key": "ManagedBy", "Value": "SMUS-CLI"},
        ],
    )
    created_role_arn = response["Role"]["Arn"]
    logger.info(
        f"Successfully created role: {created_role_arn} at {datetime.utcnow().isoformat()}"
    )
    typer.echo(f"✅ Created role: {created_role_arn}")

    # Attach policies
    if policy_arns:
        _attach_policies(iam, role_name, policy_arns)

    # Attach inline PassRole policy to allow role to pass itself
    pass_role_policy = _load_pass_role_policy(created_role_arn)
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="SelfPassRolePolicy",
        PolicyDocument=pass_role_policy,
    )
    typer.echo(f"✅ Attached inline PassRole policy to {role_name}")

    # Wait for IAM role to propagate
    import time

    typer.echo("⏳ Waiting 90s for IAM role to propagate...")
    time.sleep(90)

    return created_role_arn


def _attach_policies(iam, role_name: str, policy_arns: List[str]):
    """Attach policies to role, skipping already attached ones."""
    # Get currently attached policies
    attached = set()
    try:
        paginator = iam.get_paginator("list_attached_role_policies")
        for page in paginator.paginate(RoleName=role_name):
            for policy in page["AttachedPolicies"]:
                attached.add(policy["PolicyArn"])
    except Exception as e:
        typer.echo(f"⚠️ Warning: Could not list attached policies: {e}")

    # Attach new policies
    for policy_arn in policy_arns:
        if policy_arn in attached:
            typer.echo(f"  ✓ Policy already attached: {policy_arn}")
            continue

        try:
            iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            typer.echo(f"  ✅ Attached policy: {policy_arn}")
        except Exception as e:
            typer.echo(f"  ❌ Failed to attach policy {policy_arn}: {e}")
            raise


def _delete_role(iam, role_name: str):
    """Delete role and all its policies."""
    # Detach managed policies
    try:
        paginator = iam.get_paginator("list_attached_role_policies")
        for page in paginator.paginate(RoleName=role_name):
            for policy in page["AttachedPolicies"]:
                iam.detach_role_policy(
                    RoleName=role_name, PolicyArn=policy["PolicyArn"]
                )
    except Exception:
        pass

    # Delete inline policies
    try:
        paginator = iam.get_paginator("list_role_policies")
        for page in paginator.paginate(RoleName=role_name):
            for policy_name in page["PolicyNames"]:
                iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
    except Exception:
        pass

    # Delete role
    iam.delete_role(RoleName=role_name)
    typer.echo(f"✅ Deleted role: {role_name}")
