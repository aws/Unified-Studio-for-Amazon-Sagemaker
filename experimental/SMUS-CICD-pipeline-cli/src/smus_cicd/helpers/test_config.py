"""Helper to generate test configuration from project context."""

from typing import Any, Dict

import boto3


def generate_test_config(
    project_name: str,
    project_id: str,
    domain_id: str,
    domain_name: str,
    region: str,
    target_name: str,
    env_vars: Dict[str, str] = None,
) -> Dict[str, Any]:
    """
    Generate test configuration with project context.

    Args:
        project_name: Project name
        project_id: Project ID (already resolved)
        domain_id: Domain ID
        domain_name: Domain name
        region: AWS region
        target_name: Target name
        env_vars: Optional environment variables

    Returns:
        Dictionary with test configuration
    """
    # Get AWS account ID
    sts = boto3.client("sts", region_name=region)
    account_id = sts.get_caller_identity()["Account"]

    config = {
        "region": region,
        "account_id": account_id,
        "project_id": project_id,
        "project_name": project_name,
        "domain_id": domain_id,
        "domain_name": domain_name,
        "target_name": target_name,
        "env": env_vars or {},
    }

    return config
