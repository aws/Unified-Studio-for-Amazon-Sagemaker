"""IAM role management for SMUS projects."""

import os
from typing import List, Optional

import boto3
import typer


def _load_trust_policy(account_id: str) -> str:
    """Load and customize trust policy template."""
    resources_dir = os.path.join(os.path.dirname(__file__), "..", "resources")
    trust_policy_path = os.path.join(resources_dir, "project_role_trust_policy.json")

    with open(trust_policy_path, "r") as f:
        trust_policy = f.read()

    return trust_policy.replace("{ACCOUNT_ID}", account_id)


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

        return role_arn

    # Create new role
    trust_policy = _load_trust_policy(account_id)

    try:
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
        typer.echo(f"✅ Created role: {created_role_arn}")

        # Attach policies
        if policy_arns:
            _attach_policies(iam, role_name, policy_arns)

        # Wait for IAM role to propagate
        import time

        typer.echo("⏳ Waiting for IAM role to propagate...")
        time.sleep(30)

        return created_role_arn

    except iam.exceptions.EntityAlreadyExistsException:
        # Role exists, get its ARN and attach policies
        response = iam.get_role(RoleName=role_name)
        existing_role_arn = response["Role"]["Arn"]
        typer.echo(f"✓ Role already exists: {existing_role_arn}")

        if policy_arns:
            _attach_policies(iam, role_name, policy_arns)

        return existing_role_arn


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
