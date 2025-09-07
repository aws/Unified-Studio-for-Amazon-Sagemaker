"""
CloudFormation utility functions for SMUS CI/CD CLI.
"""

import boto3
import typer
import time
from pathlib import Path
from . import datazone


def create_project_via_cloudformation(
    project_name,
    profile_name,
    domain_name,
    region,
    pipeline_name,
    target_name,
    target_stage=None,
    user_parameters=None,
    owners=None,
    contributors=None,
):
    """Create DataZone project with memberships using dynamically generated CloudFormation template."""
    try:
        print("🔍 DEBUG: Creating project via CloudFormation")
        print(f"🔍 DEBUG: project_name={project_name}")
        print(f"🔍 DEBUG: profile_name={profile_name}")
        print(f"🔍 DEBUG: user_parameters={user_parameters}")

        cf_client = boto3.client("cloudformation", region_name=region)
        datazone_client = boto3.client("datazone", region_name=region)

        # Convert userParameters to CloudFormation format
        user_parameters_cf = []
        if user_parameters:
            print(
                f"🔍 DEBUG: Converting {len(user_parameters)} user parameters to CF format"
            )
            for env_config in user_parameters:
                print(f"🔍 DEBUG: Processing env_config: {env_config}")
                env_dict = {
                    "EnvironmentConfigurationName": env_config.EnvironmentConfigurationName,
                    "EnvironmentParameters": [],
                }
                for param in env_config.parameters:
                    env_dict["EnvironmentParameters"].append(
                        {"Name": param.name, "Value": param.value}
                    )
                user_parameters_cf.append(env_dict)
                print(f"🔍 DEBUG: Added CF env_dict: {env_dict}")
        else:
            print("🔍 DEBUG: No user_parameters provided")

        print(f"🔍 DEBUG: Final user_parameters_cf: {user_parameters_cf}")

        # Look up domain ID from domain name
        try:
            domains_response = datazone_client.list_domains()
            domain_id = None
            for domain in domains_response.get("items", []):
                if domain["name"] == domain_name:
                    domain_id = domain["id"]
                    break

            if not domain_id:
                typer.echo(f"Error: Domain '{domain_name}' not found", err=True)
                return False

        except Exception as e:
            typer.echo(f"Error finding domain by name {domain_name}: {e}", err=True)
            return False

        # Look up project profile ID from profile name
        try:
            profiles_response = datazone_client.list_project_profiles(
                domainIdentifier=domain_id
            )
            profile_id = None
            for profile in profiles_response.get("items", []):
                if profile["name"] == profile_name:
                    profile_id = profile["id"]
                    break

            if not profile_id:
                typer.echo(
                    f"Error: Project profile '{profile_name}' not found", err=True
                )
                return False

        except Exception as e:
            typer.echo(
                f"Error finding project profile by name {profile_name}: {e}", err=True
            )
            return False

        # Generate stack name: SMUS-{pipeline}-{target}-{project}-{template}
        clean_pipeline = pipeline_name.replace("_", "-").replace(" ", "-").lower()
        clean_target = target_name.replace("_", "-").replace(" ", "-").lower()
        clean_project = project_name.replace("_", "-").replace(" ", "-").lower()
        stack_name = f"SMUS-{clean_pipeline}-{clean_target}-{clean_project}-project"

        # Prepare stack tags
        tags = [
            {"Key": "PipelineName", "Value": pipeline_name},
            {"Key": "TargetName", "Value": target_name},
            {"Key": "CreatedBy", "Value": "SMUS-CLI"},
        ]
        if target_stage:
            tags.append({"Key": "TargetStage", "Value": target_stage})

        # Resolve usernames to DataZone user IDs before template generation
        owner_ids = []
        contributor_ids = []
        if owners or contributors:
            if owners:
                owner_ids = datazone.resolve_usernames_to_ids(owners, domain_id, region)
                typer.echo(f"Resolved {len(owner_ids)} owners: {owners} -> {owner_ids}")
            if contributors:
                contributor_ids = datazone.resolve_usernames_to_ids(
                    contributors, domain_id, region
                )
                typer.echo(
                    f"Resolved {len(contributor_ids)} contributors: {contributors} -> {contributor_ids}"
                )

        # Generate CloudFormation template dynamically
        template_dict = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Create a single DataZone Project with memberships",
            "Parameters": {
                "DomainIdentifier": {
                    "Type": "String",
                    "Description": "DataZone Domain ID",
                },
                "ProjectProfileId": {
                    "Type": "String",
                    "Description": "Project Profile ID to use for the project",
                },
                "ProjectName": {
                    "Type": "String",
                    "Description": "Name for the project",
                    "MinLength": 1,
                    "MaxLength": 64,
                },
                "ProjectDescription": {
                    "Type": "String",
                    "Default": "DataZone project for CI/CD pipeline",
                    "Description": "Description for the project",
                },
            },
            "Resources": {
                "DataZoneProject": {
                    "Type": "AWS::DataZone::Project",
                    "Properties": {
                        "DomainIdentifier": {"Ref": "DomainIdentifier"},
                        "Name": {"Ref": "ProjectName"},
                        "Description": {"Ref": "ProjectDescription"},
                        "ProjectProfileId": {"Ref": "ProjectProfileId"},
                    },
                }
            },
            "Outputs": {
                "ProjectId": {
                    "Description": "DataZone Project ID",
                    "Value": {"Fn::GetAtt": ["DataZoneProject", "Id"]},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-ProjectId"}},
                },
                "ProjectName": {
                    "Description": "DataZone Project Name",
                    "Value": {"Ref": "ProjectName"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-ProjectName"}},
                },
            },
        }

        # Add UserParameters if they exist
        if user_parameters_cf:
            template_dict["Resources"]["DataZoneProject"]["Properties"][
                "UserParameters"
            ] = user_parameters_cf

        # Add project memberships if they exist
        membership_counter = 1
        if owner_ids:
            for owner_id in owner_ids:
                resource_name = f"OwnerMembership{membership_counter}"
                template_dict["Resources"][resource_name] = {
                    "Type": "AWS::DataZone::ProjectMembership",
                    "Properties": {
                        "DomainIdentifier": {"Ref": "DomainIdentifier"},
                        "ProjectIdentifier": {"Fn::GetAtt": ["DataZoneProject", "Id"]},
                        "Member": {"UserIdentifier": owner_id},
                        "Designation": "PROJECT_OWNER",
                    },
                }
                membership_counter += 1

        if contributor_ids:
            for contributor_id in contributor_ids:
                resource_name = f"ContributorMembership{membership_counter}"
                template_dict["Resources"][resource_name] = {
                    "Type": "AWS::DataZone::ProjectMembership",
                    "Properties": {
                        "DomainIdentifier": {"Ref": "DomainIdentifier"},
                        "ProjectIdentifier": {"Fn::GetAtt": ["DataZoneProject", "Id"]},
                        "Member": {"UserIdentifier": contributor_id},
                        "Designation": "PROJECT_CONTRIBUTOR",
                    },
                }
                membership_counter += 1

        import json

        template_body = json.dumps(template_dict)

        # Parameters for the stack
        parameters = [
            {"ParameterKey": "DomainIdentifier", "ParameterValue": domain_id},
            {"ParameterKey": "ProjectProfileId", "ParameterValue": profile_id},
            {"ParameterKey": "ProjectName", "ParameterValue": project_name},
            {
                "ParameterKey": "ProjectDescription",
                "ParameterValue": f"Auto-created project for {project_name} in {pipeline_name} pipeline",
            },
        ]

        typer.echo(f"Creating CloudFormation stack: {stack_name}")
        typer.echo(f"Pipeline: {pipeline_name}")
        typer.echo(f"Project: {project_name}")
        typer.echo(f"Profile: {profile_name}")

        # Create the stack
        try:
            response = cf_client.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=parameters,
                Capabilities=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
                Tags=tags,
            )

            stack_id = response["StackId"]
            typer.echo(f"Stack creation initiated: {stack_id}")

        except cf_client.exceptions.AlreadyExistsException:
            # Stack already exists - check if project exists in DataZone
            typer.echo(f"CloudFormation stack {stack_name} already exists")

            # Check if the project actually exists in DataZone
            domain_id = datazone.get_domain_id_by_name(domain_name, region)
            if domain_id:
                project_id = datazone.get_project_id_by_name(
                    project_name, domain_id, region
                )
                if project_id:
                    typer.echo(f"✅ Project {project_name} already exists and is ready")

                    # Check and create missing environments from user_parameters
                    if user_parameters:
                        env_success = _create_missing_environments_via_cloudformation(
                            project_name,
                            domain_name,
                            region,
                            pipeline_name,
                            target_name,
                            user_parameters,
                            domain_id,
                            project_id,
                        )
                        if not env_success:
                            typer.echo("❌ Failed to create one or more environments")
                            return False

                    return True

            # Stack exists but project doesn't - this is an error state
            typer.echo(
                f"❌ Stack exists but project {project_name} not found in DataZone"
            )
            return False

        # Wait for stack creation to complete
        typer.echo("Waiting for stack creation to complete...")
        waiter = cf_client.get_waiter("stack_create_complete")

        try:
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={"Delay": 30, "MaxAttempts": 60},  # 30 minutes max
            )
            typer.echo(f"✅ Stack {stack_name} created successfully")

            # Wait for project deployment to complete using DataZone API
            typer.echo("Waiting for project deployment to complete...")
            domain_id = datazone.get_domain_id_by_name(domain_name, region)
            if domain_id:
                project_id = datazone.get_project_id_by_name(
                    project_name, domain_id, region
                )
                if project_id:
                    return wait_for_project_deployment(
                        project_name, project_id, domain_id, region
                    )

            return True

        except Exception as e:
            typer.echo(f"❌ Stack creation failed: {str(e)}", err=True)

            # Get stack events for debugging
            try:
                events = cf_client.describe_stack_events(StackName=stack_name)
                typer.echo("Recent stack events:")
                for event in events["StackEvents"][:5]:
                    status = event.get("ResourceStatus", "N/A")
                    reason = event.get("ResourceStatusReason", "N/A")
                    typer.echo(
                        f"  - {event.get('LogicalResourceId')}: {status} - {reason}"
                    )
            except Exception:
                pass

            return False

    except Exception as e:
        typer.echo(f"Error creating project via CloudFormation: {str(e)}", err=True)
        return False


