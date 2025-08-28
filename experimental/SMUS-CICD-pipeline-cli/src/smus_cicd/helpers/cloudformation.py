"""
CloudFormation utility functions for SMUS CI/CD CLI.
"""

import boto3
import typer
import time
from pathlib import Path
from . import datazone


def create_project_via_cloudformation(project_name, profile_name, domain_name, region, pipeline_name, target_name, target_stage=None, user_parameters=None, owners=None, contributors=None):
    """Create DataZone project with memberships using dynamically generated CloudFormation template."""
    try:
        cf_client = boto3.client('cloudformation', region_name=region)
        datazone_client = boto3.client('datazone', region_name=region)
        
        # Convert userParameters to CloudFormation format
        user_parameters_cf = []
        if user_parameters:
            for env_config in user_parameters:
                env_dict = {
                    'EnvironmentConfigurationName': env_config.EnvironmentConfigurationName,
                    'EnvironmentParameters': []
                }
                for param in env_config.parameters:
                    env_dict['EnvironmentParameters'].append({
                        'Name': param.name,
                        'Value': param.value
                    })
                user_parameters_cf.append(env_dict)
        
        # Look up domain ID from domain name
        try:
            domains_response = datazone_client.list_domains()
            domain_id = None
            for domain in domains_response.get('items', []):
                if domain['name'] == domain_name:
                    domain_id = domain['id']
                    break
            
            if not domain_id:
                typer.echo(f"Error: Domain '{domain_name}' not found", err=True)
                return False
                
        except Exception as e:
            typer.echo(f"Error finding domain by name {domain_name}: {e}", err=True)
            return False
        
        # Look up project profile ID from profile name
        try:
            profiles_response = datazone_client.list_project_profiles(domainIdentifier=domain_id)
            profile_id = None
            for profile in profiles_response.get('items', []):
                if profile['name'] == profile_name:
                    profile_id = profile['id']
                    break
            
            if not profile_id:
                typer.echo(f"Error: Project profile '{profile_name}' not found", err=True)
                return False
                
        except Exception as e:
            typer.echo(f"Error finding project profile by name {profile_name}: {e}", err=True)
            return False
        
        # Generate stack name: SMUS-{pipeline}-{target}-{project}-{template}
        clean_pipeline = pipeline_name.replace('_', '-').replace(' ', '-').lower()
        clean_target = target_name.replace('_', '-').replace(' ', '-').lower()
        clean_project = project_name.replace('_', '-').replace(' ', '-').lower()
        stack_name = f"SMUS-{clean_pipeline}-{clean_target}-{clean_project}-project"
        
        # Prepare stack tags
        tags = [
            {'Key': 'PipelineName', 'Value': pipeline_name},
            {'Key': 'TargetName', 'Value': target_name},
            {'Key': 'CreatedBy', 'Value': 'SMUS-CLI'}
        ]
        if target_stage:
            tags.append({'Key': 'TargetStage', 'Value': target_stage})
        
        # Resolve usernames to DataZone user IDs before template generation
        owner_ids = []
        contributor_ids = []
        if owners or contributors:
            if owners:
                owner_ids = datazone.resolve_usernames_to_ids(owners, domain_id, region)
                typer.echo(f"Resolved {len(owner_ids)} owners: {owners} -> {owner_ids}")
            if contributors:
                contributor_ids = datazone.resolve_usernames_to_ids(contributors, domain_id, region)
                typer.echo(f"Resolved {len(contributor_ids)} contributors: {contributors} -> {contributor_ids}")
        
        # Generate CloudFormation template dynamically
        template_dict = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Create a single DataZone Project with memberships",
            "Parameters": {
                "DomainIdentifier": {
                    "Type": "String",
                    "Description": "DataZone Domain ID"
                },
                "ProjectProfileId": {
                    "Type": "String", 
                    "Description": "Project Profile ID to use for the project"
                },
                "ProjectName": {
                    "Type": "String",
                    "Description": "Name for the project",
                    "MinLength": 1,
                    "MaxLength": 64
                },
                "ProjectDescription": {
                    "Type": "String",
                    "Default": "DataZone project for CI/CD pipeline",
                    "Description": "Description for the project"
                }
            },
            "Resources": {
                "DataZoneProject": {
                    "Type": "AWS::DataZone::Project",
                    "Properties": {
                        "DomainIdentifier": {"Ref": "DomainIdentifier"},
                        "Name": {"Ref": "ProjectName"},
                        "Description": {"Ref": "ProjectDescription"},
                        "ProjectProfileId": {"Ref": "ProjectProfileId"}
                    }
                }
            },
            "Outputs": {
                "ProjectId": {
                    "Description": "DataZone Project ID",
                    "Value": {"Fn::GetAtt": ["DataZoneProject", "Id"]},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-ProjectId"}}
                },
                "ProjectName": {
                    "Description": "DataZone Project Name", 
                    "Value": {"Ref": "ProjectName"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-ProjectName"}}
                }
            }
        }
        
        # Add UserParameters if they exist
        if user_parameters_cf:
            template_dict["Resources"]["DataZoneProject"]["Properties"]["UserParameters"] = user_parameters_cf
        
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
                        "Designation": "PROJECT_OWNER"
                    }
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
                        "Designation": "PROJECT_CONTRIBUTOR"
                    }
                }
                membership_counter += 1
        
        import json
        template_body = json.dumps(template_dict)
        
        # Parameters for the stack
        parameters = [
            {
                'ParameterKey': 'DomainIdentifier',
                'ParameterValue': domain_id
            },
            {
                'ParameterKey': 'ProjectProfileId', 
                'ParameterValue': profile_id
            },
            {
                'ParameterKey': 'ProjectName',
                'ParameterValue': project_name
            },
            {
                'ParameterKey': 'ProjectDescription',
                'ParameterValue': f'Auto-created project for {project_name} in {pipeline_name} pipeline'
            }
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
                Capabilities=['CAPABILITY_IAM', 'CAPABILITY_AUTO_EXPAND'],
                Tags=tags
            )
            
            stack_id = response['StackId']
            typer.echo(f"Stack creation initiated: {stack_id}")
            
        except cf_client.exceptions.AlreadyExistsException:
            # Stack already exists - check if project exists in DataZone
            typer.echo(f"CloudFormation stack {stack_name} already exists")
            
            # Check if the project actually exists in DataZone
            domain_id = datazone.get_domain_id_by_name(domain_name, region)
            if domain_id:
                project_id = datazone.get_project_id_by_name(project_name, domain_id, region)
                if project_id:
                    typer.echo(f"✅ Project {project_name} already exists and is ready")
                    return True
            
            # Stack exists but project doesn't - this is an error state
            typer.echo(f"❌ Stack exists but project {project_name} not found in DataZone")
            return False
        
        # Wait for stack creation to complete
        typer.echo("Waiting for stack creation to complete...")
        waiter = cf_client.get_waiter('stack_create_complete')
        
        try:
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': 60  # 30 minutes max
                }
            )
            typer.echo(f"✅ Stack {stack_name} created successfully")
            
            # Wait for project deployment to complete using DataZone API
            typer.echo("Waiting for project deployment to complete...")
            domain_id = datazone.get_domain_id_by_name(domain_name, region)
            if domain_id:
                project_id = datazone.get_project_id_by_name(project_name, domain_id, region)
                if project_id:
                    return wait_for_project_deployment(project_name, project_id, domain_id, region)
            
            return True
            
        except Exception as e:
            typer.echo(f"❌ Stack creation failed: {str(e)}", err=True)
            
            # Get stack events for debugging
            try:
                events = cf_client.describe_stack_events(StackName=stack_name)
                typer.echo("Recent stack events:")
                for event in events['StackEvents'][:5]:
                    status = event.get('ResourceStatus', 'N/A')
                    reason = event.get('ResourceStatusReason', 'N/A')
                    typer.echo(f"  - {event.get('LogicalResourceId')}: {status} - {reason}")
            except:
                pass
                
            return False
            
    except Exception as e:
        typer.echo(f"Error creating project via CloudFormation: {str(e)}", err=True)
        return False


