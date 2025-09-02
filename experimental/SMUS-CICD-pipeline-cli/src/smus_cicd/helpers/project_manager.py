"""Project management utilities for SMUS CLI."""

import typer
from typing import Dict, Any, List, Optional
from . import datazone, cloudformation
from .utils import get_datazone_project_info
from .error_handler import handle_error, handle_success, handle_info


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
            # Project exists - no need to create anything
            handle_success(f"✅ Project '{project_name}' already exists")
            self._update_existing_project(target_name, target_config, project_name)
            return project_info

        # Project doesn't exist - check if we should create it
        if self._should_create_project(target_config):
            return self._create_new_project(target_name, target_config, project_name)

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
        if not (target_config.initialization and target_config.initialization.project):
            return None

        # Parse userParameters directly from YAML since dataclass parsing doesn't handle nested structure
        import yaml

        with open(self.manifest._file_path, "r") as f:
            pipeline_data = yaml.safe_load(f)

        target_data = pipeline_data.get("targets", {}).get(target_name, {})
        init_data = target_data.get("initialization", {})
        project_data = init_data.get("project", {})
        yaml_user_params = project_data.get("userParameters", [])

        if not yaml_user_params:
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
