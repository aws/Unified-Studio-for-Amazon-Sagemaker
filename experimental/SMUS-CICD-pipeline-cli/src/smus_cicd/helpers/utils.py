"""Utility functions for SMUS CLI."""

import os
import yaml
import boto3
from pathlib import Path
from typing import Dict, Any, Optional, List
from . import datazone


def load_yaml(file_path: str) -> Dict[str, Any]:
    """
    Load and parse YAML file.

    Args:
        file_path: Path to the YAML file

    Returns:
        Parsed YAML content as dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file contains invalid YAML
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Pipeline manifest file not found: {file_path}\n"
            f"Please create a pipeline manifest file or specify the correct path using --pipeline/-p option."
        )

    try:
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML syntax in {file_path}: {e}")


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from specified path.

    Args:
        config_path: Path to configuration file (optional)

    Returns:
        Configuration dictionary (empty if file doesn't exist)
    """
    if config_path is None:
        # Use package-relative path
        config_path = Path(__file__).parent / "cloudformation" / "config.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        return {}

    return load_yaml(str(config_path))


def get_domain_id(config: Dict[str, Any]) -> Optional[str]:
    """
    Get DataZone domain ID from CloudFormation exports.

    Args:
        config: Configuration dictionary containing region and stack info

    Returns:
        Domain ID if found, None otherwise

    Raises:
        ValueError: If region is not specified in configuration
    """
    region = config.get("region")
    if not region:
        raise ValueError("Region must be specified in configuration")

    domain_stack_name = config.get("stacks", {}).get("domain", "cicd-test-domain-stack")

    cf_client = boto3.client("cloudformation", region_name=region)

    try:
        # Get stack outputs
        response = cf_client.describe_stacks(StackName=domain_stack_name)
        stacks = response.get("Stacks", [])

        if not stacks:
            return None

        outputs = stacks[0].get("Outputs", [])
        return _extract_domain_id_from_outputs(outputs)

    except Exception:
        return None


def _extract_domain_id_from_outputs(outputs: List[Dict[str, Any]]) -> Optional[str]:
    """
    Extract domain ID from CloudFormation stack outputs.

    Args:
        outputs: List of CloudFormation stack outputs

    Returns:
        Domain ID if found, None otherwise
    """
    for output in outputs:
        if output.get("OutputKey") == "DomainId":
            return output.get("OutputValue")
    return None


def get_datazone_project_info(
    project_name: str, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get DataZone project ID, status, owners, and connections.

    Args:
        project_name: Name of the project to retrieve info for
        config: Configuration dictionary

    Returns:
        Dictionary containing project information or error details
    """
    try:
        region = _get_region_from_config(config)
        domain_id = _resolve_domain_id(config, region)

        if not domain_id:
            return {"error": "Domain not found"}

        project_id = _get_project_id(project_name, domain_id, region)
        if not project_id:
            return {"error": f"Project {project_name} not found"}

        project_details = _get_project_details(domain_id, project_id, region)
        project_owners = _get_project_owners(domain_id, project_id, region)
        project_connections = _get_project_connections(project_name, config, region)

        return {
            "projectId": project_id,
            "project_id": project_id,  # Keep backward compatibility
            "status": project_details.get("status", "Unknown"),
            "owners": project_owners,
            "connections": project_connections,
        }

    except Exception as e:
        return {"error": str(e)}


def _get_region_from_config(config: Dict[str, Any]) -> str:
    """Get region from configuration, raising error if not found."""
    region = config.get("region")
    if not region:
        raise ValueError("Region must be specified in configuration")
    return region


def _resolve_domain_id(config: Dict[str, Any], region: str) -> Optional[str]:
    """Resolve domain ID from configuration or by name lookup."""
    # Try to get domain ID from CloudFormation exports first
    domain_id = get_domain_id(config)

    if not domain_id:
        # Try to get domain ID by name
        domain_name = config.get("domain", {}).get("name")
        if domain_name:
            domain_id = datazone.get_domain_id_by_name(domain_name, region)

    return domain_id


def _get_project_id(project_name: str, domain_id: str, region: str) -> Optional[str]:
    """Get project ID by name."""
    return datazone.get_project_id_by_name(project_name, domain_id, region)


def _get_project_details(
    domain_id: str, project_id: str, region: str
) -> Dict[str, Any]:
    """Get basic project details from DataZone."""
    datazone_client = boto3.client("datazone", region_name=region)
    project_response = datazone_client.get_project(
        domainIdentifier=domain_id, identifier=project_id
    )

    return {"status": project_response.get("projectStatus", "Unknown")}


def _get_project_owners(domain_id: str, project_id: str, region: str) -> List[str]:
    """Get list of project owners."""
    owners = []

    try:
        datazone_client = boto3.client("datazone", region_name=region)
        memberships_response = datazone_client.list_project_memberships(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        for member in memberships_response.get("members", []):
            if member.get("designation") == "PROJECT_OWNER":
                owner_name = _extract_owner_name(member, domain_id, datazone_client)
                if owner_name:
                    owners.append(owner_name)

    except Exception:
        pass  # Owners are optional

    return owners


def _extract_owner_name(
    member: Dict[str, Any], domain_id: str, datazone_client
) -> Optional[str]:
    """Extract readable owner name from member details."""
    member_details = member.get("memberDetails", {})
    if "user" not in member_details:
        return None

    user_id = member_details["user"].get("userId")
    if not user_id:
        return None

    try:
        user_profile = datazone_client.get_user_profile(
            domainIdentifier=domain_id, userIdentifier=user_id
        )

        return _get_readable_user_name(user_profile, user_id)

    except Exception:
        return user_id


def _get_readable_user_name(user_profile: Dict[str, Any], fallback_id: str) -> str:
    """Get readable user name from user profile."""
    details = user_profile.get("details", {})

    # For IDC users, try to get the user name from different fields
    if "sso" in details:
        sso_details = details["sso"]
        user_name = sso_details.get("username") or sso_details.get("firstName")
        if user_name:
            return user_name
    elif "iam" in details:
        iam_arn = details["iam"].get("arn", "")
        if iam_arn:
            return iam_arn.split("/")[-1]

    # Fallback to user ID if no readable name found
    return fallback_id


def _get_project_connections(
    project_name: str, config: Dict[str, Any], region: str
) -> Dict[str, Any]:
    """Get project connections using centralized logic."""
    try:
        from . import connections

        domain_name = config.get("domain", {}).get("name")
        if domain_name:
            return connections.get_project_connections(
                project_name, domain_name, region
            )
        else:
            return {}
    except Exception:
        return {}  # Connections are optional