def wait_for_project_deployment(project_name, project_id, domain_id, region):
    """Wait for project deployment to complete using DataZone API."""
    try:
        datazone_client = boto3.client("datazone", region_name=region)
        max_attempts = 120  # 10 minutes

        for attempt in range(max_attempts):
            try:
                project_response = datazone_client.get_project(
                    domainIdentifier=domain_id, identifier=project_id
                )

                status = project_response.get("projectStatus")
                deployment_status = project_response.get("overallDeploymentStatus")

                typer.echo(
                    f"Project status: {status}, Deployment status: {deployment_status} (attempt {attempt + 1}/{max_attempts})"
                )

                if status == "ACTIVE" and deployment_status != "IN_PROGRESS":
                    typer.echo(f"✅ Project {project_name} is fully deployed and ready")
                    return True
                elif status in ["FAILED", "DELETED"]:
                    typer.echo(
                        f"❌ Project creation failed with status: {status}", err=True
                    )
                    return False

                time.sleep(5)  # Wait 5 seconds between checks

            except Exception as e:
                typer.echo(f"Error checking project status: {str(e)}")
                time.sleep(5)

        typer.echo("⚠️ Timeout waiting for project deployment to complete", err=True)
        return False

    except Exception as e:
        typer.echo(f"Error waiting for project deployment: {str(e)}", err=True)
        return False


