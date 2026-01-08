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


def find_missing_env_vars(data: Union[Dict, List, str]) -> List[str]:
    """
    Find environment variables referenced in data that are not set.

    Args:
        data: YAML data (dict, list, or string)

    Returns:
        List of missing environment variable names (without defaults)
    """
    missing = set()

    def check_value(value):
        if isinstance(value, dict):
            for v in value.values():
                check_value(v)
        elif isinstance(value, list):
            for item in value:
                check_value(item)
        elif isinstance(value, str):
            pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"
            for match in re.finditer(pattern, value):
                var_name = match.group(1)
                has_default = match.group(2) is not None

                # Skip pseudo env vars
                if var_name in ("STS_ACCOUNT_ID", "AWS_ACCOUNT_ID", "STS_REGION"):
                    continue

                # Only flag as missing if no default and not set
                if not has_default and not os.getenv(var_name):
                    missing.add(var_name)

    check_value(data)
    return sorted(missing)


def substitute_env_vars(data: Union[Dict, List, str]) -> Union[Dict, List, str]:
    """
    Recursively substitute environment variables in YAML data.

    Supports ${VAR_NAME} or ${VAR_NAME:default_value} syntax for environment variable substitution.

    Pseudo environment variables (auto-resolved from AWS credentials):
    - AWS_ACCOUNT_ID: Current AWS account ID from STS
    - STS_ACCOUNT_ID: Current AWS account ID from STS (alias for AWS_ACCOUNT_ID)
    - STS_REGION: Current AWS region from boto3 session

    Args:
        data: YAML data (dict, list, or string)

    Returns:
        Data with environment variables substituted

    Raises:
        ValueError: If a required variable (without default) is not found
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
            has_default = match.group(2) is not None
            default_value = match.group(2) if has_default else None

            # Handle pseudo environment variables
            if var_name == "STS_ACCOUNT_ID" or var_name == "AWS_ACCOUNT_ID":
                import boto3

                return boto3.client("sts").get_caller_identity()["Account"]
            elif var_name == "STS_REGION":
                import boto3

                region = boto3.Session().region_name
                if region:
                    return region
                elif has_default:
                    return default_value
                else:
                    raise ValueError(
                        f"Variable ${{{var_name}}} could not be resolved: No AWS region configured"
                    )

            # Regular environment variable lookup
            value = os.getenv(var_name)
            if value is not None:
                return value
            elif has_default:
                return default_value
            else:
                raise ValueError(
                    f"Variable ${{{var_name}}} is not set and has no default value"
                )

        return re.sub(pattern, replace_var, data)
    else:
        return data


def load_yaml(file_path: str, check_missing_vars: bool = True) -> Dict[str, Any]:
    """
    Load and parse YAML file.

    Args:
        file_path: Path to the YAML file
        check_missing_vars: If True, check for missing required env vars before substitution

    Returns:
        Parsed YAML content as dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file contains invalid YAML
        ValueError: If required environment variables are missing
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Application manifest file not found: {file_path}\n"
            f"Please create an application manifest file or specify the correct path using --manifest/-m option."
        )

    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

            # Check for missing required env vars before substitution
            if check_missing_vars:
                missing_vars = find_missing_env_vars(data)
                if missing_vars:
                    raise ValueError(
                        f"Missing required environment variables in {file_path}:\n"
                        + "\n".join(f"  - {var}" for var in missing_vars)
                        + "\n\nPlease set these environment variables before running the command."
                    )

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