def wait_for_project_deployment(project_name, project_id, domain_id, region):
    """Wait for project deployment to complete using DataZone API."""
    try:
        datazone_client = boto3.client('datazone', region_name=region)
        max_attempts = 120  # 10 minutes
        
        for attempt in range(max_attempts):
            try:
                project_response = datazone_client.get_project(
                    domainIdentifier=domain_id,
                    identifier=project_id
                )
                
                status = project_response.get('projectStatus')
                deployment_status = project_response.get('overallDeploymentStatus')
                
                typer.echo(f"Project status: {status}, Deployment status: {deployment_status} (attempt {attempt + 1}/{max_attempts})")
                
                if status == 'ACTIVE' and deployment_status != 'IN_PROGRESS':
                    typer.echo(f"✅ Project {project_name} is fully deployed and ready")
                    return True
                elif status in ['FAILED', 'DELETED']:
                    typer.echo(f"❌ Project creation failed with status: {status}", err=True)
                    return False
                
                time.sleep(5)  # Wait 5 seconds between checks
                
            except Exception as e:
                typer.echo(f"Error checking project status: {str(e)}")
                time.sleep(5)
        
        typer.echo(f"⚠️ Timeout waiting for project deployment to complete", err=True)
        return False
        
    except Exception as e:
        typer.echo(f"Error waiting for project deployment: {str(e)}", err=True)
        return False


