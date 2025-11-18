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

    def ensure_project_exists(self, stage_name: str, target_config) -> Dict[str, Any]:
        """Ensure project exists, create if needed and configured to do so."""
        from .logger import get_logger

        logger = get_logger("project_manager")

        logger.debug(f"ensure_project_exists called for target: {stage_name}")

        project_name = target_config.project.name
        domain_name = target_config.domain.name
        region = target_config.domain.region

        # Resolve domain name if not provided (using tags)
        if not domain_name:
            domain_id, domain_name = datazone.resolve_domain_id(
                domain_name=None, domain_tags=target_config.domain.tags, region=region
            )
            if not domain_name:
                handle_error("Could not resolve domain name from tags")

        logger.debug(f"project_name: {project_name}")
        logger.debug(f"domain_name: {domain_name}")
        logger.debug(f"region: {region}")

        # Check if project exists in DataZone first
        # Use the config passed in (already has domain info from build_domain_config)
        project_info = get_datazone_project_info(project_name, self.config)
        logger.debug(f"project_info keys: {list(project_info.keys())}")
        logger.debug(f"project_info has error: {'error' in project_info}")
        logger.debug(f"project_info status: {project_info.get('status')}")

        if "error" not in project_info and project_info.get("status") != "NOT_FOUND":
            # Project exists - check and create missing environments
            logger.debug("Project exists path - calling _ensure_environments_exist")
            handle_success(f"✅ Project '{project_name}' already exists")
            self._update_existing_project(
                stage_name, target_config, project_name, region
            )
            environments_ready = self._ensure_environments_exist(
                stage_name, target_config, project_info, domain_name, region
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
                stage_name, target_config, project_name, domain_name, region
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
                    stage_name, target_config, project_info, domain_name, region
                )
                if not environments_ready:
                    raise Exception(
                        "Environment creation failed - cannot proceed with deployment"
                    )
            else:
                print(
                    "🔍 DEBUG: Project creation failed - NOT calling _ensure_environments_exist"
                )
                raise Exception(
                    f"Project creation failed: {project_info.get('error', 'Unknown error')}"
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
        return target_config.project.create

    def _create_new_project(
        self,
        stage_name: str,
        target_config,
        project_name: str,
        domain_name: str,
        region: str,
    ) -> Dict[str, Any]:
        """Create a new project via CloudFormation."""
        typer.echo("🔧 Auto-initializing target infrastructure...")

        # Double-check project doesn't exist (race condition protection)
        config_with_region = {**self.config, "region": region}
        project_info = get_datazone_project_info(project_name, config_with_region)
        if "error" not in project_info and project_info.get("status") != "NOT_FOUND":
            handle_success(
                f"✅ Project '{project_name}' was created by another process"
            )
            return project_info

        # Get domain ID
        domain_id = datazone.get_domain_id_by_name(domain_name, region)
        if not domain_id:
            handle_error(f"Domain '{domain_name}' not found")

        # Extract project configuration
        profile_name = self._get_profile_name(target_config)
        _ = self._extract_user_parameters(
            target_config, stage_name
        )  # Reserved for future use
        owners, contributors = self._extract_memberships(target_config)
        role_arn = self._get_role_arn(target_config)
        policy_arns = self._get_policy_arns(target_config)

        # Handle role creation or policy attachment
        if policy_arns:
            import boto3

            from . import iam

            sts = boto3.client("sts")
            account_id = sts.get_caller_identity()["Account"]

            if not role_arn:
                # Create new role with policies
                role_name = self._get_role_name(target_config, project_name)
                typer.echo(f"🔧 Creating IAM role: {role_name}")
                role_arn = iam.create_or_update_project_role(
                    role_name=role_name,
                    policy_arns=policy_arns,
                    account_id=account_id,
                    region=region,
                )
            else:
                # Attach policies to existing role
                typer.echo("🔧 Attaching policies to existing role")
                role_arn = iam.create_or_update_project_role(
                    role_name="",  # Not used when role_arn provided
                    policy_arns=policy_arns,
                    account_id=account_id,
                    region=region,
                    role_arn=role_arn,
                )

        # Extract environments for environment creation
        _ = None  # Reserved for future use
        # Check if bootstrap actions include environment creation
        if target_config.bootstrap and target_config.bootstrap.actions:
            _ = [
                a
                for a in target_config.bootstrap.actions
                if a.type.startswith("datazone.create_environment")
            ]

        # TODO: Re-enable CloudFormation path once service role permissions are configured for gamma endpoints
        # typer.echo(f"Creating project '{project_name}' via CloudFormation...")
        # success = cloudformation.create_project_via_cloudformation(
        #     project_name,
        #     profile_name,
        #     domain_name,
        #     region,
        #     self.manifest.application_name,
        #     stage_name,
        #     target_config.stage,
        #     user_parameters,
        #     owners,
        #     contributors,
        #     environments,
        #     role_arn,
        # )

        # Temporary: Use DataZone API directly for gamma endpoints
        typer.echo(f"Creating project '{project_name}' via DataZone API...")
        success = self._create_project_via_datazone_api(
            project_name,
            profile_name,
            domain_name,
            region,
            role_arn,
            owners,
            contributors,
        )

        print(f"🔍 DEBUG: DataZone API create_project returned: {success}")
        if not success:
            print("🔍 DEBUG: Project creation failed - returning error")
            handle_error("Failed to create project")

        print("🔍 DEBUG: Project creation succeeded")

        # Get domain ID for final project info lookup
        domain_id = datazone.get_domain_id_by_name(domain_name, region)
        if not domain_id:
            handle_error(f"Failed to find domain ID for {domain_name}")

        # Get project ID via DataZone API lookup
        project_id = self._get_project_id_with_retry(project_name, domain_id, region)

        if not project_id:
            handle_error(f"Failed to find project ID for {project_name}")

        # Wait for environment deployment to complete
        typer.echo("⏳ Waiting for environment deployment...")
        env_success = self._wait_for_environments(project_id, domain_id, region)
        if not env_success:
            handle_error("Environment deployment failed")

        handle_success("Target infrastructure ready")
        config_with_region = {
            **self.config,
            "region": region,
            "domain_name": domain_name,
        }
        final_project_info = get_datazone_project_info(project_name, config_with_region)
        print(
            f"🔍 DEBUG: Final project_info keys: {list(final_project_info.keys()) if isinstance(final_project_info, dict) else type(final_project_info)}"
        )
        print(
            f"🔍 DEBUG: Final project_info has error: {'error' in final_project_info if isinstance(final_project_info, dict) else 'not a dict'}"
        )
        if isinstance(final_project_info, dict) and "error" in final_project_info:
            print(f"🔍 DEBUG: Actual error content: {final_project_info['error']}")
            raise Exception(f"Project validation failed: {final_project_info['error']}")
        return final_project_info

    def _get_project_id_with_retry(
        self, project_name: str, domain_id: str, region: str, max_attempts: int = 10
    ) -> str:
        """Get project ID with retry logic for newly created projects."""
        import time

        for attempt in range(max_attempts):
            project_id = datazone.get_project_id_by_name(
                project_name, domain_id, region
            )
            if project_id:
                return project_id

            if attempt < max_attempts - 1:
                wait_time = min(2**attempt, 30)  # Exponential backoff, max 30s
                print(
                    f"⏳ Project not found, retrying in {wait_time}s... (attempt {attempt + 1}/{max_attempts})"
                )
                time.sleep(wait_time)

        return None

    def _update_existing_project(
        self, stage_name: str, target_config, project_name: str, region: str
    ):
        """Update existing project stack tags, memberships, and ensure role exists."""
        typer.echo("Updating project stack tags...")

        # Construct stack name and tags
        stack_name = f"{self.manifest.application_name}-{stage_name}-{project_name}"
        tags = [
            {"Key": "Bundle", "Value": self.manifest.application_name},
            {"Key": "Target", "Value": stage_name},
            {"Key": "Project", "Value": project_name},
            {"Key": "Stage", "Value": target_config.stage},
        ]

        cloudformation.update_project_stack_tags(stack_name, region, tags)

        owners, contributors = self._extract_memberships(target_config)
        if owners or contributors:
            typer.echo(
                "⚠️ Project memberships cannot be updated for existing projects - use CloudFormation console to modify memberships"
            )

        # Ensure role exists with correct policies (idempotent)
        role_arn = self._get_role_arn(target_config)
        policy_arns = self._get_policy_arns(target_config)

        if policy_arns or not role_arn:
            import boto3

            from . import iam

            sts = boto3.client("sts")
            account_id = sts.get_caller_identity()["Account"]

            if not role_arn:
                # No role specified, create default role
                role_name = self._get_role_name(target_config, project_name)
                typer.echo(f"🔧 Ensuring IAM role exists: {role_name}")
                role_arn = iam.create_or_update_project_role(
                    role_name=role_name,
                    policy_arns=policy_arns,
                    account_id=account_id,
                    region=region,
                )
            else:
                # Role specified, ensure policies are attached
                typer.echo(f"🔧 Ensuring policies on existing role: {role_arn}")
                role_arn = iam.create_or_update_project_role(
                    role_name="",  # Not used when role_arn provided
                    policy_arns=policy_arns,
                    account_id=account_id,
                    region=region,
                    role_arn=role_arn,
                )

    def _get_profile_name(self, target_config) -> str:
        """Extract profile name from target configuration."""
        profile_name = target_config.project.profile_name
        if target_config.bootstrap and target_config.project:
            profile_name = profile_name or target_config.project.profile_name

        # If no profile name provided, auto-detect from domain
        if not profile_name:
            from . import datazone

            domain_name = target_config.domain.name
            region = self.config.get("region")

            # Get domain ID
            domain_id = datazone.get_domain_id_by_name(domain_name, region)
            if not domain_id:
                handle_error(f"Domain '{domain_name}' not found")

            # List project profiles
            import boto3

            dz_client = boto3.client("datazone", region_name=region)
            response = dz_client.list_project_profiles(domainIdentifier=domain_id)
            profiles = response.get("items", [])

            if len(profiles) == 0:
                handle_error(
                    f"No project profiles found in domain '{domain_name}'. "
                    f"Please specify 'profileName' in your manifest under targets.{target_config.project.name}.project.profileName"
                )
            elif len(profiles) == 1:
                profile_name = profiles[0]["name"]
                typer.echo(f"✓ Auto-detected project profile: {profile_name}")
            else:
                profile_names = [p["name"] for p in profiles]
                handle_error(
                    f"Multiple project profiles found in domain '{domain_name}': {', '.join(profile_names)}. "
                    f"Please specify one of these profiles using 'profileName' in your manifest under targets.{target_config.project.name}.project.profileName"
                )

        return profile_name

    def _create_project_via_datazone_api(
        self,
        project_name,
        profile_name,
        domain_name,
        region,
        role_arn,
        owners,
        contributors,
    ):
        """Create project using DataZone API directly (for gamma endpoints)."""
        import boto3

        # Get domain ID
        domain_id = datazone.get_domain_id_by_name(domain_name, region)
        if not domain_id:
            handle_error(f"Domain '{domain_name}' not found")
            return False

        # Get profile ID
        dz_client = boto3.client("datazone", region_name=region)
        response = dz_client.list_project_profiles(domainIdentifier=domain_id)
        profile_id = None
        available_profiles = []
        for profile in response.get("items", []):
            available_profiles.append(profile["name"])
            if profile["name"] == profile_name:
                profile_id = profile["id"]
                break

        if not profile_id:
            # Try to use first available profile as default
            if available_profiles:
                default_profile = available_profiles[0]
                typer.echo(
                    f"⚠️ Profile '{profile_name}' not found. Using default profile: '{default_profile}'"
                )
                for profile in response.get("items", []):
                    if profile["name"] == default_profile:
                        profile_id = profile["id"]
                        profile_name = default_profile
                        break

            if not profile_id:
                profiles_list = (
                    ", ".join(available_profiles) if available_profiles else "none"
                )
                handle_error(
                    f"Project profile '{profile_name}' not found. Available profiles: {profiles_list}"
                )
                return False

        # Prepare create project parameters
        params = {
            "domainIdentifier": domain_id,
            "name": project_name,
            "projectProfileId": profile_id,
        }

        # Add customer-provided role if specified
        if role_arn:
            params["customerProvidedRoleConfigs"] = [
                {"roleArn": role_arn, "roleDesignation": "PROJECT_OWNER"}
            ]
            typer.echo(f"✓ Using customer-provided role: {role_arn}")

        try:
            response = dz_client.create_project(**params)
            project_id = response["id"]
            typer.echo(f"✅ Project created: {project_id}")

            # Manage memberships if provided
            if owners or contributors:
                typer.echo("🔧 Managing project memberships...")
                datazone.manage_project_memberships(
                    project_id, domain_id, region, owners, contributors
                )

            return True
        except Exception as e:
            typer.echo(f"❌ Error creating project: {e}")
            return False

    def _get_role_arn(self, target_config) -> Optional[str]:
        """Extract role ARN from target configuration."""
        role_arn = None

        # Check initialization.project.role.arn first
        if target_config.bootstrap and target_config.project:
            init_project = target_config.project
            if hasattr(init_project, "role") and init_project.role:
                if isinstance(init_project.role, dict):
                    role_arn = init_project.role.get("arn")
                elif hasattr(init_project.role, "arn"):
                    role_arn = init_project.role.arn

        # Fallback to target_config.project.role.arn
        if (
            not role_arn
            and hasattr(target_config.project, "role")
            and target_config.project.role
        ):
            if isinstance(target_config.project.role, dict):
                role_arn = target_config.project.role.get("arn")
            elif hasattr(target_config.project.role, "arn"):
                role_arn = target_config.project.role.arn

        # Replace wildcard account ID with current account
        if role_arn and ":*:" in role_arn:
            import boto3

            sts = boto3.client("sts")
            account_id = sts.get_caller_identity()["Account"]
            role_arn = role_arn.replace(":*:", f":{account_id}:")

        return role_arn

    def _get_role_name(self, target_config, project_name: str) -> str:
        """Extract role name from target configuration or generate default."""
        role_name = None

        # Check initialization.project.role.name first
        if target_config.bootstrap and target_config.project:
            init_project = target_config.project
            if hasattr(init_project, "role") and init_project.role:
                if isinstance(init_project.role, dict):
                    role_name = init_project.role.get("name")
                elif hasattr(init_project.role, "name"):
                    role_name = init_project.role.name

        # Fallback to target_config.project.role.name
        if (
            not role_name
            and hasattr(target_config.project, "role")
            and target_config.project.role
        ):
            if isinstance(target_config.project.role, dict):
                role_name = target_config.project.role.get("name")
            elif hasattr(target_config.project.role, "name"):
                role_name = target_config.project.role.name

        # Default to smus-{project_name}-role
        return role_name or f"smus-{project_name}-role"

    def _get_policy_arns(self, target_config) -> List[str]:
        """Extract policy ARNs from target configuration."""
        policy_arns = []

        # Check initialization.project.role.policies first
        if target_config.bootstrap and target_config.project:
            init_project = target_config.project
            if hasattr(init_project, "role") and init_project.role:
                if isinstance(init_project.role, dict):
                    policies = init_project.role.get("policies", [])
                elif hasattr(init_project.role, "policies"):
                    policies = init_project.role.policies
                else:
                    policies = []

                if policies:
                    policy_arns.extend(
                        policies if isinstance(policies, list) else [policies]
                    )

        # Fallback to target_config.project.role.policies
        if (
            not policy_arns
            and hasattr(target_config.project, "role")
            and target_config.project.role
        ):
            if isinstance(target_config.project.role, dict):
                policies = target_config.project.role.get("policies", [])
            elif hasattr(target_config.project.role, "policies"):
                policies = target_config.project.role.policies
            else:
                policies = []

            if policies:
                policy_arns.extend(
                    policies if isinstance(policies, list) else [policies]
                )

        return policy_arns

    def _wait_for_environments(
        self, project_id, domain_id, region, max_wait_seconds=300
    ):
        """Wait for project environments to be fully deployed."""
        import json
        import time

        import boto3

        dz_client = boto3.client("datazone", region_name=region)
        start_time = time.time()

        while time.time() - start_time < max_wait_seconds:
            response = dz_client.get_project(
                domainIdentifier=domain_id, identifier=project_id
            )

            print(
                f"🔍 DEBUG get_project response: {json.dumps(response, indent=2, default=str)}"
            )

            project_status = response.get("projectStatus")
            env_deployment = response.get("environmentDeploymentDetails", {})
            overall_status = env_deployment.get("overallDeploymentStatus")

            typer.echo(
                f"  Project status: {project_status}, Environment deployment: {overall_status}"
            )

            if project_status in ["UPDATE_FAILED", "DELETE_FAILED"]:
                typer.echo(f"  ❌ Project status failed: {project_status}")
                failure_reasons = response.get("failureReasons", [])
                if failure_reasons:
                    for reason in failure_reasons:
                        typer.echo(f"    Failure: {reason}")
                return False

            # Check environment deployment status
            if overall_status == "SUCCESSFUL":
                typer.echo(f"  ✅ Environment deployment: {overall_status}")

                # Verify project has connections
                typer.echo("  Verifying project connections...")
                connections_response = dz_client.list_connections(
                    domainIdentifier=domain_id, projectIdentifier=project_id
                )
                connections = connections_response.get("items", [])
                print(f"🔍 DEBUG: Found {len(connections)} connections")

                if not connections:
                    typer.echo(
                        "  ❌ Project has no connections - environments not ready"
                    )
                    return False

                typer.echo(f"  ✅ Project has {len(connections)} connections")
                return True
            elif overall_status == "FAILED":
                typer.echo("  ❌ Environment deployment failed")
                env_failures = env_deployment.get("environmentFailureReasons", {})
                if env_failures:
                    for env_id, reason in env_failures.items():
                        typer.echo(f"    Environment {env_id}: {reason}")
                return False
            elif overall_status in ["IN_PROGRESS", "PENDING_DEPLOYMENT"]:
                time.sleep(10)
            else:
                # No deployment details yet or unknown status
                time.sleep(10)

        typer.echo(
            f"⚠️  Timeout waiting for environment deployment after {max_wait_seconds}s"
        )
        return False

    def _extract_user_parameters(
        self, target_config, stage_name: str
    ) -> Optional[List]:
        """Extract user parameters from target configuration."""
        print(f"🔍 DEBUG: Extracting user parameters for target: {stage_name}")

        if not (target_config.bootstrap and target_config.project):
            print(f"🔍 DEBUG: No initialization.project found for target: {stage_name}")
            return None

        # Parse userParameters directly from YAML since dataclass parsing doesn't handle nested structure
        import yaml

        with open(self.manifest._file_path, "r") as f:
            pipeline_data = yaml.safe_load(f)

        target_data = pipeline_data.get("targets", {}).get(stage_name, {})
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
        from smus_cicd.application.application_manifest import (
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
        self,
        stage_name: str,
        target_config,
        project_info: Dict[str, Any],
        domain_name: str,
        region: str,
    ) -> bool:
        """Ensure required environments exist in the project."""
        print(f"🔍 DEBUG: _ensure_environments_exist called for target: {stage_name}")
        print(
            f"🔍 DEBUG: target_config.bootstrap exists: {target_config.bootstrap is not None}"
        )

        if target_config.bootstrap:
            print(
                f"🔍 DEBUG: target_config.bootstrap type: {type(target_config.bootstrap)}"
            )
            print(
                f"🔍 DEBUG: target_config.bootstrap attributes: {dir(target_config.bootstrap)}"
            )
            print(
                f"🔍 DEBUG: hasattr environments: {hasattr(target_config.bootstrap, 'environments')}"
            )
            if hasattr(target_config.bootstrap, "environments"):
                print(
                    f"🔍 DEBUG: environments value: {target_config.bootstrap.actions}"
                )

        if not (
            target_config.bootstrap and hasattr(target_config.bootstrap, "environments")
        ):
            print(f"🔍 DEBUG: No environments specified for target: {stage_name}")
            # Still create connections even if no environments specified
            if target_config.bootstrap:
                project_id = project_info.get("project_id")
                domain_id = datazone.get_domain_id_by_name(domain_name, region)
                if project_id and domain_id:
                    self._ensure_manifest_connections(
                        target_config, domain_id, project_id, region
                    )
            return True  # No environments to create is success

        project_id = project_info.get("project_id")

        # Resolve domain_id the same way _create_new_project does
        domain_id = datazone.get_domain_id_by_name(domain_name, region)

        print(f"🔍 DEBUG: Resolved project_id: {project_id}, domain_id: {domain_id}")

        if not project_id or not domain_id:
            print(
                f"🔍 DEBUG: Missing project_id or domain_id: {project_id}, {domain_id}"
            )
            return False

        # Ensure connections exist (idempotent)
        self._ensure_manifest_connections(target_config, domain_id, project_id, region)

        if not project_id or not domain_id:
            print(
                f"🔍 DEBUG: Missing project_id or domain_id: {project_id}, {domain_id}"
            )
            return False

        print(f"🔍 DEBUG: Checking environments for project {project_id}")

        # Get existing environments in the project
        try:
            import boto3

            datazone_client = boto3.client("datazone", region_name=region)

            existing_envs_response = datazone_client.list_environments(
                domainIdentifier=domain_id, projectIdentifier=project_id
            )
            existing_env_names = [
                env["name"] for env in existing_envs_response.get("items", [])
            ]
            print(f"🔍 DEBUG: Existing environments: {existing_env_names}")

        except Exception as e:
            print(f"🔍 DEBUG: Error listing environments: {e}")
            raise Exception(
                f"Failed to list environments for project {project_id}: {e}"
            )

        # Check each required environment
        all_environments_ready = True
        for env_config in target_config.bootstrap.actions:
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
            success = self._create_environment(domain_id, project_id, env_name, region)

            if success:
                print(f"✅ Environment '{env_name}' created successfully")
                # Check if this is a workflow environment and validate MWAA
                if "workflow" in env_name.lower() or "mwaa" in env_name.lower():
                    self._validate_mwaa_environment(project_id, domain_id, region)
            else:
                print(f"❌ Failed to create environment: {env_name}")
                all_environments_ready = False

        return all_environments_ready

    def _create_environment(
        self, domain_id: str, project_id: str, env_name: str, region: str
    ) -> bool:
        """Create a DataZone environment."""
        try:
            import boto3

            datazone_client = boto3.client("datazone", region_name=region)

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
            raise Exception(
                f"Failed to create environment for project {project_id}: {e}"
            )

    def _validate_mwaa_environment(
        self, project_id: str, domain_id: str, region: str
    ) -> None:
        """Validate MWAA environment is available."""
        try:
            import time

            import boto3

            # Wait a bit for environment to be ready
            time.sleep(5)

            datazone_client = boto3.client("datazone", region_name=region)

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

    def _ensure_manifest_connections(
        self, target_config, domain_id: str, project_id: str, region: str
    ) -> None:
        """Ensure connections from manifest exist (idempotent). Updates existing connections by recreating them."""
        if not (
            target_config.bootstrap
            and hasattr(target_config.bootstrap, "connections")
            and target_config.bootstrap.actions
        ):
            return

        import boto3

        from .connection_creator import ConnectionCreator

        # Get existing connections
        datazone_client = boto3.client("datazone", region_name=region)
        existing_conns = {}
        try:
            response = datazone_client.list_connections(
                domainIdentifier=domain_id, projectIdentifier=project_id
            )
            for conn in response.get("items", []):
                existing_conns[conn["name"]] = conn["connectionId"]
        except Exception as e:
            print(f"⚠️  Could not list existing connections: {e}")

        # Get environment ID (use first available environment)
        try:
            envs_response = datazone_client.list_environments(
                domainIdentifier=domain_id, projectIdentifier=project_id
            )
            environments = envs_response.get("items", [])
            if not environments:
                print("⚠️  No environments found - cannot create connections")
                return
            environment_id = environments[0]["id"]
        except Exception as e:
            print(f"⚠️  Could not get environment ID: {e}")
            return

        creator = ConnectionCreator(domain_id, region)

        for conn_config in target_config.bootstrap.actions:
            full_name = f"project.{conn_config.name}.{conn_config.type.lower()}"

            # If connection exists, delete it first to update
            if full_name in existing_conns:
                try:
                    print(f"🔄 Updating connection: {full_name} (deleting old)")
                    datazone_client.delete_connection(
                        domainIdentifier=domain_id, identifier=existing_conns[full_name]
                    )
                    print(f"✅ Deleted old connection: {full_name}")
                except Exception as e:
                    print(f"⚠️  Failed to delete connection {full_name}: {e}")
                    continue

            try:
                print(f"🔗 Creating connection: {full_name} ({conn_config.type})")
                conn_id = creator.create_from_config(
                    environment_id=environment_id,
                    connection_config=conn_config,
                )
                print(f"✅ Connection created: {full_name} ({conn_id})")
            except Exception as e:
                print(f"⚠️  Failed to create connection {full_name}: {e}")

    def _extract_memberships(self, target_config) -> tuple[List[str], List[str]]:
        """Extract owners and contributors from target configuration."""
        owners = []
        contributors = []

        if target_config.bootstrap and target_config.project:
            owners = getattr(target_config.project, "owners", [])
            contributors = getattr(target_config.project, "contributors", [])
        else:
            owners = target_config.project.owners or []
            contributors = target_config.project.contributors or []

        # Replace wildcard account ID in IAM ARNs
        import boto3

        sts = boto3.client("sts")
        account_id = sts.get_caller_identity()["Account"]

        owners = [
            owner.replace(":*:", f":{account_id}:") if ":*:" in owner else owner
            for owner in owners
        ]
        contributors = [
            contrib.replace(":*:", f":{account_id}:") if ":*:" in contrib else contrib
            for contrib in contributors
        ]

        return owners, contributors
