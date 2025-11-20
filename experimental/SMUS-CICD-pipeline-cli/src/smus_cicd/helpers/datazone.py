import os
import time
from time import sleep
from typing import Dict, List, Optional, Tuple

"""
DataZone integration functions for SMUS CI/CD CLI.
"""

import boto3
import typer


def _get_datazone_client(region: str):
    """Create DataZone client with optional custom endpoint from environment."""
    endpoint_url = os.environ.get("DATAZONE_ENDPOINT_URL")
    if endpoint_url:
        return boto3.client("datazone", region_name=region, endpoint_url=endpoint_url)
    return boto3.client("datazone", region_name=region)


def _get_datazone_internal_client(region: str):
    """Create DataZone-internal client for project operations with customerProvidedRoleConfigs support."""
    endpoint_url = os.environ.get("DATAZONE_ENDPOINT_URL")
    if endpoint_url:
        return boto3.client(
            "datazone-internal", region_name=region, endpoint_url=endpoint_url
        )
    return boto3.client("datazone-internal", region_name=region)


def resolve_domain_id(
    domain_name: Optional[str] = None,
    domain_tags: Optional[Dict[str, str]] = None,
    region: str = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve domain ID by name, tags, or auto-detect if only one domain exists.

    Args:
        domain_name: Optional domain name to search for
        domain_tags: Optional dict with tag key-value pairs (e.g., {"purpose": "smus-cicd-testing", "STAGE": "DEV"})
                     All tags must match for a domain to be selected
        region: AWS region

    Returns:
        Tuple of (domain_id, domain_name) or (None, None) if not found

    Raises:
        Exception: If multiple domains found without specific criteria
    """
    try:
        datazone_client = _get_datazone_client(region)
        response = datazone_client.list_domains()
        domains = response.get("items", [])

        if not domains:
            return None, None

        # Filter by name if provided
        if domain_name:
            for domain in domains:
                if domain.get("name") == domain_name:
                    return domain.get("id"), domain.get("name")
            return None, None

        # Filter by tags if provided - ALL tags must match
        if domain_tags:
            matching_domains = []
            for domain in domains:
                domain_arn = domain.get("arn")
                tags_response = datazone_client.list_tags_for_resource(
                    resourceArn=domain_arn
                )
                tags = tags_response.get("tags", {})

                # Check if all provided tags match
                if all(tags.get(k) == v for k, v in domain_tags.items()):
                    matching_domains.append(domain)

            if len(matching_domains) == 0:
                return None, None
            elif len(matching_domains) == 1:
                return matching_domains[0].get("id"), matching_domains[0].get("name")
            else:
                tag_str = ", ".join(f"{k}={v}" for k, v in domain_tags.items())
                raise Exception(
                    f"Multiple domains found with tags {tag_str}. Please specify domain name or add more specific tags."
                )

        # Auto-detect: only one domain exists
        if len(domains) == 1:
            return domains[0].get("id"), domains[0].get("name")
        else:
            raise Exception(
                f"Multiple domains found in region {region}. Please specify domain name or tags."
            )

    except Exception as e:
        if "Multiple domains" in str(e):
            raise
        # Log the actual error before re-raising
        from .logger import get_logger

        logger = get_logger("datazone")
        logger.error(f"Error resolving domain: {e}")
        raise


def get_project_user_role_arn(project_name: str, domain_name: str, region: str) -> str:
    """Get the user role ARN for a DataZone project from its tooling environment."""
    try:
        # Get domain and project IDs
        domain_id = get_domain_id_by_name(domain_name, region)
        if not domain_id:
            return None

        project_id = get_project_id_by_name(project_name, domain_id, region)
        if not project_id:
            return None

        # List environments to find tooling environment
        datazone_client = _get_datazone_client(region)
        environments_response = datazone_client.list_environments(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        # Find tooling environment
        for env in environments_response.get("items", []):
            if "tooling" in env.get("name", "").lower():
                # Get environment details
                env_detail = datazone_client.get_environment(
                    domainIdentifier=domain_id, identifier=env.get("id")
                )

                # Look for userRoleArn in provisioned resources
                for resource in env_detail.get("provisionedResources", []):
                    if resource.get("name") == "userRoleArn":
                        return resource.get("value")

        return None

    except Exception as e:
        from .logger import get_logger

        logger = get_logger("datazone")
        logger.error(f"Failed to get project user role ARN for {project_name}: {e}")
        return None


def get_domain_id_by_name(domain_name, region):
    """Get DataZone domain ID by searching domains by name. Returns None if not found."""
    domain_id, _ = resolve_domain_id(domain_name=domain_name, region=region)
    return domain_id


def get_default_project_profile(domain_id, region):
    """Get the default project profile for a domain. Returns first available profile."""
    try:
        datazone_client = _get_datazone_client(region)
        response = datazone_client.list_project_profiles(domainIdentifier=domain_id)
        profiles = response.get("items", [])

        if not profiles:
            return None

        # Return first profile as default
        return profiles[0]["name"]
    except Exception as e:
        typer.echo(f"⚠️ Could not get project profiles: {e}", err=True)
        return None


def list_all_projects(domain_id, region):
    """List all projects in a domain with proper pagination handling."""
    datazone_client = _get_datazone_client(region)
    all_projects = []
    next_token = None

    while True:
        params = {"domainIdentifier": domain_id}
        if next_token:
            params["nextToken"] = next_token

        response = datazone_client.list_projects(**params)
        all_projects.extend(response.get("items", []))

        next_token = response.get("nextToken")
        if not next_token:
            break

    return all_projects


def get_project_by_name(project_name, domain_id, region):
    """Get DataZone project by name with proper pagination handling. Returns None if not found."""
    try:
        projects = list_all_projects(domain_id, region)

        for project in projects:
            if project.get("name") == project_name:
                return project

        return None
    except Exception as e:
        # Check if this is a permission error
        error_str = str(e)
        if any(
            perm_error in error_str.lower()
            for perm_error in [
                "accessdenied",
                "access denied",
                "unauthorized",
                "forbidden",
                "permission",
                "not authorized",
                "insufficient privileges",
            ]
        ):
            typer.echo(
                f"❌ Error: Insufficient permissions to list projects in domain {domain_id}: {str(e)}",
                err=True,
            )
        else:
            typer.echo(f"❌ Error finding project {project_name}: {str(e)}", err=True)
        raise Exception(f"Failed to lookup project {project_name}: {e}")


def get_project_id_by_name(project_name, domain_id, region):
    """Get DataZone project ID by searching projects by name. Returns None if not found."""
    try:
        project = get_project_by_name(project_name, domain_id, region)
        return project.get("id") if project else None

    except Exception as e:
        # Check if this is a permission error
        error_str = str(e)
        if any(
            perm_error in error_str.lower()
            for perm_error in [
                "accessdenied",
                "access denied",
                "unauthorized",
                "forbidden",
                "permission",
                "not authorized",
                "insufficient privileges",
            ]
        ):
            typer.echo(f"❌ AWS Permission Error: {error_str}", err=True)
            typer.echo(
                "Check if the role has DataZone permissions to list projects.", err=True
            )
        else:
            typer.echo(
                f"❌ Error finding project by name {project_name}: {str(e)}", err=True
            )
        # Re-raise permission/API errors, but not "not found" errors
        raise Exception(f"Failed to lookup project {project_name}: {e}")


def create_environment_and_wait(domain_id, project_id, env_name, target_name, region):
    """Create DataZone environment and wait for it to be ACTIVE."""
    try:
        datazone_client = _get_datazone_client(region)

        # Check if environment already exists
        try:
            environments_response = datazone_client.list_environments(
                domainIdentifier=domain_id, projectIdentifier=project_id
            )
            typer.echo(
                f"🔍 DEBUG: Found {len(environments_response.get('items', []))} existing environments"
            )

            environment_name = f"{target_name}-{env_name.lower().replace(' ', '-')}-env"
            for env in environments_response.get("items", []):
                existing_name = env.get("name")
                existing_status = env.get("status")
                existing_id = env.get("id")
                typer.echo(
                    f"🔍 DEBUG: Checking existing environment: {existing_name} (status: {existing_status})"
                )

                if existing_name == environment_name:
                    if existing_status == "ACTIVE":
                        typer.echo(
                            f"✅ Environment '{env_name}' already exists and is ACTIVE"
                        )
                        return True
                    elif existing_status == "CREATING":
                        typer.echo(
                            f"⏳ Environment '{env_name}' is already being created, waiting for completion..."
                        )
                        # Wait for existing environment to complete
                        return _wait_for_environment_completion(
                            datazone_client, domain_id, existing_id
                        )
                    elif existing_status in ["FAILED", "CANCELLED"]:
                        typer.echo(
                            f"⚠️ Environment '{env_name}' exists but is in {existing_status} state"
                        )
                        # Could delete and recreate, but for now just fail
                        return False

        except Exception as list_error:
            typer.echo(f"🔍 DEBUG: Could not check existing environments: {list_error}")

        # Get environment configuration ID
        config_id = get_environment_configuration_id(
            datazone_client, domain_id, env_name
        )
        if not config_id:
            typer.echo(f"❌ Environment configuration '{env_name}' not found")
            return False

        # Create environment
        environment_name = f"{target_name}-{env_name.lower().replace(' ', '-')}-env"
        typer.echo(f"🔧 Creating environment via DataZone API: {environment_name}")
        typer.echo(f"🔍 DEBUG: Using configuration ID: {config_id}")

        response = datazone_client.create_environment(
            domainIdentifier=domain_id,
            projectIdentifier=project_id,
            name=environment_name,
            environmentConfigurationId=config_id,
            description=f"Environment for {target_name} target - {env_name}",
        )

        environment_id = response.get("id")
        typer.echo(f"✅ Environment created successfully: {environment_id}")
        typer.echo(f"🔍 DEBUG: Environment status: {response.get('status')}")

        # Wait for environment to be fully provisioned
        typer.echo("⏳ Waiting for environment to be fully provisioned...")
        return _wait_for_environment_completion(
            datazone_client, domain_id, environment_id
        )

    except Exception as e:
        typer.echo(f"❌ Error creating environment: {e}")
        return False


def _wait_for_environment_completion(datazone_client, domain_id, environment_id):
    """Wait for an existing environment to complete provisioning."""
    max_attempts = 120  # 20 minutes max (10 seconds * 120)
    attempt = 0

    while attempt < max_attempts:
        try:
            env_response = datazone_client.get_environment(
                domainIdentifier=domain_id, identifier=environment_id
            )
            status = env_response.get("status")
            typer.echo(
                f"🔍 DEBUG: Environment status check {attempt + 1}/{max_attempts}: {status}"
            )

            if status == "ACTIVE":
                typer.echo("✅ Environment is now ACTIVE and ready")
                return True
            elif status in ["FAILED", "CANCELLED"]:
                typer.echo(f"❌ Environment creation failed with status: {status}")
                return False

            # Wait 10 seconds before next check
            time.sleep(10)
            attempt += 1

        except Exception as e:
            typer.echo(f"⚠️ Error checking environment status: {e}")
            attempt += 1
            time.sleep(10)

    if attempt >= max_attempts:
        typer.echo("⚠️ Timeout waiting for environment to become ACTIVE")
        return False


def get_environment_configuration_id(datazone_client, domain_id, env_name):
    """Get environment configuration ID by name."""
    try:
        # List environment configurations
        configs_response = datazone_client.list_environment_configurations(
            domainIdentifier=domain_id
        )

        for config in configs_response.get("items", []):
            config_name = config.get("name")
            config_id = config.get("id")

            if config_name == env_name:
                return config_id

        return None

    except Exception as e:
        typer.echo(f"❌ Error getting environment configuration: {e}")
        return None


def wait_for_data_source_runs_completion(
    domain_name, project_id, region, max_wait_seconds=300
):
    """Wait for any running data source runs to complete."""
    try:
        domain_id = get_domain_id_by_name(domain_name, region)
        if not domain_id:
            return

        datazone_client = _get_datazone_client(region)

        # List data sources in the project
        data_sources_response = datazone_client.list_data_sources(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        start_time = time.time()

        while time.time() - start_time < max_wait_seconds:
            running_runs = []

            for data_source in data_sources_response.get("items", []):
                data_source_id = data_source["dataSourceId"]

                # List runs for this data source
                runs_response = datazone_client.list_data_source_runs(
                    domainIdentifier=domain_id, dataSourceIdentifier=data_source_id
                )

                # Check for running runs
                for run in runs_response.get("items", []):
                    if run.get("status") == "RUNNING":
                        running_runs.append(run["id"])

            if not running_runs:
                print("All data source runs completed")
                return

            print(f"Waiting for {len(running_runs)} data source runs to complete...")
            sleep(10)

        print(
            f"Warning: Some data source runs still running after {max_wait_seconds} seconds"
        )

    except Exception as e:
        print(f"Warning: Error waiting for data source runs: {str(e)}")


def delete_project_custom_form_types(domain_name, project_id, region):
    """Delete custom form types owned by a project that start with SageMakerUnifiedStudioScheduleFormType."""
    try:
        domain_id = get_domain_id_by_name(domain_name, region)
        if not domain_id:
            raise Exception(f"Domain '{domain_name}' not found")

        datazone_client = _get_datazone_client(region)

        # Search for custom form types owned by this project
        response = datazone_client.search(
            domainIdentifier=domain_id,
            searchScope="FORM_TYPE",
            managed=False,  # Only custom form types
        )

        deleted_forms = []
        for item in response.get("items", []):
            form_type = item.get("formTypeItem", {})
            form_name = form_type.get("name", "")
            owning_project = form_type.get("owningProjectId", "")

            # Delete form types owned by this project that start with SageMakerUnifiedStudioScheduleFormType
            if owning_project == project_id and form_name.startswith(
                "SageMakerUnifiedStudioScheduleFormType"
            ):

                try:
                    datazone_client.delete_form_type(
                        domainIdentifier=domain_id, formTypeIdentifier=form_name
                    )
                    deleted_forms.append(form_name)
                    print(f"Deleted form type: {form_name}")

                except Exception as e:
                    print(f"Warning: Failed to delete form type {form_name}: {str(e)}")

        return deleted_forms

    except Exception as e:
        # Don't fail the entire deletion if form type cleanup fails
        print(
            f"Warning: Error cleaning up custom form types for project {project_id}: {str(e)}"
        )
        return []


def delete_project_data_sources(domain_name, project_id, region):
    """Delete all data sources in a project."""
    try:
        domain_id = get_domain_id_by_name(domain_name, region)
        if not domain_id:
            return []

        datazone_client = _get_datazone_client(region)

        # List data sources in the project
        data_sources_response = datazone_client.list_data_sources(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        deleted_sources = []
        for data_source in data_sources_response.get("items", []):
            data_source_id = data_source["dataSourceId"]
            data_source_name = data_source.get("name", data_source_id)

            try:
                datazone_client.delete_data_source(
                    domainIdentifier=domain_id, identifier=data_source_id
                )
                deleted_sources.append(data_source_name)
                print(f"Deleted data source: {data_source_name}")
            except Exception as e:
                print(
                    f"Warning: Failed to delete data source {data_source_name}: {str(e)}"
                )

        return deleted_sources

    except Exception as e:
        print(
            f"Warning: Error deleting data sources for project {project_id}: {str(e)}"
        )
        return []


def delete_project_environments(domain_name, project_id, region):
    """Delete all environments in a project and wait for completion."""
    try:
        domain_id = get_domain_id_by_name(domain_name, region)
        if not domain_id:
            return []

        datazone_client = _get_datazone_client(region)

        # List environments in the project
        environments_response = datazone_client.list_environments(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        deleted_environments = []
        for environment in environments_response.get("items", []):
            env_id = environment["id"]
            env_name = environment.get("name", env_id)

            try:
                datazone_client.delete_environment(
                    domainIdentifier=domain_id, identifier=env_id
                )
                deleted_environments.append(env_name)
                print(f"Deleted environment: {env_name}")
            except Exception as e:
                print(f"Warning: Failed to delete environment {env_name}: {str(e)}")

        # Wait for environments to be deleted
        if deleted_environments:
            print("Waiting for environments to be deleted...")

            max_wait = 300  # 5 minutes
            start_time = time.time()

            while time.time() - start_time < max_wait:
                remaining_envs = datazone_client.list_environments(
                    domainIdentifier=domain_id, projectIdentifier=project_id
                ).get("items", [])

                if not remaining_envs:
                    print("All environments deleted successfully")
                    break

                print(
                    f"Waiting for {len(remaining_envs)} environments to finish deleting..."
                )
                sleep(10)
            else:
                print(
                    f"Warning: Some environments still exist after {max_wait} seconds"
                )

        return deleted_environments

    except Exception as e:
        print(
            f"Warning: Error deleting environments for project {project_id}: {str(e)}"
        )
        return []


def delete_project(domain_name, project_id, region):
    """Delete a DataZone project."""
    try:
        domain_id = get_domain_id_by_name(domain_name, region)
        if not domain_id:
            raise Exception(f"Domain '{domain_name}' not found")

        # First, delete all environments and wait for completion
        print("Deleting project environments...")
        deleted_environments = delete_project_environments(
            domain_name, project_id, region
        )
        if deleted_environments:
            print(f"Deleted environments: {', '.join(deleted_environments)}")

        # Delete data sources to stop metadata generation
        print("Deleting data sources...")
        deleted_sources = delete_project_data_sources(domain_name, project_id, region)
        if deleted_sources:
            print(f"Deleted data sources: {', '.join(deleted_sources)}")
            # Wait for data sources to be deleted

            print("Waiting for data sources to be deleted...")
            sleep(30)

        # Try to delete any custom form types owned by this project
        deleted_forms = delete_project_custom_form_types(
            domain_name, project_id, region
        )
        if deleted_forms:
            print(f"Deleted custom form types: {', '.join(deleted_forms)}")

        datazone_client = _get_datazone_client(region)

        # FIXME: This is a workaround for DataZone API bug where enabled form types
        # cannot be deleted programmatically, preventing project deletion.
        # Once AWS fixes the API to allow disabling/deleting enabled form types,
        # remove this force deletion approach and properly handle form type cleanup.
        try:
            # FIXME: Using skipDeletionCheck=True to bypass form type validation
            # This is necessary because enabled form types cannot be deleted via API
            datazone_client.delete_project(
                domainIdentifier=domain_id,
                identifier=project_id,
                skipDeletionCheck=True,
            )
            print(f"✅ Successfully deleted project {project_id} (forced deletion)")
            return True
        except Exception as e:
            if "MetaDataForms found" in str(e):
                print(
                    "Warning: Project deletion blocked by form types that cannot be deleted via API"
                )
                print("FIXME: This requires manual cleanup through DataZone console")
                # For now, we'll report this as a known limitation rather than failing
                raise Exception(
                    f"Project deletion blocked by undeletable form types: {str(e)}"
                )
            else:
                raise e

    except Exception as e:
        raise Exception(f"Error deleting project {project_id}: {str(e)}")


def get_project_status(domain_name, project_id, region):
    """Get the status of a DataZone project. Returns None if project doesn't exist."""
    try:
        domain_id = get_domain_id_by_name(domain_name, region)
        if not domain_id:
            return None

        datazone_client = _get_datazone_client(region)
        response = datazone_client.get_project(
            domainIdentifier=domain_id, identifier=project_id
        )

        return response.get("projectStatus")

    except datazone_client.exceptions.ResourceNotFoundException:
        return None
    except Exception as e:
        raise Exception(f"Error getting project status: {str(e)}")


def get_project_details(project_name, region, domain_name):
    """Get detailed project information from DataZone using names."""
    try:
        # Get domain ID by name
        domain_id = get_domain_id_by_name(domain_name, region)
        if not domain_id:
            return {
                "status": f'Error: Domain "{domain_name}" not found',
                "owners": "N/A",
                "projectId": "N/A",
            }

        # Get project ID by name
        project_id = get_project_id_by_name(project_name, domain_id, region)
        if not project_id:
            return {
                "status": f'Error: Project "{project_name}" not found in domain',
                "owners": "N/A",
                "projectId": "N/A",
            }

        # Get project details from DataZone
        datazone_client = _get_datazone_client(region)

        try:
            response = datazone_client.get_project(
                domainIdentifier=domain_id, identifier=project_id
            )

            project = response.get("project", {})

            return {
                "status": project.get("projectStatus", "UNKNOWN"),
                "owners": ", ".join(
                    [
                        member.get("memberDetails", {})
                        .get("user", {})
                        .get("userIdentifier", "Unknown")
                        for member in project.get("projectMembers", [])
                        if member.get("designation") == "PROJECT_OWNER"
                    ]
                )
                or "N/A",
                "projectId": project_id,
                "domainId": domain_id,
            }

        except Exception as e:
            return {
                "status": f"Error: {str(e)}",
                "owners": "N/A",
                "projectId": project_id,
                "domainId": domain_id,
            }

    except Exception as e:
        return {"status": f"Error: {str(e)}", "owners": "N/A", "projectId": "N/A"}


def get_project_connections(project_id, domain_id, region):
    """Get project connections from DataZone."""
    typer.echo(
        f"🔍 DEBUG: get_project_connections called for project {project_id}", err=True
    )
    try:
        datazone_client = _get_datazone_client(region)

        # DEBUG: Log the exact parameters being used for the ListConnections call
        import sys

        is_json_output = "--output" in sys.argv and "JSON" in sys.argv
        if not is_json_output:
            print(
                f"🔍 DEBUG datazone.get_project_connections: region={region}, domain_id={domain_id}, project_id={project_id}",
                file=sys.stderr,
            )

        # List connections for the project with pagination
        connections = {}
        next_token = None

        while True:
            list_params = {
                "domainIdentifier": domain_id,
                "projectIdentifier": project_id,
                "maxResults": 50,
            }
            if next_token:
                list_params["nextToken"] = next_token

            response = datazone_client.list_connections(**list_params)

            if not is_json_output:
                print(
                    f"🔍 DEBUG: Page returned {len(response.get('items', []))} connections",
                    file=sys.stderr,
                )

            for connection in response.get("items", []):
                connection_name = connection.get("name", "unknown")
                connection_id = connection.get("connectionId", "")

                typer.echo(f"🔍 DEBUG: Processing {connection_name}", err=True)

                # Get detailed connection information
                try:
                    detail_response = datazone_client.get_connection(
                        domainIdentifier=domain_id, identifier=connection_id
                    )

                    connection_type = detail_response.get("type", "UNKNOWN")

                    conn_info = {
                        "connectionId": connection_id,
                        "type": connection_type,
                        "description": detail_response.get("description", ""),
                        "environmentId": detail_response.get("environmentId"),
                    }

                    # Add type-specific properties
                    props = detail_response.get("props", {})
                    if connection_type == "S3":
                        s3_props = props.get("s3Properties", {})
                        conn_info["s3Uri"] = s3_props.get("s3Uri", "")
                    elif connection_type == "WORKFLOWS_MWAA":
                        mwaa_props = props.get("mwaaProperties", {})
                        env_name = mwaa_props.get("environmentName")

                        # If no environment name in properties, infer it from project structure
                        if not env_name:
                            env_name = f"DataZoneMWAAEnv-{domain_id}-{project_id}-dev"

                        conn_info["environmentName"] = env_name

                    connections[connection_name] = conn_info

                except Exception as e:
                    connections[connection_name] = {
                        "connectionId": connection_id,
                        "type": "UNKNOWN",
                        "error": str(e),
                    }

            # Check if there are more pages
            next_token = response.get("nextToken")
            if not next_token:
                break

        if not is_json_output:
            print(
                f"🔍 DEBUG: Retrieved {len(connections)} total connections",
                file=sys.stderr,
            )

        return connections

    except Exception as e:
        # Check if this is a permission error
        error_str = str(e)
        if any(
            perm_error in error_str.lower()
            for perm_error in [
                "accessdenied",
                "access denied",
                "unauthorized",
                "forbidden",
                "permission",
                "not authorized",
                "insufficient privileges",
            ]
        ):
            typer.echo(
                f"❌ AWS Permission Error getting project connections: {error_str}",
                err=True,
            )
            typer.echo(
                "Check if the role has DataZone permissions to list connections.",
                err=True,
            )
            return {}
        else:
            typer.echo(f"Error getting project connections: {str(e)}", err=True)
            return {}


def resolve_connection_details(connection_name, target_config, region, domain_name):
    """Resolve connection details for a target configuration."""
    project = target_config.get("project", {})
    project_name = project.get("name")

    if not project_name:
        return None

    # Get domain ID by name
    domain_id = get_domain_id_by_name(domain_name, region)
    if not domain_id:
        return None

    # Get project ID by name
    project_id = get_project_id_by_name(project_name, domain_id, region)
    if not project_id:
        return None

    # Get project connections
    connections = get_project_connections(project_id, domain_id, region)
    return connections.get(connection_name)


def get_user_id_by_username(username, domain_id, region):
    """Get user identifier by username or IAM role ARN using DataZone and Identity Center APIs."""
    try:
        datazone_client = _get_datazone_client(region)

        # Check if username is an IAM role ARN
        if username.startswith("arn:aws:iam::") and ":role/" in username:
            # Search for IAM role in DataZone user profiles
            try:
                response = datazone_client.search_user_profiles(
                    domainIdentifier=domain_id, userType="DATAZONE_IAM_USER"
                )

                for user_profile in response.get("items", []):
                    iam_details = user_profile.get("details", {}).get("iam", {})
                    if iam_details.get("arn") == username:
                        return user_profile.get("id")

                print(f"IAM role ARN '{username}' not found in DataZone user profiles")
                return None

            except Exception as e:
                print(f"Error searching for IAM role '{username}': {str(e)}")
                return None

        # Handle regular username lookup via Identity Center
        # Get Identity Center instance ARN from DataZone domain
        domain_response = datazone_client.get_domain(identifier=domain_id)

        # Extract Identity Center instance ARN from domain
        sso_domain_details = domain_response.get("singleSignOn", {})
        idc_instance_arn = sso_domain_details.get("idcInstanceArn")

        if not idc_instance_arn:
            print(f"No Identity Center instance ARN found for domain {domain_id}")
            return None

        # Use SSO Admin to get the Identity Store ID from the instance ARN
        sso_admin_client = boto3.client("sso-admin", region_name=region)
        instances_response = sso_admin_client.list_instances()

        identity_store_id = None
        for instance in instances_response.get("Instances", []):
            if instance.get("InstanceArn") == idc_instance_arn:
                identity_store_id = instance.get("IdentityStoreId")
                break

        if not identity_store_id:
            print(f"No Identity Store ID found for instance ARN {idc_instance_arn}")
            return None

        # Use Identity Center APIs to find user
        identitystore_client = boto3.client("identitystore", region_name=region)

        # Search for user by username
        response = identitystore_client.list_users(
            IdentityStoreId=identity_store_id,
            Filters=[{"AttributePath": "UserName", "AttributeValue": username}],
        )

        users = response.get("Users", [])
        if users:
            return users[0].get("UserId")

        return None

    except Exception as e:
        print(f"Error getting user ID for {username}: {str(e)}")
        return None


def resolve_usernames_to_ids(usernames, domain_id, region):
    """Resolve list of usernames to IDC user identifiers."""
    user_ids = []

    for username in usernames:
        user_id = get_user_id_by_username(username, domain_id, region)
        if user_id:
            user_ids.append(user_id)
        else:
            print(f"Warning: Could not resolve username '{username}' to user ID")

    return user_ids


def get_project_environments(project_id, domain_id, region):
    """Get all environments for a project."""
    try:
        datazone_client = _get_datazone_client(region)
        response = datazone_client.list_environments(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )
        return response.get("items", [])
    except Exception as e:
        print(f"Error getting project environments: {str(e)}")
        return []


def manage_project_memberships(
    project_id, domain_id, region, owners=None, contributors=None
):
    """Idempotently manage project memberships via DataZone API."""
    try:
        datazone_client = _get_datazone_client(region)

        # Get existing memberships
        response = datazone_client.list_project_memberships(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        existing_members = {}
        for member in response.get("members", []):
            member_details = member.get("memberDetails", {})
            if "user" in member_details:
                user_id = member_details["user"].get("userIdentifier")
                if user_id:
                    existing_members[user_id] = member.get("designation")

        typer.echo(f"🔍 Found {len(existing_members)} existing members")

        # Add owners
        if owners:
            owner_ids = resolve_usernames_to_ids(owners, domain_id, region)
            for i, owner_id in enumerate(owner_ids):
                if not owner_id:  # Skip if resolution failed
                    continue

                if owner_id not in existing_members:
                    try:
                        datazone_client.create_project_membership(
                            domainIdentifier=domain_id,
                            projectIdentifier=project_id,
                            member={"userIdentifier": owner_id},
                            designation="PROJECT_OWNER",
                        )
                        typer.echo(f"✅ Added owner: {owner_id}")
                    except Exception as e:
                        if "User is already in the project" in str(e):
                            typer.echo(f"✓ Owner already exists: {owner_id}")
                        else:
                            typer.echo(f"❌ Failed to add owner {owner_id}: {e}")
                            return False
                elif existing_members[owner_id] != "PROJECT_OWNER":
                    typer.echo(
                        f"⚠️ User {owner_id} exists with different role: {existing_members[owner_id]}"
                    )
                else:
                    typer.echo(f"✓ Owner already exists: {owner_id}")

        # Add contributors
        if contributors:
            contributor_ids = resolve_usernames_to_ids(contributors, domain_id, region)
            for contributor_id in contributor_ids:
                if not contributor_id:  # Skip if resolution failed
                    continue

                if contributor_id not in existing_members:
                    try:
                        datazone_client.create_project_membership(
                            domainIdentifier=domain_id,
                            projectIdentifier=project_id,
                            member={"userIdentifier": contributor_id},
                            designation="PROJECT_CONTRIBUTOR",
                        )
                        typer.echo(f"✅ Added contributor: {contributor_id}")
                    except Exception as e:
                        if "User is already in the project" in str(e):
                            typer.echo(
                                f"✓ Contributor already exists: {contributor_id}"
                            )
                        else:
                            typer.echo(
                                f"❌ Failed to add contributor {contributor_id}: {e}"
                            )
                            return False
                elif existing_members[contributor_id] != "PROJECT_CONTRIBUTOR":
                    typer.echo(
                        f"⚠️ User {contributor_id} exists with different role: {existing_members[contributor_id]}"
                    )
                else:
                    typer.echo(f"✓ Contributor already exists: {contributor_id}")

        return True

    except Exception as e:
        typer.echo(f"❌ Error managing project memberships: {str(e)}", err=True)
        return False


# Asset Access Functions for DataZone Catalog Integration


def search_asset_listing(
    domain_id: str, identifier: str, region: str
) -> Optional[Tuple[str, str]]:
    """Search for asset listing and return (asset_id, listing_id)."""
    try:
        datazone_client = _get_datazone_client(region)

        response = datazone_client.search_listings(
            domainIdentifier=domain_id, searchText=identifier
        )

        items = response.get("items", [])
        if not items:
            typer.echo(f"❌ No listings found for identifier: {identifier}")
            raise Exception(f"No listings found for identifier: {identifier}")

        item = items[0]["assetListing"]
        asset_id = item["entityId"]
        listing_id = item["listingId"]

        typer.echo(f"✅ Found asset: {asset_id}, listing: {listing_id}")
        return asset_id, listing_id

    except Exception as e:
        typer.echo(f"❌ Error searching for asset {identifier}: {e}")
        raise


def check_existing_subscription(
    domain_id: str, project_id: str, listing_id: str, region: str
) -> Optional[str]:
    """Check if subscription request already exists for the asset."""
    try:
        datazone_client = _get_datazone_client(region)

        # Check subscription requests
        response = datazone_client.list_subscription_requests(
            domainIdentifier=domain_id, owningProjectId=project_id
        )

        for request in response.get("items", []):
            if request.get("subscribedListings", [{}])[0].get("id") == listing_id:
                typer.echo(
                    f"✅ Found existing subscription request: {request['id']} (status: {request.get('status', 'UNKNOWN')})"
                )
                return request["id"]

        # Also check active subscriptions
        try:
            subs_response = datazone_client.list_subscriptions(
                domainIdentifier=domain_id, owningProjectId=project_id
            )

            for sub in subs_response.get("items", []):
                if sub.get("subscribedListing", {}).get("id") == listing_id:
                    typer.echo(
                        f"✅ Found existing active subscription: {sub['id']} (status: {sub.get('status', 'UNKNOWN')})"
                    )
                    return sub["id"]

        except Exception as e:
            typer.echo(f"⚠️ Could not check active subscriptions: {e}")

        return None

    except Exception as e:
        typer.echo(f"❌ Error checking existing subscriptions: {e}")
        raise


def create_subscription_request(
    domain_id: str, project_id: str, listing_id: str, reason: str, region: str
) -> Optional[str]:
    """Create subscription request for asset."""
    try:
        datazone_client = _get_datazone_client(region)

        response = datazone_client.create_subscription_request(
            domainIdentifier=domain_id,
            requestReason=reason,
            subscribedListings=[{"identifier": listing_id}],
            subscribedPrincipals=[{"project": {"identifier": project_id}}],
        )

        request_id = response["id"]
        typer.echo(f"✅ Created subscription request: {request_id}")
        return request_id

    except Exception as e:
        typer.echo(f"❌ Error creating subscription request: {e}")
        raise


def wait_for_subscription_approval(
    domain_id: str, request_id: str, region: str, timeout: int = 300
) -> bool:
    """Wait for subscription approval with timeout."""
    typer.echo(f"⏳ Waiting for subscription approval (timeout: {timeout}s)...")

    datazone_client = _get_datazone_client(region)
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = datazone_client.get_subscription_request_details(
                domainIdentifier=domain_id, identifier=request_id
            )

            status = response["status"]
            typer.echo(f"📊 Subscription request {request_id} status: {status}")

            if status in ["APPROVED", "ACCEPTED"]:
                typer.echo("✅ Subscription approved!")
                return True
            elif status in ["REJECTED", "ERROR"]:
                typer.echo(f"❌ Subscription failed with status: {status}")
                raise Exception(f"Subscription request failed with status: {status}")

            typer.echo("⏳ Waiting 30 seconds before next check...")
            time.sleep(30)

        except Exception as e:
            typer.echo(f"❌ Error checking subscription status: {e}")
            raise

    typer.echo("⏰ Timeout waiting for subscription approval")
    raise Exception(f"Timeout waiting for subscription approval after {timeout}s")


def check_subscription_grants(
    domain_id: str, subscription_id: str, region: str
) -> bool:
    """Check subscription grant status with retry logic."""
    try:
        datazone_client = _get_datazone_client(region)

        # Wait up to 60 seconds for grants to be created after subscription approval
        max_wait_time = 60
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            response = datazone_client.list_subscription_grants(
                domainIdentifier=domain_id, subscriptionId=subscription_id
            )

            grants = response.get("items", [])

            if not grants:
                # No grants yet - wait and retry
                remaining_time = max_wait_time - (time.time() - start_time)
                if remaining_time > 0:
                    typer.echo(
                        f"⏳ Waiting for grants to be created... ({remaining_time:.0f}s remaining)"
                    )
                    time.sleep(10)
                    continue
                else:
                    typer.echo(
                        "❌ No grants created within timeout period - this indicates an error"
                    )
                    raise Exception(
                        "No subscription grants created within timeout period"
                    )

            # Check grant status
            all_completed = True
            for grant in grants:
                status = grant["status"]
                grant_id = grant["id"]
                typer.echo(f"📊 Grant {grant_id} status: {status}")

                if status != "COMPLETED":
                    all_completed = False

            if all_completed:
                return True
            else:
                # Grants exist but not all completed - wait and retry
                remaining_time = max_wait_time - (time.time() - start_time)
                if remaining_time > 0:
                    typer.echo(
                        f"⏳ Waiting for grants to complete... ({remaining_time:.0f}s remaining)"
                    )
                    time.sleep(10)
                    continue
                else:
                    typer.echo("❌ Grants did not complete within timeout period")
                    raise Exception(
                        "Subscription grants did not complete within timeout period"
                    )

        return False

    except Exception as e:
        typer.echo(f"❌ Error checking subscription grants: {e}")
        raise


def process_asset_access(
    domain_id: str, project_id: str, identifier: str, reason: str, region: str
) -> bool:
    """Complete asset access workflow for a single asset."""
    typer.echo(f"\n🔍 Processing asset access for: {identifier}")

    # Step 1: Search for asset
    result = search_asset_listing(domain_id, identifier, region)
    asset_id, listing_id = result

    # Step 2: Check existing subscription
    existing_id = check_existing_subscription(domain_id, project_id, listing_id, region)

    # Step 3: Create subscription if needed
    if not existing_id:
        request_id = create_subscription_request(
            domain_id, project_id, listing_id, reason, region
        )

        # Step 4: Wait for approval
        wait_for_subscription_approval(domain_id, request_id, region)

        # Step 5: Find the actual subscription ID by listing
        subscription_id = find_subscription_by_listing(
            domain_id, project_id, listing_id, region
        )
        if not subscription_id:
            # Fallback to request ID
            subscription_id = get_subscription_id_from_request(
                domain_id, request_id, region
            )
    else:
        # Use existing subscription
        subscription_id = existing_id
        typer.echo("✅ Using existing subscription")

    # Step 6: Check grants
    check_subscription_grants(domain_id, subscription_id, region)

    typer.echo("✅ Asset access successfully configured!")
    return True


def get_subscription_id_from_request(
    domain_id: str, request_id: str, region: str
) -> str:
    """Get actual subscription ID from request ID after approval."""
    try:
        datazone_client = _get_datazone_client(region)

        # First try to get subscription ID from request details
        try:
            response = datazone_client.get_subscription_request_details(
                domainIdentifier=domain_id, identifier=request_id
            )

            subscription_id = response.get("subscriptionId")
            if subscription_id:
                typer.echo(f"📊 Subscription ID from request: {subscription_id}")
                return subscription_id
        except Exception as e:
            typer.echo(f"⚠️ Could not get request details: {e}")

        # If that fails, the request_id might actually be the subscription_id
        # This happens when DataZone creates the subscription immediately
        typer.echo(f"📊 Using request ID as subscription ID: {request_id}")
        return request_id

    except Exception as e:
        typer.echo(f"⚠️ Error getting subscription ID: {e}")
        raise


def find_subscription_by_listing(
    domain_id: str, project_id: str, listing_id: str, region: str
) -> Optional[str]:
    """Find subscription ID by matching listing ID."""
    try:
        datazone_client = _get_datazone_client(region)

        response = datazone_client.list_subscriptions(
            domainIdentifier=domain_id, owningProjectId=project_id
        )

        for sub in response.get("items", []):
            if sub.get("subscribedListing", {}).get("id") == listing_id:
                if sub.get("status") == "APPROVED":
                    return sub["id"]

        return None

    except Exception as e:
        typer.echo(f"⚠️ Error finding subscription by listing: {e}")
        raise


def process_catalog_assets(
    domain_id: str, project_id: str, assets: List[Dict], region: str
) -> bool:
    """Process all catalog assets for a deployment target."""
    if not assets:
        typer.echo("📋 No catalog assets to process")
        return True

    typer.echo(f"\n📦 Processing {len(assets)} catalog assets...")

    success_count = 0
    failed_assets = []

    for i, asset in enumerate(assets, 1):
        typer.echo(f"\n--- Asset {i}/{len(assets)} ---")

        # Extract asset configuration
        selector = asset.get("selector", {})
        reason = asset.get("requestReason", "Required for pipeline deployment")

        # Handle asset ID vs search
        if "assetId" in selector:
            typer.echo("⚠️ Direct assetId not yet supported, use search instead")
            continue

        search = selector.get("search", {})
        if not search:
            typer.echo("❌ No search configuration found in asset selector")
            failed_assets.append("No search configuration")
            continue

        asset_type = search.get("assetType")
        identifier = search.get("identifier")

        if not identifier:
            typer.echo("❌ No identifier found in asset search configuration")
            failed_assets.append("No identifier")
            continue

        # Skip non-Glue assets as specified in requirements
        if asset_type and asset_type != "GlueTable":
            typer.echo(f"⏭️ Skipping asset type {asset_type} (only GlueTable supported)")
            continue

        # Process asset access
        try:
            if process_asset_access(domain_id, project_id, identifier, reason, region):
                success_count += 1
            else:
                failed_assets.append(identifier)
        except Exception as e:
            typer.echo(f"❌ Failed to process asset: {identifier} - {e}")
            failed_assets.append(f"{identifier}: {e}")

    typer.echo(
        f"\n✅ Processed {success_count}/{len(assets)} catalog assets successfully"
    )

    if failed_assets:
        typer.echo(f"❌ Failed assets: {', '.join(failed_assets)}")
        raise Exception(
            f"Failed to process {len(failed_assets)} catalog assets: {', '.join(failed_assets)}"
        )

    return True


# Shared workflow helper functions
def is_connection_serverless_airflow(
    connection_name: str, domain_id: str, project_id: str, region: str
) -> bool:
    """
    Check if a DataZone connection is serverless Airflow.

    This handles the DataZone bug where both serverless and MWAA
    connections have type WORKFLOWS_MWAA. We distinguish by checking
    if physicalEndpoints contains a MWAA ARN.

    Args:
        connection_name: Connection name to check
        domain_id: DataZone domain ID
        project_id: DataZone project ID
        region: AWS region

    Returns:
        True if connection is serverless Airflow, False otherwise
    """
    try:
        client = _get_datazone_client(region)
        response = client.list_connections(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        for conn in response.get("items", []):
            if conn["name"] == connection_name:
                # Check if it's a workflow connection
                if conn["type"] == "WORKFLOWS_MWAA":
                    # CRITICAL: Check physicalEndpoints for MWAA ARN
                    # Serverless: type=WORKFLOWS_MWAA WITHOUT MWAA ARN
                    # MWAA: type=WORKFLOWS_MWAA WITH MWAA ARN
                    physical_endpoints = conn.get("physicalEndpoints", [])
                    has_mwaa_arn = any(
                        "glueConnection" in ep
                        and "arn:aws:airflow" in str(ep.get("glueConnection", ""))
                        for ep in physical_endpoints
                    )
                    # If no MWAA ARN, it's serverless
                    return not has_mwaa_arn

        return False

    except Exception:
        return False


def target_uses_serverless_airflow(manifest, target_config) -> bool:
    """
    Check if a target uses serverless Airflow workflows.

    This is the tested logic from monitor.py that properly detects
    serverless Airflow by querying DataZone at runtime.

    Args:
        manifest: Application manifest
        target_config: Target configuration

    Returns:
        True if target uses serverless Airflow, False otherwise
    """
    if not hasattr(manifest.content, "workflows") or not manifest.content.workflows:
        return False

    region = target_config.domain.region
    project_name = target_config.project.name

    try:
        # Resolve domain and project IDs
        domain_id, _ = resolve_domain_id(
            target_config.domain.name,
            (
                target_config.domain.tags
                if hasattr(target_config.domain, "tags")
                else None
            ),
            region,
        )

        if not domain_id:
            return False

        project_id = get_project_id_by_name(project_name, domain_id, region)
        if not project_id:
            return False

        # Check each workflow's connection
        for workflow in manifest.content.workflows:
            conn_name = workflow.get("connectionName", "")
            if conn_name:
                # Resolve project. prefix to default.
                if conn_name.startswith("project."):
                    conn_name = conn_name.replace("project.", "default.", 1)

                if is_connection_serverless_airflow(
                    conn_name, domain_id, project_id, region
                ):
                    return True

        return False

    except Exception:
        return False
