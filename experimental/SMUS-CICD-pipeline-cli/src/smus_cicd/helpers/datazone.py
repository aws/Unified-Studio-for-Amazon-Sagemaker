import time
from time import sleep

"""
DataZone integration functions for SMUS CI/CD CLI.
"""

import boto3
import typer


def get_domain_id_by_name(domain_name, region):
    """Get DataZone domain ID by searching domains by name."""
    try:
        datazone_client = boto3.client("datazone", region_name=region)

        # List all domains and find by name
        response = datazone_client.list_domains()

        for domain in response.get("items", []):
            if domain.get("name") == domain_name:
                return domain.get("id")

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
            typer.echo(f"❌ AWS Permission Error: {error_str}", err=True)
            typer.echo(
                "Check if the role has DataZone permissions to find domains.", err=True
            )
        else:
            typer.echo(
                f"Error finding domain by name {domain_name}: {str(e)}", err=True
            )
        return None


def get_project_id_by_name(project_name, domain_id, region):
    """Get DataZone project ID by searching projects by name."""
    try:
        datazone_client = boto3.client("datazone", region_name=region)

        # List all projects in the domain and find by name
        response = datazone_client.list_projects(domainIdentifier=domain_id)

        for project in response.get("items", []):
            if project.get("name") == project_name:
                return project.get("id")

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
            typer.echo(f"❌ AWS Permission Error: {error_str}", err=True)
            typer.echo(
                "Check if the role has DataZone permissions to list projects.", err=True
            )
        else:
            typer.echo(
                f"Error finding project by name {project_name}: {str(e)}", err=True
            )
        return None


def create_environment_and_wait(domain_id, project_id, env_name, target_name, region):
    """Create DataZone environment and wait for it to be ACTIVE."""
    try:
        datazone_client = boto3.client("datazone", region_name=region)

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

        datazone_client = boto3.client("datazone", region_name=region)

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

        datazone_client = boto3.client("datazone", region_name=region)

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

        datazone_client = boto3.client("datazone", region_name=region)

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

        datazone_client = boto3.client("datazone", region_name=region)

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

        datazone_client = boto3.client("datazone", region_name=region)

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

        datazone_client = boto3.client("datazone", region_name=region)
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
        datazone_client = boto3.client("datazone", region_name=region)

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
    try:
        datazone_client = boto3.client("datazone", region_name=region)

        # DEBUG: Log the exact parameters being used for the ListConnections call
        import sys

        is_json_output = "--output" in sys.argv and "JSON" in sys.argv
        if not is_json_output:
            print(
                f"🔍 DEBUG datazone.get_project_connections: region={region}, domain_id={domain_id}, project_id={project_id}",
                file=sys.stderr,
            )

        # List connections for the project
        response = datazone_client.list_connections(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        connections = {}
        for connection in response.get("items", []):
            connection_name = connection.get("name", "unknown")
            connection_id = connection.get("connectionId", "")

            # Get detailed connection information
            try:
                detail_response = datazone_client.get_connection(
                    domainIdentifier=domain_id, identifier=connection_id
                )

                connection_detail = detail_response.get("connection", {})
                connection_type = connection_detail.get("type", "UNKNOWN")

                conn_info = {
                    "connectionId": connection_id,
                    "type": connection_type,
                    "description": connection_detail.get("description", ""),
                    "status": connection_detail.get("status", "UNKNOWN"),
                }

                # Add type-specific properties
                props = connection_detail.get("props", {})
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
        datazone_client = boto3.client("datazone", region_name=region)

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
        datazone_client = boto3.client("datazone", region_name=region)
        response = datazone_client.list_environments(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )
        return response.get("items", [])
    except Exception as e:
        print(f"Error getting project environments: {str(e)}")
        return []
