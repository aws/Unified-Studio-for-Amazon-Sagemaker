"""Project management utilities for SMUS CLI."""

import typer
from typing import Dict, Any, List, Optional
from . import datazone, cloudformation
from .utils import get_datazone_project_info
from .error_handler import handle_error, handle_success


class ProjectManager:
    """Manages project creation and initialization operations."""

    def __init__(self, manifest, config: Dict[str, Any]):
        self.manifest = manifest
        self.config = config
        self.domain_name = manifest.domain.name
        self.region = manifest.domain.region

    def ensure_project_exists(self, target_name: str, target_config) -> Dict[str, Any]:
        """Ensure project exists, create if needed and configured to do so."""
        project_name = target_config.project.name

        # Check if project exists in DataZone first
        project_info = get_datazone_project_info(project_name, self.config)

        if "error" not in project_info:
            # Project exists - check and create missing environments
            handle_success(f"✅ Project '{project_name}' already exists")
            self._update_existing_project(target_name, target_config, project_name)
            self._ensure_environments_exist(target_name, target_config, project_info)
            return project_info

        # Project doesn't exist - check if we should create it
        if self._should_create_project(target_config):
            project_info = self._create_new_project(target_name, target_config, project_name)
            if "error" not in project_info:
                # After creating project, ensure environments exist
                self._ensure_environments_exist(target_name, target_config, project_info)
            return project_info

        # Project doesn't exist and we're not configured to create it
        handle_error(f"Project '{project_name}' not found and create=false")
        return project_info

    def _should_create_project(self, target_config) -> bool:
        """Check if project should be created based on configuration."""
        should_create = target_config.project.create
        if target_config.initialization and target_config.initialization.project:
            should_create = should_create or target_config.initialization.project.create
        return should_create

    def _create_new_project(
        self, target_name: str, target_config, project_name: str
    ) -> Dict[str, Any]:
        """Create a new project via CloudFormation."""
        typer.echo("🔧 Auto-initializing target infrastructure...")

        # Double-check project doesn't exist (race condition protection)
        project_info = get_datazone_project_info(project_name, self.config)
        if "error" not in project_info:
            handle_success(
                f"✅ Project '{project_name}' was created by another process"
            )
            return project_info

        # Get domain ID
        domain_id = datazone.get_domain_id_by_name(self.domain_name, self.region)
        if not domain_id:
            handle_error(f"Domain '{self.domain_name}' not found")

        # Extract project configuration
        profile_name = self._get_profile_name(target_config)
        user_parameters = self._extract_user_parameters(target_config, target_name)
        owners, contributors = self._extract_memberships(target_config)

        typer.echo(f"Creating project '{project_name}' via CloudFormation...")
        success = cloudformation.create_project_via_cloudformation(
            project_name,
            profile_name,
            self.domain_name,
            self.region,
            self.manifest.pipeline_name,
            target_name,
            target_config.stage,
            user_parameters,
            owners,
            contributors,
        )

        if not success:
            handle_error("Failed to create project")

        handle_success("Target infrastructure ready")
        return get_datazone_project_info(project_name, self.config)

    def _update_existing_project(
        self, target_name: str, target_config, project_name: str
    ):
        """Update existing project stack tags and memberships."""
        typer.echo("Updating project stack tags...")
        cloudformation.update_project_stack_tags(
            project_name,
            self.domain_name,
            self.region,
            self.manifest.pipeline_name,
            target_name,
            target_config.stage,
        )

        owners, contributors = self._extract_memberships(target_config)
        if owners or contributors:
            typer.echo(
                "⚠️ Project memberships cannot be updated for existing projects - use CloudFormation console to modify memberships"
            )

    def _get_profile_name(self, target_config) -> str:
        """Extract profile name from target configuration."""
        profile_name = target_config.project.profile_name
        if target_config.initialization and target_config.initialization.project:
            profile_name = (
                profile_name or target_config.initialization.project.profile_name
            )
        return profile_name

    def _extract_user_parameters(
        self, target_config, target_name: str
    ) -> Optional[List]:
        """Extract user parameters from target configuration."""
        print(f"🔍 DEBUG: Extracting user parameters for target: {target_name}")

        if not (target_config.initialization and target_config.initialization.project):
            print(f"🔍 DEBUG: No initialization.project found for target: {target_name}")
            return None

        # Parse userParameters directly from YAML since dataclass parsing doesn't handle nested structure
        import yaml

        with open(self.manifest._file_path, "r") as f:
            pipeline_data = yaml.safe_load(f)

        target_data = pipeline_data.get("targets", {}).get(target_name, {})
        init_data = target_data.get("initialization", {})
        project_data = init_data.get("project", {})

        print(f"🔍 DEBUG: Target data keys: {list(target_data.keys())}")
        print(f"🔍 DEBUG: Init data keys: {list(init_data.keys())}")
        print(f"🔍 DEBUG: Project data keys: {list(project_data.keys())}")

        # Check for both userParameters and environments
        yaml_user_params = project_data.get("userParameters", [])
        environments = init_data.get("environments", [])

        print(f"🔍 DEBUG: Found userParameters: {yaml_user_params}")
        print(f"🔍 DEBUG: Found environments: {environments}")

        if not yaml_user_params and environments:
            print("🔍 DEBUG: Converting environments to userParameters format")
            # Convert environments to userParameters format
            yaml_user_params = []
            for env in environments:
                if isinstance(env, dict) and "EnvironmentConfigurationName" in env:
                    yaml_user_params.append(env)
                elif isinstance(env, str):
                    yaml_user_params.append({"EnvironmentConfigurationName": env, "parameters": []})
                else:
                    print(f"🔍 DEBUG: Unknown environment format: {env}")
            print(f"🔍 DEBUG: Converted userParameters: {yaml_user_params}")

        if not yaml_user_params:
            print("🔍 DEBUG: No userParameters or environments found")
            return None

        return self._build_user_parameters(yaml_user_params)

    def _build_user_parameters(self, yaml_user_params: List) -> List:
        """Build user parameters from YAML data."""
        from smus_cicd.pipeline.pipeline_manifest import (
            EnvironmentUserParameters,
            UserParameter,
        )

        user_parameters = []
        for env_config in yaml_user_params:
            env_name = env_config.get("EnvironmentConfigurationName")
            params = env_config.get("parameters", [])
            user_param_objects = [
                UserParameter(name=param.get("name"), value=param.get("value"))
                for param in params
            ]
            user_parameters.append(
                EnvironmentUserParameters(
                    EnvironmentConfigurationName=env_name, parameters=user_param_objects
                )
            )

        return user_parameters

    def _ensure_environments_exist(self, target_name: str, target_config, project_info: Dict[str, Any]) -> None:
        """Ensure required environments exist in the project."""
        if not (target_config.initialization and hasattr(target_config.initialization, 'environments')):
            print(f"🔍 DEBUG: No environments specified for target: {target_name}")
            return

        project_id = project_info.get('project_id')
        domain_id = project_info.get('domain_id')

        if not project_id or not domain_id:
            print(f"🔍 DEBUG: Missing project_id or domain_id: {project_id}, {domain_id}")
            return

        print(f"🔍 DEBUG: Checking environments for project {project_id}")

        # Get existing environments in the project
        try:
            import boto3
            datazone_client = boto3.client("datazone", region_name=self.region)

            existing_envs_response = datazone_client.list_environments(
                domainIdentifier=domain_id,
                projectIdentifier=project_id
            )
            existing_env_names = [env['name'] for env in existing_envs_response.get('items', [])]
            print(f"🔍 DEBUG: Existing environments: {existing_env_names}")

        except Exception as e:
            print(f"🔍 DEBUG: Error listing environments: {e}")
            return

        # Check each required environment
        for env_config in target_config.initialization.environments:
            env_name = env_config.get('EnvironmentConfigurationName') if isinstance(env_config, dict) else env_config
            print(f"🔍 DEBUG: Checking required environment: {env_name}")

            if env_name in existing_env_names:
                print(f"✅ Environment '{env_name}' already exists")
                continue

            # Environment doesn't exist, try to create it
            print(f"🔧 Creating missing environment: {env_name}")
            success = self._create_environment(domain_id, project_id, env_name)

            if success:
                print(f"✅ Environment '{env_name}' created successfully")
                # Check if this is a workflow environment and validate MWAA
                if 'workflow' in env_name.lower() or 'mwaa' in env_name.lower():
                    self._validate_mwaa_environment(project_id, domain_id)
            else:
                print(f"❌ Failed to create environment: {env_name}")

    def _create_environment(self, domain_id: str, project_id: str, env_name: str) -> bool:
        """Create a DataZone environment."""
        try:
            import boto3
            datazone_client = boto3.client("datazone", region_name=self.region)

            # Get available environment profiles to find the right one
            profiles_response = datazone_client.list_environment_profiles(
                domainIdentifier=domain_id,
                projectIdentifier=project_id
            )

            # Find matching profile
            profile_id = None
            for profile in profiles_response.get('items', []):
                if profile['name'] == env_name:
                    profile_id = profile['id']
                    break

            if not profile_id:
                print(f"🔍 DEBUG: Environment profile '{env_name}' not found")
                return False

            # Create the environment
            response = datazone_client.create_environment(
                domainIdentifier=domain_id,
                projectIdentifier=project_id,
                environmentProfileIdentifier=profile_id,
                name=env_name,
                description=f"Auto-created environment for {env_name}"
            )

            print(f"🔍 DEBUG: Environment creation initiated: {response.get('id')}")
            return True

        except Exception as e:
            print(f"🔍 DEBUG: Error creating environment: {e}")
            return False

    def _validate_mwaa_environment(self, project_id: str, domain_id: str) -> None:
        """Validate MWAA environment is available."""
        try:
            import boto3
            import time

            # Wait a bit for environment to be ready
            time.sleep(5)

            datazone_client = boto3.client("datazone", region_name=self.region)

            # Get project connections to find MWAA connection
            connections_response = datazone_client.list_project_data_sources(
                domainIdentifier=domain_id,
                projectIdentifier=project_id
            )

            mwaa_connection = None
            for conn in connections_response.get('items', []):
                if 'mwaa' in conn.get('type', '').lower():
                    mwaa_connection = conn
                    break

            if mwaa_connection:
                print("✅ MWAA environment is available")
            else:
                print("⚠️  MWAA environment connection not found")

        except Exception as e:
            print(f"🔍 DEBUG: Error validating MWAA: {e}")

    def _extract_memberships(self, target_config) -> tuple[List[str], List[str]]:
        """Extract owners and contributors from target configuration."""
        owners = []
        contributors = []

        if target_config.initialization and target_config.initialization.project:
            owners = getattr(target_config.initialization.project, "owners", [])
            contributors = getattr(
                target_config.initialization.project, "contributors", []
            )
        else:
            owners = target_config.project.owners or []
            contributors = target_config.project.contributors or []

        return owners, contributors