def delete_project_stack(
    project_name, domain_name, region, pipeline_name, target_name, output="TEXT"
):
    """Delete CloudFormation stack for a project."""
    try:
        cf_client = boto3.client("cloudformation", region_name=region)

        # Generate stack name using same logic as creation
        clean_pipeline = pipeline_name.replace("_", "-").replace(" ", "-").lower()
        clean_target = target_name.replace("_", "-").replace(" ", "-").lower()
        clean_project = project_name.replace("_", "-").replace(" ", "-").lower()
        stack_name = f"SMUS-{clean_pipeline}-{clean_target}-{clean_project}-project"

        try:
            # Check if stack exists
            cf_client.describe_stacks(StackName=stack_name)

            # Delete the stack
            if output.upper() != "JSON":
                typer.echo(f"Deleting CloudFormation stack: {stack_name}")
            cf_client.delete_stack(StackName=stack_name)

            # Wait for deletion to complete
            if output.upper() != "JSON":
                typer.echo("Waiting for stack deletion to complete...")
            waiter = cf_client.get_waiter("stack_delete_complete")
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={"Delay": 30, "MaxAttempts": 60},  # 30 minutes max
            )
            if output.upper() != "JSON":
                typer.echo(f"✅ Stack {stack_name} deleted successfully")
            return True

        except cf_client.exceptions.ClientError as e:
            if "does not exist" in str(e):
                if output.upper() != "JSON":
                    typer.echo(f"⚠️ Stack {stack_name} not found - skipping")
                return True
            else:
                raise e

    except Exception as e:
        typer.echo(f"❌ Error deleting CloudFormation stack: {str(e)}", err=True)
        return False


