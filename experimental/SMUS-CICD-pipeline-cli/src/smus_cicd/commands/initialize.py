"""Initialize command implementation."""
import time
import typer
import boto3
from ..helpers import datazone, cloudformation
from ..pipeline import PipelineManifest

def initialize_command(
    targets: str,
    manifest_file: str,
    async_mode: bool
):
    """Initialize a DataZone workflow environment for the specified target."""
    try:
        manifest = PipelineManifest.from_file(manifest_file)
        
        # Parse targets - handle single target or comma-separated list
        target_list = [t.strip() for t in targets.split(',')]
        
        # Initialize each target
        for target_name in target_list:
            typer.echo(f"Initializing target: {target_name}")
        
        # For now, use first target (can be enhanced later for multi-target)
        target_name = target_list[0]
        
        # Get domain configuration
        domain_name = manifest.domain.name
        region = manifest.domain.region
        
        if not domain_name or not region:
            typer.echo("Error: Domain name and region must be specified in pipeline configuration", err=True)
            raise typer.Exit(1)
        
        # Get target configuration
        if target_name not in manifest.targets:
            typer.echo(f"Error: Target '{target_name}' not found in manifest", err=True)
            raise typer.Exit(1)
        
        target_config = manifest.targets[target_name]
        project_config = target_config.project
        project_name = project_config.name
        
        # Check if target has initialization configuration
        initialization = target_config.initialization
        environments = initialization.environments if initialization else []
        
        # Get project creation details - check both project and initialization.project sections
        should_create = project_config.create
        profile_name = project_config.profile_name
        
        # Also check initialization.project section for backward compatibility
        if initialization and initialization.project:
            init_project_config = initialization.project
            if not should_create:
                should_create = init_project_config.create
            if not profile_name:
                profile_name = init_project_config.profile_name
            
        # Get owners and contributors from initialization.project if available, otherwise from project
        owners = []
        contributors = []
        
        if initialization and initialization.project:
            owners = initialization.project.owners or []
            contributors = initialization.project.contributors or []
        else:
            owners = project_config.owners or []
            contributors = project_config.contributors or []
        
        if not project_name:
            typer.echo(f"Error: No project name found for target '{target_name}'", err=True)
            raise typer.Exit(1)
        
        typer.echo(f"Initializing environment for target: {target_name}")
        typer.echo(f"Project: {project_name}")
        typer.echo(f"Domain: {domain_name}")
        typer.echo(f"Region: {region}")
        
        # Get domain ID and check if project exists
        domain_id = datazone.get_domain_id_by_name(domain_name, region)
        if not domain_id:
            typer.echo(f"Error: Domain '{domain_name}' not found", err=True)
            raise typer.Exit(1)
        
        project_id = datazone.get_project_id_by_name(project_name, domain_id, region)
        
        # Handle project creation if needed
        if not project_id:
            if should_create:
                if not profile_name:
                    typer.echo(f"Error: profileName required for project creation", err=True)
                    raise typer.Exit(1)
                
                typer.echo(f"Project '{project_name}' not found. Creating via CloudFormation...")
                success = cloudformation.create_project_via_cloudformation(
                    project_name, 
                    profile_name, 
                    domain_name, 
                    region, 
                    manifest.pipeline_name, 
                    target_name,
                    target_config.stage
                )
                
                if not success:
                    typer.echo(f"Failed to create project '{project_name}'", err=True)
                    raise typer.Exit(1)
                
                # Get project ID after creation
                project_id = datazone.get_project_id_by_name(project_name, domain_id, region)
                if not project_id:
                    typer.echo(f"Error: Project '{project_name}' still not found after creation", err=True)
                    raise typer.Exit(1)
                    
                typer.echo(f"✅ Project '{project_name}' created successfully (ID: {project_id})")
                
                # Create project memberships for new project
                if owners or contributors:
                    typer.echo("⚠️ Project memberships should be specified during project creation - use deploy command instead")
            else:
                typer.echo(f"Error: Project '{project_name}' not found and create=False", err=True)
                typer.echo("Set project.create=True in pipeline configuration to auto-create", err=True)
                raise typer.Exit(1)
        else:
            typer.echo(f"Project '{project_name}' exists")
            
            # Always update project stack tags to ensure they're current
            typer.echo("Updating project stack tags...")
            cloudformation.update_project_stack_tags(
                project_name, domain_name, region, 
                manifest.pipeline_name, target_name, target_config.stage
            )
            
            # Update project memberships for existing project if specified
            if owners or contributors:
                typer.echo("⚠️ Project memberships cannot be updated for existing projects - use CloudFormation console to modify memberships")
        
        # Environment creation is optional - skip if no environments configured
        if not environments:
            typer.echo(f"No environments configured for target '{target_name}', skipping environment creation")
            typer.echo(f"✅ Target '{target_name}' initialization complete (project only)")
            return
        
        # Get the environment configuration name from target
        target_env_config_name = environments[0].get('EnvironmentConfigurationName')
        if not target_env_config_name:
            typer.echo(f"Error: No EnvironmentConfigurationName found in target '{target_name}' initialization", err=True)
            raise typer.Exit(1)
        
        datazone_client = boto3.client('datazone', region_name=region)
        
        # Check if environments already exist for this target
        env_name = f"{target_name}-workflow-env"
        existing_environments = []
        
        try:
            environments_response = datazone_client.list_environments(
                domainIdentifier=domain_id,
                projectIdentifier=project_id
            )
            
            for env in environments_response.get('items', []):
                if env.get('name') == env_name:
                    existing_environments.append(env)
                    
        except Exception as e:
            typer.echo(f"Warning: Could not check existing environments: {str(e)}")
        
        # Check if we already have the required environments
        required_env_count = len(environments)
        existing_env_count = len(existing_environments)
        
        if existing_env_count >= required_env_count:
            typer.echo(f"✅ Target '{target_name}' already initialized")
            typer.echo(f"Found {existing_env_count} existing environment(s):")
            for env in existing_environments:
                typer.echo(f"  - {env.get('name')} (ID: {env.get('id')}, Status: {env.get('status')})")
            typer.echo("No additional environments needed.")
            return
        
        # Create environment
        typer.echo(f"Creating environment: {env_name}")
        
        # Get project profile to find environment configuration
        project_details = datazone_client.get_project(
            domainIdentifier=domain_id,
            identifier=project_id
        )
        
        project_profile_id = project_details.get('projectProfileId')
        if not project_profile_id:
            typer.echo("Error: No project profile found", err=True)
            raise typer.Exit(1)
        
        # Get project profile details
        profile_details = datazone_client.get_project_profile(
            domainIdentifier=domain_id,
            identifier=project_profile_id
        )
        
        # Find environment configuration that matches target specification
        env_configs = profile_details.get('environmentConfigurations', [])
        env_config_id = None
        
        for config in env_configs:
            if config.get('name') == target_env_config_name:
                env_config_id = config.get('id')
                typer.echo(f"Using environment configuration: {config.get('name')} ({env_config_id})")
                break
        
        if not env_config_id:
            typer.echo(f"Error: Environment configuration '{target_env_config_name}' not found in project profile")
            typer.echo("Available environment configurations:")
            for config in env_configs:
                typer.echo(f"  - {config.get('name')} ({config.get('id')})")
            raise typer.Exit(1)
        
        # Create environment with configuration
        create_response = datazone_client.create_environment(
            domainIdentifier=domain_id,
            name=env_name,
            projectIdentifier=project_id,
            environmentConfigurationId=env_config_id,
            description=f"Workflow environment for {target_name} target"
        )
        
        environment_id = create_response.get('id')
        typer.echo(f"Environment created with ID: {environment_id}")
        
        # Wait for environment to be ready unless --async flag is used
        if not async_mode:
            typer.echo("Waiting for environment to be ready...")
            max_wait_time = 1800  # 30 minutes
            start_time = time.time()
            
            while True:
                try:
                    env_details = datazone_client.get_environment(
                        domainIdentifier=domain_id,
                        identifier=environment_id
                    )
                    
                    status = env_details.get('status')
                    elapsed = int(time.time() - start_time)
                    typer.echo(f"Environment status: {status} (elapsed: {elapsed}s)")
                    
                    if status == 'ACTIVE':
                        typer.echo("✅ Environment is ready!")
                        break
                    elif status in ['FAILED', 'CANCELLED', 'CREATE_FAILED']:
                        typer.echo(f"❌ Environment creation failed with status: {status}")
                        raise typer.Exit(1)
                    elif elapsed > max_wait_time:
                        typer.echo(f"⏰ Timeout after {max_wait_time}s. Environment status: {status}", err=True)
                        raise typer.Exit(1)
                    
                    time.sleep(30)
                    
                except KeyboardInterrupt:
                    typer.echo("\n⚠️  Wait interrupted by user. Environment may still be creating.")
                    break
                except Exception as e:
                    typer.echo(f"Error checking environment status: {str(e)}", err=True)
                    break
        else:
            typer.echo("⚡ Async mode: Not waiting for environment deployment to complete")
        
        typer.echo(f"✅ Environment initialization complete for target: {target_name}")
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)
