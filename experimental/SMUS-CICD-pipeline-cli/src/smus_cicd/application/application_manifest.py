"""Centralized bundle manifest parsing and data model."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..bootstrap.models import BootstrapAction, BootstrapConfig


@dataclass
class TestConfig:
    """Test configuration."""

    folder: str


@dataclass
class DomainConfig:
    """Domain configuration."""

    region: str
    name: Optional[str] = None
    tags: Optional[Dict[str, str]] = None


@dataclass
class AssetSearchConfig:
    """Asset search configuration."""

    assetType: Optional[str] = None
    identifier: str = ""


@dataclass
class AssetSelectorConfig:
    """Asset selector configuration."""

    assetId: Optional[str] = None
    search: Optional[AssetSearchConfig] = None


@dataclass
class AssetConfig:
    """Asset configuration for catalog access."""

    selector: AssetSelectorConfig
    permission: str = "READ"
    requestReason: str = "Required for pipeline deployment"


@dataclass
class CatalogConfig:
    """Catalog configuration for bundle."""

    connectionName: Optional[str] = None
    assets: List[AssetConfig] = field(default_factory=list)


@dataclass
class StorageConfig:
    """Storage configuration."""

    name: str
    connectionName: str
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    targetDirectory: Optional[str] = None


@dataclass
class GitConfig:
    """Git repository configuration."""

    repository: str
    url: str
    branch: str = "main"
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


@dataclass
class QuickSightDashboardConfig:
    """QuickSight dashboard configuration."""

    dashboardId: str
    source: str = "export"  # export or bundle
    overrideParameters: Dict[str, Any] = field(default_factory=dict)
    permissions: List[Dict[str, str]] = field(default_factory=list)
    owners: List[str] = field(default_factory=list)
    viewers: List[str] = field(default_factory=list)


@dataclass
class ContentConfig:
    """Application content configuration."""

    storage: List[StorageConfig] = field(default_factory=list)
    git: List[GitConfig] = field(default_factory=list)
    catalog: Optional[CatalogConfig] = None
    quicksight: List[QuickSightDashboardConfig] = field(default_factory=list)
    workflows: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class UserParameter:
    """User parameter for project configuration."""

    name: str
    value: str


@dataclass
class EnvironmentUserParameters:
    """Environment configuration user parameters."""

    EnvironmentConfigurationName: str
    parameters: List[UserParameter] = field(default_factory=list)


@dataclass
class ProjectConfig:
    """Project configuration."""

    name: str
    create: bool = False
    profile_name: Optional[str] = None
    owners: List[str] = field(default_factory=list)
    contributors: List[str] = field(default_factory=list)
    user_parameters: List[UserParameter] = field(default_factory=list)
    userParameters: List[EnvironmentUserParameters] = field(default_factory=list)
    role: Optional[Dict[str, Any]] = None


@dataclass
class DeploymentConfiguration:
    """Deployment configuration for a stage."""

    storage: List[StorageConfig] = field(default_factory=list)
    git: List[GitConfig] = field(default_factory=list)
    catalog: Optional[Dict[str, Any]] = None
    quicksight: Optional[Dict[str, Any]] = None


@dataclass
class StageConfig:
    """Stage configuration."""

    project: ProjectConfig
    domain: DomainConfig
    stage: str
    bootstrap: Optional["BootstrapConfig"] = None
    deployment_configuration: Optional[DeploymentConfiguration] = None
    environment_variables: Optional[Dict[str, Any]] = None
    quicksight: List[QuickSightDashboardConfig] = field(default_factory=list)


@dataclass
class EventBridgeConfig:
    """EventBridge monitoring configuration."""

    enabled: bool = True
    eventBusName: str = "default"
    includeMetadata: bool = True


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""

    eventbridge: Optional[EventBridgeConfig] = None


@dataclass
class ApplicationManifest:
    """Complete application manifest data model."""

    application_name: str
    content: ContentConfig
    stages: Dict[str, StageConfig]
    tests: Optional[TestConfig] = None
    monitoring: Optional[MonitoringConfig] = None
    _file_path: Optional[str] = field(default=None, init=False)

    @classmethod
    def from_file(cls, manifest_file: str) -> "ApplicationManifest":
        """Load bundle manifest from YAML file with validation."""
        from .validation import validate_manifest_file

        # Validate manifest file (YAML syntax + schema)
        is_valid, errors, manifest_data = validate_manifest_file(manifest_file)
        if not is_valid:
            error_msg = (
                f"Manifest validation failed for {manifest_file}:\n"
                + "\n".join(f"  - {error}" for error in errors)
            )
            raise ValueError(error_msg)

        manifest = cls.from_dict(manifest_data)
        manifest._file_path = manifest_file
        return manifest

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApplicationManifest":
        """Create application manifest from dictionary."""
        # Validate required top-level fields
        if not data.get("applicationName"):
            raise ValueError("applicationName is required and cannot be empty")

        if "stages" not in data:
            raise ValueError("stages configuration is required")

        stages_data = data.get("stages", {})
        if not stages_data:
            raise ValueError("at least one stage must be defined")

        # Parse content configuration
        content_data = data.get("content", {})

        # Parse catalog configuration
        catalog = None
        catalog_data = content_data.get("catalog")
        if catalog_data:
            assets = []
            for asset_data in catalog_data.get("assets", []):
                selector_data = asset_data.get("selector", {})

                # Parse search config if present
                search = None
                search_data = selector_data.get("search")
                if search_data:
                    search = AssetSearchConfig(
                        assetType=search_data.get("assetType"),
                        identifier=search_data.get("identifier", ""),
                    )

                selector = AssetSelectorConfig(
                    assetId=selector_data.get("assetId"), search=search
                )

                asset = AssetConfig(
                    selector=selector,
                    permission=asset_data.get("permission", "READ"),
                    requestReason=asset_data.get(
                        "requestReason", "Required for pipeline deployment"
                    ),
                )
                assets.append(asset)

            catalog = CatalogConfig(
                connectionName=catalog_data.get("connectionName"), assets=assets
            )

        # Parse storage configs
        storage_configs = []
        for storage_data in content_data.get("storage", []):
            storage_configs.append(
                StorageConfig(
                    name=storage_data.get("name", ""),
                    connectionName=storage_data.get("connectionName", ""),
                    include=storage_data.get("include", []),
                    exclude=storage_data.get("exclude", []),
                    targetDirectory=storage_data.get("targetDirectory"),
                )
            )

        # Parse git configs
        git_configs = []
        for git_data in content_data.get("git", []):
            git_configs.append(
                GitConfig(
                    repository=git_data.get("repository", ""),
                    url=git_data.get("url", ""),
                    branch=git_data.get("branch", "main"),
                    include=git_data.get("include", []),
                    exclude=git_data.get("exclude", []),
                )
            )

        # Parse QuickSight dashboards
        quicksight_dashboards = []
        for qs_data in content_data.get("quicksight", []):
            quicksight_dashboards.append(
                QuickSightDashboardConfig(
                    dashboardId=qs_data.get("dashboardId", ""),
                    source=qs_data.get("source", "export"),
                    overrideParameters=qs_data.get("overrideParameters", {}),
                    permissions=qs_data.get("permissions", []),
                    owners=qs_data.get("owners", []),
                    viewers=qs_data.get("viewers", []),
                )
            )

        # Parse workflows
        workflows = content_data.get("workflows", [])

        content = ContentConfig(
            storage=storage_configs,
            git=git_configs,
            catalog=catalog,
            quicksight=quicksight_dashboards,
            workflows=workflows,
        )

        # Parse tests
        tests = None
        tests_data = data.get("tests")
        if tests_data:
            tests = TestConfig(folder=tests_data.get("folder"))

        # Parse stages
        stages = {}
        for stage_name, stage_data in stages_data.items():
            if not stage_data:
                raise ValueError(f"stage '{stage_name}' configuration cannot be empty")

            # Parse domain config
            domain_data = stage_data.get("domain")
            if not domain_data:
                raise ValueError(
                    f"stage '{stage_name}' must have a domain configuration"
                )

            domain = DomainConfig(
                region=domain_data.get("region", ""),
                name=domain_data.get("name"),
                tags=domain_data.get("tags"),
            )

            if not domain.region.strip():
                raise ValueError(
                    f"stage '{stage_name}' domain.region is required and cannot be empty"
                )

            # Parse project config
            project_data = stage_data.get("project")
            if not project_data:
                raise ValueError(
                    f"stage '{stage_name}' must have a project configuration"
                )

            if isinstance(project_data, str):
                # Handle simple string format: project: "project-name"
                if not project_data.strip():
                    raise ValueError(
                        f"stage '{stage_name}' project name cannot be empty"
                    )
                project = ProjectConfig(name=project_data)
            else:
                # Handle object format
                project_name = project_data.get("name", "")
                if not project_name.strip():
                    raise ValueError(
                        f"stage '{stage_name}' project.name is required and cannot be empty"
                    )

                project = ProjectConfig(
                    name=project_name,
                    create=project_data.get("create", False),
                    profile_name=project_data.get("profileName"),
                    owners=project_data.get("owners", []),
                    contributors=project_data.get("contributors", []),
                    role=project_data.get("role"),
                )

            # Parse bootstrap config
            stage_bootstrap = None
            bootstrap_data = stage_data.get("bootstrap")
            if bootstrap_data:
                actions = []
                for action_data in bootstrap_data.get("actions", []):
                    # Extract type and all other fields as parameters
                    action_type = action_data.get("type")
                    if not action_type:
                        raise ValueError("Bootstrap action must have 'type' field")

                    # All fields except 'type' go into parameters
                    parameters = {k: v for k, v in action_data.items() if k != "type"}

                    actions.append(
                        BootstrapAction(type=action_type, parameters=parameters)
                    )

                stage_bootstrap = BootstrapConfig(actions=actions)

            # Parse bundle target configuration
            deployment_config = None
            btc_data = stage_data.get("deployment_configuration")
            if btc_data:
                # Parse storage configs
                storage_configs = []
                for storage_data in btc_data.get("storage", []):
                    storage_configs.append(
                        StorageConfig(
                            name=storage_data.get("name", ""),
                            connectionName=storage_data.get("connectionName", ""),
                            include=storage_data.get("include", []),
                            exclude=storage_data.get("exclude", []),
                            targetDirectory=storage_data.get("targetDirectory"),
                        )
                    )

                # Parse git configs
                git_configs = []
                for git_data in btc_data.get("git", []):
                    git_configs.append(
                        GitConfig(
                            repository=git_data.get("repository", ""),
                            url=git_data.get("url", ""),
                            branch=git_data.get("branch", "main"),
                            include=git_data.get("include", []),
                            exclude=git_data.get("exclude", []),
                        )
                    )

                deployment_config = DeploymentConfiguration(
                    storage=storage_configs,
                    git=git_configs,
                    catalog=btc_data.get("catalog"),
                    quicksight=btc_data.get("quicksight"),
                )

            # Parse stage - derive from target name if not provided
            stage = stage_data.get("stage")
            if not stage:
                # Derive stage from target name
                stage = stage_name.upper()

            # Parse stage-specific QuickSight dashboards
            stage_quicksight = []
            for qs_data in stage_data.get("quicksight", []):
                stage_quicksight.append(
                    QuickSightDashboardConfig(
                        dashboardId=qs_data.get("dashboardId", ""),
                        source=qs_data.get("source", "export"),
                        overrideParameters=qs_data.get("overrideParameters", {}),
                        permissions=qs_data.get("permissions", []),
                        owners=qs_data.get("owners", []),
                        viewers=qs_data.get("viewers", []),
                    )
                )

            stages[stage_name] = StageConfig(
                project=project,
                domain=domain,
                stage=stage,
                bootstrap=stage_bootstrap,
                deployment_configuration=deployment_config,
                environment_variables=stage_data.get("environment_variables"),
                quicksight=stage_quicksight,
            )

        # Parse monitoring configuration
        monitoring = None
        monitoring_data = data.get("monitoring")
        if monitoring_data:
            eventbridge = None
            eventbridge_data = monitoring_data.get("eventbridge")
            if eventbridge_data is not None:
                eventbridge = EventBridgeConfig(
                    enabled=eventbridge_data.get("enabled", True),
                    eventBusName=eventbridge_data.get("eventBusName", "default"),
                    includeMetadata=eventbridge_data.get("includeMetadata", True),
                )
            monitoring = MonitoringConfig(eventbridge=eventbridge)

        return cls(
            application_name=data.get("applicationName", ""),
            content=content,
            stages=stages,
            tests=tests,
            monitoring=monitoring,
        )

    def get_stage(self, stage_name: str) -> Optional[StageConfig]:
        """Get stage configuration by name."""
        return self.stages.get(stage_name)