def update_project_stack_tags(
    pipeline_name, target_name, project_name, region, target_stage=None
):
    """Update existing project stack with tags."""
    try:
        cf_client = boto3.client("cloudformation", region_name=region)

        # Generate stack name
        clean_pipeline = pipeline_name.replace("_", "-").replace(" ", "-").lower()
        clean_target = target_name.replace("_", "-").replace(" ", "-").lower()
        clean_project = project_name.replace("_", "-").replace(" ", "-").lower()
        stack_name = f"SMUS-{clean_pipeline}-{clean_target}-{clean_project}-project"

        # Prepare stack tags
        tags = [
            {"Key": "PipelineName", "Value": pipeline_name},
            {"Key": "TargetName", "Value": target_name},
            {"Key": "CreatedBy", "Value": "SMUS-CLI"},
        ]
        if target_stage:
            tags.append({"Key": "TargetStage", "Value": target_stage})

        # Check if stack exists
        try:
            response = cf_client.describe_stacks(StackName=stack_name)
            stack_status = response["Stacks"][0]["StackStatus"]

            if stack_status in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
                # Read the CloudFormation template
                template_path = (
                    Path(__file__).parent.parent
                    / "cloudformation"
                    / "single-project.yaml"
                )
                with open(template_path, "r") as f:
                    template_body = f.read()

                # Get current parameters
                current_stack = response["Stacks"][0]
                parameters = [
                    {
                        "ParameterKey": param["ParameterKey"],
                        "ParameterValue": param["ParameterValue"],
                    }
                    for param in current_stack["Parameters"]
                ]

                # Update stack with tags
                typer.echo(f"Updating project stack tags: {stack_name}")
                cf_client.update_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Capabilities=["CAPABILITY_IAM"],
                    Tags=tags,
                )

                # Wait for update to complete
                waiter = cf_client.get_waiter("stack_update_complete")
                waiter.wait(
                    StackName=stack_name, WaiterConfig={"MaxAttempts": 60, "Delay": 5}
                )

                typer.echo(f"✅ Project stack {stack_name} updated with tags")
                return True
            else:
                typer.echo(
                    f"⚠️ Project stack {stack_name} is in state {stack_status}, skipping update"
                )
                return False

        except cf_client.exceptions.ClientError as e:
            if "does not exist" in str(e):
                typer.echo(f"⚠️ Project stack {stack_name} does not exist")
                return False
            else:
                raise e

    except Exception as e:
        if "No updates are to be performed" in str(e):
            typer.echo(f"✅ Project stack {stack_name} tags are already up to date")
            return True
        else:
            typer.echo(f"❌ Error updating project stack tags: {str(e)}", err=True)
            return False


def _create_missing_environments_via_cloudformation(
    project_name,
    domain_name,
    region,
    pipeline_name,
    target_name,
    user_parameters,
    domain_id,
    project_id,
):
    """Create missing environments using CloudFormation stacks."""
    if not user_parameters:
        return True

    typer.echo("🔍 Checking for missing environments...")

    # Get existing environments for the project
    existing_envs = datazone.get_project_environments(project_id, domain_id, region)
    existing_env_names = {env.get("name", "") for env in existing_envs}

    all_success = True

    # Check each environment from user_parameters
    for env_param in user_parameters:
        # Handle EnvironmentUserParameters object
        if hasattr(env_param, "EnvironmentConfigurationName"):
            env_name = env_param.EnvironmentConfigurationName
            env_parameters = (
                env_param.parameters if hasattr(env_param, "parameters") else []
            )
        else:
            # Fallback for dict format
            env_name = env_param.get("EnvironmentConfigurationName", "")
            env_parameters = env_param.get("EnvironmentParameters", [])

        if not env_name:
            continue

        if env_name in existing_env_names:
            typer.echo(f"✅ Environment '{env_name}' already exists, skipping")
            continue

        typer.echo(f"🔧 Creating missing environment: {env_name}")
        try:
            # Create environment using CloudFormation stack
            success = _create_environment_stack(
                project_name,
                env_name,
                domain_name,
                region,
                pipeline_name,
                target_name,
                domain_id,
                project_id,
                env_parameters,
            )
            if success:
                typer.echo(f"✅ Environment '{env_name}' created successfully")
                # Check if this is a workflow environment and validate MWAA
                if "workflow" in env_name.lower() or "mwaa" in env_name.lower():
                    _validate_mwaa_environment(project_id, domain_id, region)
            else:
                typer.echo(f"❌ Failed to create environment '{env_name}'")
                all_success = False
        except Exception as e:
            typer.echo(f"❌ Error creating environment '{env_name}': {str(e)}")
            all_success = False

    return all_success