def delete_project_stack(project_name, domain_name, region, pipeline_name, target_name, output="TEXT"):
    """Delete CloudFormation stack for a project."""
    try:
        cf_client = boto3.client('cloudformation', region_name=region)
        
        # Generate stack name using same logic as creation
        clean_pipeline = pipeline_name.replace('_', '-').replace(' ', '-').lower()
        clean_target = target_name.replace('_', '-').replace(' ', '-').lower()
        clean_project = project_name.replace('_', '-').replace(' ', '-').lower()
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
            waiter = cf_client.get_waiter('stack_delete_complete')
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': 60  # 30 minutes max
                }
            )
            if output.upper() != "JSON":
                typer.echo(f"✅ Stack {stack_name} deleted successfully")
            return True
            
        except cf_client.exceptions.ClientError as e:
            if 'does not exist' in str(e):
                if output.upper() != "JSON":
                    typer.echo(f"⚠️ Stack {stack_name} not found - skipping")
                return True
            else:
                raise e
                
    except Exception as e:
        typer.echo(f"❌ Error deleting CloudFormation stack: {str(e)}", err=True)
        return False


    """Update existing project stack with tags."""
    try:
        cf_client = boto3.client('cloudformation', region_name=region)
        
        # Generate stack name
        clean_pipeline = pipeline_name.replace('_', '-').replace(' ', '-').lower()
        clean_target = target_name.replace('_', '-').replace(' ', '-').lower()
        clean_project = project_name.replace('_', '-').replace(' ', '-').lower()
        stack_name = f"SMUS-{clean_pipeline}-{clean_target}-{clean_project}-project"
        
        # Prepare stack tags
        tags = [
            {'Key': 'PipelineName', 'Value': pipeline_name},
            {'Key': 'TargetName', 'Value': target_name},
            {'Key': 'CreatedBy', 'Value': 'SMUS-CLI'}
        ]
        if target_stage:
            tags.append({'Key': 'TargetStage', 'Value': target_stage})
        
        # Check if stack exists
        try:
            response = cf_client.describe_stacks(StackName=stack_name)
            stack_status = response['Stacks'][0]['StackStatus']
            
            if stack_status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                # Read the CloudFormation template
                template_path = Path(__file__).parent.parent / "cloudformation" / "single-project.yaml"
                with open(template_path, 'r') as f:
                    template_body = f.read()
                
                # Get current parameters
                current_stack = response['Stacks'][0]
                parameters = [
                    {
                        'ParameterKey': param['ParameterKey'],
                        'ParameterValue': param['ParameterValue']
                    }
                    for param in current_stack['Parameters']
                ]
                
                # Update stack with tags
                typer.echo(f"Updating project stack tags: {stack_name}")
                cf_client.update_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Capabilities=['CAPABILITY_IAM'],
                    Tags=tags
                )
                
                # Wait for update to complete
                waiter = cf_client.get_waiter('stack_update_complete')
                waiter.wait(StackName=stack_name, WaiterConfig={'MaxAttempts': 60, 'Delay': 5})
                
                typer.echo(f"✅ Project stack {stack_name} updated with tags")
                return True
            else:
                typer.echo(f"⚠️ Project stack {stack_name} is in state {stack_status}, skipping update")
                return False
                
        except cf_client.exceptions.ClientError as e:
            if 'does not exist' in str(e):
                typer.echo(f"⚠️ Project stack {stack_name} does not exist")
                return False
            else:
                raise e
                
    except Exception as e:
        if 'No updates are to be performed' in str(e):
            typer.echo(f"✅ Project stack {stack_name} tags are already up to date")
            return True
        else:
            typer.echo(f"❌ Error updating project stack tags: {str(e)}", err=True)
            return False



