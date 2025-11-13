"""Utility functions for SMUS CLI."""

import os
import re
from typing import Any, Dict, List, Optional, Union

import boto3
import yaml

from . import datazone


def build_domain_config(target_config) -> Dict[str, Any]:
    """
    Build domain configuration from target config.

    Args:
        target_config: Target configuration object with domain attribute

    Returns:
        Dictionary with domain configuration including region, name (if present), and tags (if present)
    """
    config = load_config()
    config["domain"] = {
        "region": target_config.domain.region,
    }
    if target_config.domain.name:
        config["domain"]["name"] = target_config.domain.name
        config["domain_name"] = target_config.domain.name
    if target_config.domain.tags:
        config["domain"]["tags"] = target_config.domain.tags
    config["region"] = target_config.domain.region
    return config


def substitute_env_vars(data: Union[Dict, List, str]) -> Union[Dict, List, str]:
    """
    Recursively substitute environment variables in YAML data.

    Supports ${VAR_NAME} syntax for environment variable substitution.

    Pseudo environment variables (auto-resolved from AWS credentials):
    - STS_ACCOUNT_ID: Current AWS account ID from STS
    - STS_REGION: Current AWS region from boto3 session

    Args:
        data: YAML data (dict, list, or string)

    Returns:
        Data with environment variables substituted
    """
    if isinstance(data, dict):
        return {key: substitute_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [substitute_env_vars(item) for item in data]
    elif isinstance(data, str):
        # Pattern to match ${VAR_NAME} or ${VAR_NAME:default_value}
        pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"

        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""

            # Handle pseudo environment variables
            if var_name == "STS_ACCOUNT_ID":
                import boto3

                return boto3.client("sts").get_caller_identity()["Account"]
            elif var_name == "STS_REGION":
                import boto3

                return boto3.Session().region_name or default_value

            # Regular environment variable lookup
            return os.getenv(var_name, default_value)

        return re.sub(pattern, replace_var, data)
    else:
        return data


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
            f"Bundle manifest file not found: {file_path}\n"
            f"Please create a bundle manifest file or specify the correct path using --bundle/-b option."
        )

    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
            return substitute_env_vars(data)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML syntax in {file_path}: {e}")


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration - returns empty dict as all config comes from pipeline manifest.

    Args:
        config_path: Ignored - kept for backward compatibility

    Returns:
        Empty configuration dictionary
    """
    return {}


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
    region = _get_region_from_config(config)
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
            raise Exception(
                "Domain not found - check domain name/tags in manifest or CloudFormation stack"
            )

        project_id = _get_project_id(project_name, domain_id, region)
        if not project_id:
            # Project doesn't exist - return minimal info indicating this
            return {
                "projectId": None,
                "status": "NOT_FOUND",
                "name": project_name,
                "owners": [],
                "connections": {},
            }

        project_details = _get_project_details(domain_id, project_id, region)
        project_owners = _get_project_owners(domain_id, project_id, region)
        project_connections = _get_project_connections(
            project_name, domain_id, project_id, region
        )

        result = {
            "projectId": project_id,
            "project_id": project_id,  # Keep backward compatibility
            "status": project_details.get("status", "Unknown"),
            "owners": project_owners,
            "connections": project_connections,
        }
        return result

    except Exception as e:
        from .logger import get_logger

        logger = get_logger("utils")
        logger.error(f"Error getting DataZone project info for {project_name}: {e}")
        return {"error": str(e)}


def _get_region_from_config(config: Dict[str, Any]) -> str:
    """Get region from configuration, using domain.region as the single source of truth."""
    from .logger import get_logger

    logger = get_logger("utils")

    # Use domain.region from pipeline manifest as the single source of truth
    domain_region = config.get("domain", {}).get("region")
    if domain_region:
        logger.debug(f"Using domain.region from config: {domain_region}")
        return domain_region

    # Fallback to aws.region in config for backward compatibility
    region = config.get("aws", {}).get("region")
    if region:
        logger.debug(f"Using region from config: {region}")
        return region

    raise ValueError(
        "Region must be specified in domain.region or aws.region configuration"
    )


def _resolve_domain_id(config: Dict[str, Any], region: str) -> Optional[str]:
    """Resolve domain ID from configuration or by name/tags lookup."""
    from .logger import get_logger

    logger = get_logger("utils")

    # Try to get domain ID from CloudFormation exports first
    domain_id = get_domain_id(config)

    if not domain_id:
        # Try to resolve domain by name or tags
        domain_config = config.get("domain", {})
        domain_name = domain_config.get("name")
        domain_tags = domain_config.get("tags")

        if domain_name or domain_tags:
            try:
                domain_id, _ = datazone.resolve_domain_id(
                    domain_name=domain_name, domain_tags=domain_tags, region=region
                )
            except Exception as e:
                logger.error(f"Failed to resolve domain: {str(e)}")
                raise Exception(f"Failed to resolve domain: {str(e)}")

    return domain_id


def _get_project_id(project_name: str, domain_id: str, region: str) -> Optional[str]:
    """Get project ID by name."""
    return datazone.get_project_id_by_name(project_name, domain_id, region)


def _get_project_details(
    domain_id: str, project_id: str, region: str
) -> Dict[str, Any]:
    """Get basic project details from DataZone."""
    datazone_client = datazone._get_datazone_client(region)
    project_response = datazone_client.get_project(
        domainIdentifier=domain_id, identifier=project_id
    )

    return {"status": project_response.get("projectStatus", "Unknown")}


def _get_project_owners(domain_id: str, project_id: str, region: str) -> List[str]:
    """Get list of project owners."""
    owners = []

    try:
        datazone_client = datazone._get_datazone_client(region)
        memberships_response = datazone_client.list_project_memberships(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        for member in memberships_response.get("members", []):
            if member.get("designation") == "PROJECT_OWNER":
                owner_name = _extract_owner_name(member, domain_id, datazone_client)
                if owner_name:
                    owners.append(owner_name)

    except Exception as e:
        from .logger import get_logger

        logger = get_logger("utils")
        logger.warning(f"Failed to get project owners (non-critical): {e}")

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

    except Exception as e:
        from .logger import get_logger

        logger = get_logger("utils")
        logger.warning(
            f"Failed to get user profile for {user_id}, using ID as fallback: {e}"
        )
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
    project_name: str, domain_id: str, project_id: str, region: str
) -> Dict[str, Any]:
    """Get project connections using domain_id and project_id directly."""
    from .logger import get_logger

    logger = get_logger("utils")

    try:
        datazone_client = datazone._get_datazone_client(region)

        connections_dict = {}
        next_token = None

        # Paginate through all connections
        while True:
            list_params = {
                "domainIdentifier": domain_id,
                "projectIdentifier": project_id,
                "maxResults": 50,
            }
            if next_token:
                list_params["nextToken"] = next_token

            response = datazone_client.list_connections(**list_params)

            for conn in response.get("items", []):
                conn_name = conn.get("name", "unknown")
                conn_type = conn.get("type", "")

                # Check if WORKFLOWS_MWAA is actually serverless
                if conn_type == "WORKFLOWS_MWAA":
                    props = conn.get("props", {})
                    if "workflowsServerlessProperties" in props:
                        conn_type = "WORKFLOWS_SERVERLESS"

                connections_dict[conn_name] = {
                    "connectionId": conn.get("connectionId", ""),
                    "type": conn_type,
                    "region": region,
                }

                # Add S3 URI if it's an S3 connection
                if conn_type == "S3":
                    props = conn.get("props", {}).get("s3Properties", {})
                    if props.get("s3Uri"):
                        connections_dict[conn_name]["s3Uri"] = props["s3Uri"]

                # Add workgroup info for ATHENA connections
                elif conn_type == "ATHENA":
                    props = conn.get("props", {}).get("athenaProperties", {})
                    if props.get("workgroupName"):
                        connections_dict[conn_name]["workgroupName"] = props[
                            "workgroupName"
                        ]

                # Add SPARK connection properties
                elif conn_type == "SPARK":
                    # Need to get full connection details for sparkGlueProperties and configurations
                    try:
                        detail_response = datazone_client.get_connection(
                            domainIdentifier=domain_id,
                            identifier=conn.get("connectionId", ""),
                        )
                        props = detail_response.get("props", {}).get(
                            "sparkGlueProperties", {}
                        )
                        if props:
                            connections_dict[conn_name]["sparkGlueProperties"] = props

                        configurations = detail_response.get("configurations", [])
                        if configurations:
                            connections_dict[conn_name][
                                "configurations"
                            ] = configurations
                    except Exception as e:
                        logger.warning(f"Failed to get SPARK connection details: {e}")

            # Check for next page
            next_token = response.get("nextToken")
            if not next_token:
                break

        return connections_dict

    except Exception as e:
        logger.error(f"Failed to get project connections for {project_name}: {e}")
        return {}