def _get_environment_configuration_id(
    domain_id: str, project_id: str, env_name: str, region: str
) -> str:
    """Get environment configuration ID from project profile."""
    try:
        import boto3

        datazone_client = boto3.client("datazone", region_name=region)

        # Get project details to find project profile
        project_details = datazone_client.get_project(
            domainIdentifier=domain_id, identifier=project_id
        )

        project_profile_id = project_details.get("projectProfileId")
        if not project_profile_id:
            typer.echo("🔍 DEBUG: No project profile found")
            return None

        typer.echo(f"🔍 DEBUG: Project Profile ID: {project_profile_id}")

        # Get project profile details
        profile_details = datazone_client.get_project_profile(
            domainIdentifier=domain_id, identifier=project_profile_id
        )

        # Find environment configuration that matches target specification
        env_configs = profile_details.get("environmentConfigurations", [])
        typer.echo(f"🔍 DEBUG: Found {len(env_configs)} environment configurations")

        for config in env_configs:
            config_name = config.get("name")
            config_id = config.get("id")
            typer.echo(f"🔍 DEBUG: - {config_name} (ID: {config_id})")
            if config_name == env_name:
                typer.echo(f"🔍 DEBUG: Found matching configuration: {config_id}")
                return config_id

        typer.echo(f"🔍 DEBUG: Environment configuration '{env_name}' not found")
        return None

    except Exception as e:
        typer.echo(f"🔍 DEBUG: Error getting environment configuration: {e}")
        return None


def _validate_mwaa_environment(project_id: str, domain_id: str, region: str) -> None:
    """Validate MWAA environment is available."""
    try:
        import boto3
        import time

        # Wait a bit for environment to be ready
        time.sleep(5)

        datazone_client = boto3.client("datazone", region_name=region)

        # Get project connections to find MWAA connection
        connections_response = datazone_client.list_data_sources(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )

        mwaa_connection = None
        for conn in connections_response.get("items", []):
            if "mwaa" in conn.get("type", "").lower():
                mwaa_connection = conn
                break

        if mwaa_connection:
            typer.echo("✅ MWAA environment is available")
        else:
            typer.echo("⚠️  MWAA environment connection not found")

    except Exception as e:
        typer.echo(f"🔍 DEBUG: Error validating MWAA: {e}")


def _create_environment_stack(
    project_name,
    env_name,
    domain_name,
    region,
    pipeline_name,
    target_name,
    domain_id,
    project_id,
    env_parameters,
):
    """Create a DataZone environment directly using API (not CloudFormation)."""
    typer.echo(f"🔍 DEBUG: Starting environment creation for '{env_name}'")

    try:
        import boto3

        datazone_client = boto3.client("datazone", region_name=region)
        typer.echo(f"🔍 DEBUG: DataZone client created for region {region}")

        # Generate environment name
        safe_env_name = env_name.replace(" ", "-").replace("_", "-").lower()
        environment_name = f"{target_name}-{safe_env_name}-env"
        typer.echo(f"🔍 DEBUG: Generated environment name: {environment_name}")

        # Check if environment already exists
        typer.echo(f"🔍 DEBUG: Checking if environment already exists...")
        try:
            environments_response = datazone_client.list_environments(
                domainIdentifier=domain_id, projectIdentifier=project_id
            )
            typer.echo(
                f"🔍 DEBUG: Found {len(environments_response.get('items', []))} existing environments"
            )

            for env in environments_response.get("items", []):
                existing_name = env.get("name")
                typer.echo(f"🔍 DEBUG: Checking existing environment: {existing_name}")
                if existing_name == environment_name:
                    typer.echo(
                        f"✅ Environment '{environment_name}' already exists, skipping creation"
                    )
                    return True

        except Exception as list_error:
            typer.echo(f"🔍 DEBUG: Could not check existing environments: {list_error}")

        typer.echo(f"🔍 DEBUG: Environment doesn't exist, proceeding with creation")

        # Get the correct environment configuration ID
        typer.echo(f"🔍 DEBUG: Getting environment configuration ID...")
        config_id = _get_environment_configuration_id(
            domain_id, project_id, env_name, region
        )
        if not config_id:
            typer.echo(f"❌ Environment configuration '{env_name}' not found")
            return False

        typer.echo(
            f"🔧 Creating environment directly via DataZone API: {environment_name}"
        )
        typer.echo(f"🔍 DEBUG: Using configuration ID: {config_id}")

        # Create environment directly using DataZone API
        typer.echo(f"🔍 DEBUG: Calling create_environment API...")
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
        typer.echo(f"🔍 DEBUG: Environment creation completed successfully")

        return True

    except Exception as e:
        typer.echo(f"❌ Error creating environment via API: {e}")
        typer.echo(f"🔍 DEBUG: Exception type: {type(e).__name__}")
        return False
