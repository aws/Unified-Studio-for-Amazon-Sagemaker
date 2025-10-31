"""
CloudFormation utility functions for SMUS CI/CD CLI.
"""

import json
import time

import boto3
import typer

from . import datazone
from .logger import get_logger


def get_project_id_from_stack(stack_name, region):
    """Get DataZone project ID from CloudFormation stack outputs."""
    try:
        cf_client = boto3.client("cloudformation", region_name=region)
        response = cf_client.describe_stacks(StackName=stack_name)

        if not response.get("Stacks"):
            return None

        stack = response["Stacks"][0]
        outputs = stack.get("Outputs", [])

        for output in outputs:
            if output.get("OutputKey") == "ProjectId":
                return output.get("OutputValue")

        return None
    except Exception as e:
        logger = get_logger("cloudformation")
        logger.debug(f"Failed to get project ID from stack {stack_name}: {e}")
        return None


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
    environments=None,
    role_arn=None,
):
    """Create DataZone project using CloudFormation template (without memberships)."""
    logger = get_logger("cloudformation")

    try:
        logger.debug("Creating project via CloudFormation")
        logger.debug(f"project_name={project_name}")
        logger.debug(f"profile_name={profile_name}")
        logger.debug(f"user_parameters={user_parameters}")

        cf_client = boto3.client("cloudformation", region_name=region)
        datazone_client = boto3.client("datazone", region_name=region)

        # Convert userParameters to CloudFormation format
        user_parameters_cf = []
        if user_parameters:
            logger.debug(
                f"Converting {len(user_parameters)} user parameters to CF format"
            )
            for env_config in user_parameters:
                logger.debug(f"Processing env_config: {env_config}")
                env_dict = {
                    "EnvironmentConfigurationName": env_config.EnvironmentConfigurationName,
                    "EnvironmentParameters": [],
                }
                for param in env_config.parameters:
                    env_dict["EnvironmentParameters"].append(
                        {"Name": param.name, "Value": param.value}
                    )
                user_parameters_cf.append(env_dict)
                logger.debug(f"Added CF env_dict: {env_dict}")
        else:
            logger.debug("No user_parameters provided")

        logger.debug(f"Final user_parameters_cf: {user_parameters_cf}")

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
                raise Exception(f"Domain '{domain_name}' not found")

        except Exception as e:
            typer.echo(f"Error finding domain by name {domain_name}: {e}", err=True)
            raise Exception(f"Failed to find domain {domain_name}: {e}")

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
                raise Exception(f"Project profile '{profile_name}' not found")

        except Exception as e:
            typer.echo(
                f"Error finding project profile by name {profile_name}: {e}", err=True
            )
            raise Exception(f"Failed to find project profile {profile_name}: {e}")

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

        # Check if project already exists
        existing_project_id = datazone.get_project_id_by_name(
            project_name, domain_id, region
        )
        if existing_project_id:
            typer.echo(f"🔍 Project {project_name} already exists")

        # Generate CloudFormation template (project only, no memberships)
        template_dict = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Create a single DataZone Project",
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

        # Add CustomerProvidedRoleConfigs if role_arn is provided
        if role_arn:
            template_dict["Resources"]["DataZoneProject"]["Properties"][
                "CustomerProvidedRoleConfigs"
            ] = [{"RoleArn": role_arn, "RoleDesignation": "PROJECT_OWNER"}]
            typer.echo(f"✓ Using customer-provided role: {role_arn}")

        # Convert template to JSON
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

        # Create or update the stack
        try:
            response = cf_client.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=parameters,
                Capabilities=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
                Tags=tags,
            )
            typer.echo(f"Stack creation initiated: {response['StackId']}")

        except cf_client.exceptions.AlreadyExistsException:
            # Stack already exists - attempt to update it
            typer.echo(f"CloudFormation stack {stack_name} already exists")

            # Check if stack is in a transitional state
            try:
                stack_response = cf_client.describe_stacks(StackName=stack_name)
                current_status = stack_response["Stacks"][0]["StackStatus"]

                if "IN_PROGRESS" in current_status:
                    typer.echo(f"⏳ Stack is in transitional state: {current_status}")
                    typer.echo("Waiting for stack to reach stable state...")

                    # Wait for stack to reach stable state
                    max_wait_attempts = 60  # 30 minutes
                    wait_attempt = 0

                    while (
                        wait_attempt < max_wait_attempts
                        and "IN_PROGRESS" in current_status
                    ):
                        time.sleep(30)
                        wait_attempt += 1
                        try:
                            stack_response = cf_client.describe_stacks(
                                StackName=stack_name
                            )
                            current_status = stack_response["Stacks"][0]["StackStatus"]
                            typer.echo(f"Stack status: {current_status}")
                        except Exception:
                            break

                    if "IN_PROGRESS" in current_status:
                        typer.echo("⏰ Timeout waiting for stack to reach stable state")
                        return False

            except Exception as e:
                typer.echo(f"Warning: Could not check stack status: {e}")

            try:
                typer.echo(f"Updating CloudFormation stack: {stack_name}")
                cf_client.update_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Capabilities=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
                    Tags=tags,
                )

                # Wait for update to complete
                typer.echo("Waiting for stack update to complete...")
                waiter = cf_client.get_waiter("stack_update_complete")
                waiter.wait(
                    StackName=stack_name,
                    WaiterConfig={"Delay": 30, "MaxAttempts": 60},
                )
                typer.echo(f"✅ Stack {stack_name} updated successfully")

            except cf_client.exceptions.ClientError as update_error:

                error_message = str(update_error)

                if "No updates are to be performed" in error_message:
                    # Check if this is a legacy stack that needs membership resources removed
                    try:
                        stack_response = cf_client.describe_stacks(StackName=stack_name)
                        stack_resources = cf_client.describe_stack_resources(
                            StackName=stack_name
                        )

                        # Check if stack has membership resources that need to be removed
                        has_membership_resources = any(
                            resource["ResourceType"]
                            == "AWS::DataZone::ProjectMembership"
                            for resource in stack_resources["StackResources"]
                        )

                        if has_membership_resources:
                            typer.echo(
                                f"🔄 Stack {stack_name} has legacy membership resources - forcing update to remove them"
                            )
                            # Force update by adding a dummy parameter change
                            updated_parameters = parameters.copy()
                            updated_parameters.append(
                                {
                                    "ParameterKey": "ProjectDescription",
                                    "ParameterValue": f"Auto-created project for {project_name} in {pipeline_name} pipeline (updated)",
                                }
                            )

                            cf_client.update_stack(
                                StackName=stack_name,
                                TemplateBody=template_body,
                                Parameters=updated_parameters,
                                Capabilities=[
                                    "CAPABILITY_IAM",
                                    "CAPABILITY_AUTO_EXPAND",
                                ],
                                Tags=tags,
                            )

                            # Wait for update to complete
                            typer.echo("Waiting for stack update to complete...")
                            waiter = cf_client.get_waiter("stack_update_complete")
                            waiter.wait(
                                StackName=stack_name,
                                WaiterConfig={"Delay": 30, "MaxAttempts": 60},
                            )
                            typer.echo(
                                f"✅ Stack {stack_name} updated successfully (membership resources removed)"
                            )
                        else:
                            typer.echo(f"✅ Stack {stack_name} is already up to date")
                    except Exception as check_error:
                        typer.echo(
                            f"Warning: Could not check for legacy membership resources: {check_error}"
                        )
                        typer.echo(f"✅ Stack {stack_name} is already up to date")
                else:
                    typer.echo(
                        f"❌ Failed to update stack {stack_name}: {update_error}"
                    )
                    return False

            return True

        # Wait for stack creation to complete
        typer.echo("Waiting for stack creation to complete...")
        waiter = cf_client.get_waiter("stack_create_complete")

        try:
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={"Delay": 30, "MaxAttempts": 60},
            )
            typer.echo(f"✅ Stack {stack_name} created successfully")
            return True

        except Exception as e:
            typer.echo(f"❌ Stack creation failed: {str(e)}", err=True)
            return False

    except Exception as e:
        typer.echo(f"Error creating project via CloudFormation: {str(e)}", err=True)
        return False


