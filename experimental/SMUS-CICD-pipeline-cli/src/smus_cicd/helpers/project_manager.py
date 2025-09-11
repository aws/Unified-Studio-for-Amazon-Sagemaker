"""Project management utilities for SMUS CLI."""

from typing import Any, Dict, List, Optional

import typer

from . import cloudformation, datazone
from .error_handler import handle_error, handle_success
from .utils import get_datazone_project_info


class ProjectManager:
    """Manages project creation and initialization operations."""

    def __init__(self, manifest, config: Dict[str, Any]):
        self.manifest = manifest
        self.config = config
        self.domain_name = manifest.domain.name
        self.region = manifest.domain.region

    def ensure_project_exists(self, target_name: str, target_config) -> Dict[str, Any]:
        """Ensure project exists, create if needed and configured to do so."""
        from .logger import get_logger

        logger = get_logger("project_manager")

        logger.debug(f"ensure_project_exists called for target: {target_name}")

        project_name = target_config.project.name
        logger.debug(f"project_name: {project_name}")

        # Check if project exists in DataZone first
        # Ensure config has region for get_datazone_project_info
        config_with_region = {**self.config, "region": self.region}
        project_info = get_datazone_project_info(project_name, config_with_region)
        logger.debug(f"project_info keys: {list(project_info.keys())}")
        logger.debug(f"project_info has error: {'error' in project_info}")

        if "error" not in project_info:
            # Project exists - check and create missing environments
            logger.debug("Project exists path - calling _ensure_environments_exist")
            handle_success(f"✅ Project '{project_name}' already exists")
            self._update_existing_project(target_name, target_config, project_name)
            environments_ready = self._ensure_environments_exist(
                target_name, target_config, project_info
            )
            if not environments_ready:
                raise Exception(
                    "Environment creation failed - cannot proceed with deployment"
                )
            return project_info

        # Project doesn't exist - check if we should create it
        logger.debug("Project doesn't exist - checking if should create")
        if self._should_create_project(target_config):
            logger.debug("Should create project - calling _create_new_project")
            project_info = self._create_new_project(
                target_name, target_config, project_name
            )
            logger.debug("_create_new_project returned")
            logger.debug(
                f"project_info after creation: {list(project_info.keys()) if isinstance(project_info, dict) else type(project_info)}"
            )
            logger.debug(
                f"project_info has error after creation: {'error' in project_info if isinstance(project_info, dict) else 'not a dict'}"
            )
            if "error" not in project_info:
                # After creating project, ensure environments exist
                print(
                    "🔍 DEBUG: Project created successfully - calling _ensure_environments_exist"
                )
                environments_ready = self._ensure_environments_exist(
                    target_name, target_config, project_info
                )
                if not environments_ready:
                    raise Exception(
                        "Environment creation failed - cannot proceed with deployment"
                    )
            else:
                print(
                    "🔍 DEBUG: Project creation failed - NOT calling _ensure_environments_exist"
                )
            return project_info

        # Project doesn't exist and we're not configured to create it
        print(
            "🔍 DEBUG: Project doesn't exist and create=false - NOT calling _ensure_environments_exist"
        )
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
        config_with_region = {**self.config, "region": self.region}
        project_info = get_datazone_project_info(project_name, config_with_region)
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

        # Extract environments for environment creation
        environments = None
        if target_config.initialization and hasattr(
            target_config.initialization, "environments"
        ):
            environments = target_config.initialization.environments

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
            environments,
        )

        print(
            f"🔍 DEBUG: CloudFormation create_project_via_cloudformation returned: {success}"
        )
        if not success:
            print("🔍 DEBUG: CloudFormation creation failed - returning error")
            handle_error("Failed to create project")

        print("🔍 DEBUG: CloudFormation creation succeeded - managing memberships")

        # Get domain ID for membership management
        domain_id = datazone.get_domain_id_by_name(self.domain_name, self.region)
        if not domain_id:
            handle_error(f"Failed to find domain ID for {self.domain_name}")

        # Get project ID for membership management
        project_id = datazone.get_project_id_by_name(
            project_name, domain_id, self.region
        )
        if not project_id:
            handle_error(f"Failed to find project ID for {project_name}")

        # Manage project memberships via DataZone API
        typer.echo("🔧 Managing project memberships...")
        membership_success = datazone.manage_project_memberships(
            project_id, domain_id, self.region, owners, contributors
        )

        if not membership_success:
            handle_error("Failed to manage project memberships")

        handle_success("Target infrastructure ready")
        config_with_region = {**self.config, "region": self.region}
        final_project_info = get_datazone_project_info(project_name, config_with_region)
        print(
            f"🔍 DEBUG: Final project_info keys: {list(final_project_info.keys()) if isinstance(final_project_info, dict) else type(final_project_info)}"
        )
        print(
            f"🔍 DEBUG: Final project_info has error: {'error' in final_project_info if isinstance(final_project_info, dict) else 'not a dict'}"
        )
        if isinstance(final_project_info, dict) and "error" in final_project_info:
            print(f"🔍 DEBUG: Actual error content: {final_project_info['error']}")
        return final_project_info

    def _update_existing_project(
        self, target_name: str, target_config, project_name: str
    ):
        """Update existing project stack tags and memberships."""
        typer.echo("Updating project stack tags...")
        cloudformation.update_project_stack_tags(
            self.manifest.pipeline_name,
            target_name,
            project_name,
            self.region,
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
            print(
                f"🔍 DEBUG: No initialization.project found for target: {target_name}"
            )
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
                    yaml_user_params.append(
                        {"EnvironmentConfigurationName": env, "parameters": []}
                    )
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

    def _ensure_environments_exist(
        self, target_name: str, target_config, project_info: Dict[str, Any]
    ) -> bool:
        """Ensure required environments exist in the project."""
        print(f"🔍 DEBUG: _ensure_environments_exist called for target: {target_name}")
        print(
            f"🔍 DEBUG: target_config.initialization exists: {target_config.initialization is not None}"
        )

        if target_config.initialization:
            print(
                f"🔍 DEBUG: target_config.initialization type: {type(target_config.initialization)}"
            )
            print(
                f"🔍 DEBUG: target_config.initialization attributes: {dir(target_config.initialization)}"
            )
            print(
                f"🔍 DEBUG: hasattr environments: {hasattr(target_config.initialization, 'environments')}"
            )
            if hasattr(target_config.initialization, "environments"):
                print(
                    f"🔍 DEBUG: environments value: {target_config.initialization.environments}"
                )

        if not (
            target_config.initialization
            and hasattr(target_config.initialization, "environments")
        ):
            print(f"🔍 DEBUG: No environments specified for target: {target_name}")
            return True  # No environments to create is success

        project_id = project_info.get("project_id")

        # Resolve domain_id the same way _create_new_project does
        domain_id = datazone.get_domain_id_by_name(self.domain_name, self.region)

        print(f"🔍 DEBUG: Resolved project_id: {project_id}, domain_id: {domain_id}")

        if not project_id or not domain_id:
            print(
                f"🔍 DEBUG: Missing project_id or domain_id: {project_id}, {domain_id}"
            )
            return False

        print(f"🔍 DEBUG: Checking environments for project {project_id}")

        # Get existing environments in the project
        try:
            import boto3

            datazone_client = boto3.client("datazone", region_name=self.region)

            existing_envs_response = datazone_client.list_environments(
                domainIdentifier=domain_id, projectIdentifier=project_id
            )
            existing_env_names = [
                env["name"] for env in existing_envs_response.get("items", [])
            ]
            print(f"🔍 DEBUG: Existing environments: {existing_env_names}")

        except Exception as e:
            print(f"🔍 DEBUG: Error listing environments: {e}")
            return False

        # Check each required environment
        all_environments_ready = True
        for env_config in target_config.initialization.environments:
            env_name = (
                env_config.get("EnvironmentConfigurationName")
                if isinstance(env_config, dict)
                else env_config
            )
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
                if "workflow" in env_name.lower() or "mwaa" in env_name.lower():
                    self._validate_mwaa_environment(project_id, domain_id)
            else:
                print(f"❌ Failed to create environment: {env_name}")
                all_environments_ready = False

        return all_environments_ready

    def _create_environment(
        self, domain_id: str, project_id: str, env_name: str
    ) -> bool:
        """Create a DataZone environment."""
        try:
            import boto3

            datazone_client = boto3.client("datazone", region_name=self.region)

            # Get project details to find the project profile ID
            print(f"🔍 DEBUG: Getting project details for project: {project_id}")
            project_response = datazone_client.get_project(
                domainIdentifier=domain_id, identifier=project_id
            )

            project_profile_id = project_response.get("projectProfileId")
            if not project_profile_id:
                print("🔍 DEBUG: Project profile ID not found")
                return False

            print(f"🔍 DEBUG: Project profile ID: {project_profile_id}")

            # Get project profile details to find environment configuration
            print("🔍 DEBUG: Getting project profile details")
            profile_details = datazone_client.get_project_profile(
                domainIdentifier=domain_id, identifier=project_profile_id
            )

            # Find environment configuration that matches target specification
            env_configs = profile_details.get("environmentConfigurations", [])
            env_config_id = None

            for config in env_configs:
                if config.get("name") == env_name:
                    env_config_id = config.get("id")
                    print(
                        f"🔍 DEBUG: Using environment configuration: {config.get('name')} ({env_config_id})"
                    )
                    break

            if not env_config_id:
                print(f"🔍 DEBUG: Environment configuration '{env_name}' not found")
                return False

            # Create environment with configuration
            print(
                f"🔍 DEBUG: Creating environment with configuration ID: {env_config_id}"
            )
            response = datazone_client.create_environment(
                domainIdentifier=domain_id,
                projectIdentifier=project_id,
                environmentConfigurationId=env_config_id,
                name=env_name,
                description=f"Auto-created environment for {env_name}",
            )

            environment_id = response.get("id")
            print(f"🔍 DEBUG: Environment creation initiated: {environment_id}")

            # Wait for environment to be fully provisioned
            print("⏳ Waiting for environment to be fully provisioned...")
            max_attempts = (
                360  # 3 hours max (360 * 30 seconds = 10800 seconds = 3 hours)
            )
            attempt = 0

            while attempt < max_attempts:
                try:
                    env_response = datazone_client.get_environment(
                        domainIdentifier=domain_id, identifier=environment_id
                    )
                    status = env_response.get("status")
                    print(
                        f"🔍 DEBUG: Environment status check {attempt + 1}/{max_attempts}: {status}"
                    )

                    if status == "ACTIVE":
                        print("✅ Environment is now ACTIVE and ready")
                        return True
                    elif status in ["FAILED", "CANCELLED"]:
                        print(f"❌ Environment creation failed with status: {status}")
                        return False

                    # Wait 30 seconds before next check
                    import time

                    time.sleep(30)
                    attempt += 1

                except Exception as e:
                    print(f"⚠️ Error checking environment status: {e}")
                    attempt += 1
                    import time

                    time.sleep(30)

            if attempt >= max_attempts:
                print("⚠️ Timeout waiting for environment to become ACTIVE")
                return False

            return True

        except Exception as e:
            print(f"🔍 DEBUG: Error creating environment: {e}")
            return False

    def _validate_mwaa_environment(self, project_id: str, domain_id: str) -> None:
        """Validate MWAA environment is available."""
        try:
            import time

            import boto3

            # Wait a bit for environment to be ready
            time.sleep(5)

            datazone_client = boto3.client("datazone", region_name=self.region)

            # Get project connections to find MWAA connection
            connections_response = datazone_client.list_project_data_sources(
                domainIdentifier=domain_id, projectIdentifier=project_id
            )

            mwaa_connection = None
            for conn in connections_response.get("items", []):
                if "mwaa" in conn.get("type", "").lower():
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