def validate_project_exists(
    project_info: Dict[str, Any],
    project_name: str,
    target_name: str,
    allow_create: bool = False,
) -> None:
    """
    Validate that project exists when connecting to AWS.

    Args:
        project_info: Project info dict from get_datazone_project_info
        project_name: Name of the project
        target_name: Name of the target
        allow_create: If True, don't fail if project will be created

    Raises:
        ValueError: If project or domain not found
    """
    # Check if domain lookup failed
    if project_info.get("error"):
        error_msg = project_info.get("error")
        if "Domain not found" in error_msg:
            raise ValueError(
                f"Cannot connect to target '{target_name}': Domain not found.\n"
                f"Please check:\n"
                f"  - Domain tags in manifest match an existing domain\n"
                f"  - Domain region is correct\n"
                f"  - AWS credentials have access to the domain"
            )
        raise ValueError(f"Cannot connect to target '{target_name}': {error_msg}")

    # Check if project exists
    if project_info.get("status") == "NOT_FOUND":
        if allow_create:
            # Project will be created during deployment
            return
        raise ValueError(
            f"Cannot connect to target '{target_name}': Project '{project_name}' not found.\n"
            f"Please check:\n"
            f"  - Project name is correct\n"
            f"  - Project exists in the domain\n"
            f"  - AWS credentials have access to the project\n"
            f"Or set 'create: true' in the project configuration to create it during deployment."
        )


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
        project_members = _get_project_owners(domain_id, project_id, region)
        project_connections = _get_project_connections(
            project_name, domain_id, project_id, region
        )

        result = {
            "projectId": project_id,
            "project_id": project_id,  # Keep backward compatibility
            "domain_id": domain_id,  # Add for bootstrap handlers
            "status": project_details.get("status", "Unknown"),
            "owners": project_members.get("owners", []),
            "contributors": project_members.get("contributors", []),
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
    """Get list of project owners and contributors."""
    owners = []
    contributors = []

    try:
        datazone_client = datazone._get_datazone_client(region)
        memberships_response = datazone_client.list_project_memberships(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        for member in memberships_response.get("members", []):
            designation = member.get("designation")
            member_name = _extract_member_name(member, domain_id, datazone_client)

            if member_name:
                if designation == "PROJECT_OWNER":
                    owners.append(member_name)
                elif designation == "PROJECT_CONTRIBUTOR":
                    contributors.append(member_name)

    except Exception as e:
        from .logger import get_logger

        logger = get_logger("utils")
        logger.warning(f"Failed to get project members (non-critical): {e}")

    return {"owners": owners, "contributors": contributors}


def _extract_member_name(
    member: Dict[str, Any], domain_id: str, datazone_client
) -> Optional[str]:
    """Extract readable member name from member details (user or group)."""
    member_details = member.get("memberDetails", {})

    # Check for user
    if "user" in member_details:
        user_id = member_details["user"].get("userId")
        if user_id:
            return _extract_owner_name_from_user(user_id, domain_id, datazone_client)

    # Check for group (IAM role)
    if "group" in member_details:
        group_id = member_details["group"].get("groupId")
        if group_id:
            try:
                profile = datazone_client.get_group_profile(
                    domainIdentifier=domain_id, groupIdentifier=group_id
                )
                # Return role ARN if available, otherwise group name or ID
                return (
                    profile.get("rolePrincipalArn")
                    or profile.get("groupName")
                    or group_id
                )
            except Exception as e:
                from .logger import get_logger

                logger = get_logger("utils")
                logger.warning(f"Failed to get group profile for {group_id}: {e}")
                return group_id

    return None


def _extract_owner_name_from_user(
    user_id: str, domain_id: str, datazone_client
) -> Optional[str]:
    """Extract readable owner name from user ID."""
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


def _extract_owner_name(
    member: Dict[str, Any], domain_id: str, datazone_client
) -> Optional[str]:
    """Extract readable owner name from member details (backward compatibility)."""
    return _extract_member_name(member, domain_id, datazone_client)


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
    """Get project connections using the centralized connections helper."""
    from . import connections
    from .logger import get_logger

    logger = get_logger("utils")

    try:
        return connections.get_project_connections(project_id, domain_id, region)
    except Exception as e:
        logger.error(f"Failed to get project connections for {project_name}: {e}")
        return {}