def wait_for_project_deployment(project_name, project_id, domain_id, region):
    """Wait for project deployment to complete using DataZone API."""
    try:
        datazone_client = boto3.client("datazone", region_name=region)

        # Poll project status until it's active
        max_attempts = 60  # 30 minutes with 30-second intervals
        attempt = 0

        while attempt < max_attempts:
            try:
                response = datazone_client.get_project(
                    domainIdentifier=domain_id, identifier=project_id
                )

                project_status = response.get("projectStatus", "UNKNOWN")
                typer.echo(f"Project status: {project_status}")

                if project_status == "ACTIVE":
                    typer.echo(f"✅ Project {project_name} is now active")
                    return True
                elif project_status in ["FAILED", "DELETED"]:
                    typer.echo(
                        f"❌ Project {project_name} deployment failed with status: {project_status}"
                    )
                    return False

                # Wait before next check
                time.sleep(30)
                attempt += 1

            except Exception as e:
                typer.echo(f"Error checking project status: {str(e)}")
                time.sleep(30)
                attempt += 1

        typer.echo(f"⏰ Timeout waiting for project {project_name} to become active")
        return False

    except Exception as e:
        typer.echo(f"Error waiting for project deployment: {str(e)}")
        return False


def delete_project_stack(
    project_name, domain_name, region, pipeline_name, target_name, output="TEXT"
):
    """Delete CloudFormation stack for a project."""
    try:
        # Generate stack name: SMUS-{pipeline}-{target}-{project}-{template}
        clean_pipeline = pipeline_name.replace("_", "-").replace(" ", "-").lower()
        clean_target = target_name.replace("_", "-").replace(" ", "-").lower()
        clean_project = project_name.replace("_", "-").replace(" ", "-").lower()
        stack_name = f"SMUS-{clean_pipeline}-{clean_target}-{clean_project}-project"

        cf_client = boto3.client("cloudformation", region_name=region)

        if output.upper() != "JSON":
            typer.echo(f"Deleting CloudFormation stack: {stack_name}")
        cf_client.delete_stack(StackName=stack_name)

        # Wait for deletion to complete
        if output.upper() != "JSON":
            typer.echo("Waiting for stack deletion to complete...")
        waiter = cf_client.get_waiter("stack_delete_complete")
        waiter.wait(
            StackName=stack_name,
            WaiterConfig={"Delay": 30, "MaxAttempts": 60},
        )
        if output.upper() != "JSON":
            typer.echo(f"✅ Stack {stack_name} deleted successfully")
        return True

    except cf_client.exceptions.ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ValidationError" and "does not exist" in str(e):
            if output.upper() != "JSON":
                typer.echo(f"✅ Stack {stack_name} does not exist")
            return True
        else:
            if output.upper() != "JSON":
                typer.echo(f"❌ Failed to delete stack {stack_name}: {e}")
            return False
    except Exception as e:
        if output.upper() != "JSON":
            typer.echo(f"❌ Error deleting stack {stack_name}: {e}")
        return False


def update_project_stack_tags(stack_name, region, tags):
    """Update CloudFormation stack tags if stack exists."""
    try:
        cf_client = boto3.client("cloudformation", region_name=region)

        # Check if stack exists first
        try:
            cf_client.describe_stacks(StackName=stack_name)
        except cf_client.exceptions.ClientError as e:
            if "does not exist" in str(e):
                typer.echo(
                    f"⚠️  Stack {stack_name} not found - project was created outside CICD, skipping tag update"
                )
                return True
            raise

        typer.echo(f"Updating CloudFormation stack tags: {stack_name}")
        cf_client.update_stack(
            StackName=stack_name,
            UsePreviousTemplate=True,
            Tags=tags,
        )

        typer.echo(f"✅ Stack {stack_name} tags updated successfully")
        return True

    except cf_client.exceptions.ClientError as e:
        if "No updates are to be performed" in str(e):
            typer.echo(f"✅ Stack {stack_name} tags are already up to date")
            return True
        else:
            typer.echo(f"❌ Failed to update stack tags {stack_name}: {e}")
            return False
    except Exception as e:
        typer.echo(f"❌ Error updating stack tags {stack_name}: {e}")
        return False
