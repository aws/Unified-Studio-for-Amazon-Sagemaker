"""Centralized bundle manifest parsing and data model."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InitializationAction:
    """Single initialization action (workflow, event, cloudformation)."""

    type: str  # workflow, event, cloudformation
    # Workflow fields
    workflowName: Optional[str] = None
    connectionName: Optional[str] = None
    engine: Optional[str] = None
    triggerPostDeployment: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)
    logging: Optional[str] = None
    # Event fields
    eventBridgeRule: Optional[str] = None
    # CloudFormation fields
    stackName: Optional[str] = None
    templatePath: Optional[str] = None


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


@dataclass
class GitConfig:
    """Git repository configuration."""

    repository: str
    url: str
    branch: str = "main"
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


@dataclass
class ContentConfig:
    """Application content configuration."""

    storage: List[StorageConfig] = field(default_factory=list)
    git: List[GitConfig] = field(default_factory=list)
    catalog: Optional[CatalogConfig] = None


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
class EnvironmentConfig:
    """Environment configuration."""

    environment_configuration_name: str
    user_parameters: List[UserParameter] = field(default_factory=list)


@dataclass
class DomainInitConfig:
    """Domain initialization configuration."""

    name: str
    region: str
    create: bool = False


@dataclass
class ConnectionConfig:
    """DataZone connection configuration."""

    name: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InitializationConfig:
    """Initialization configuration."""

    project: Optional[ProjectConfig] = None
    domain: Optional[DomainInitConfig] = None
    environments: List[EnvironmentConfig] = field(default_factory=list)
    connections: List[ConnectionConfig] = field(default_factory=list)


@dataclass
class DeploymentConfiguration:
    """Deployment configuration for a stage."""

    storage: List[StorageConfig] = field(default_factory=list)
    git: List[GitConfig] = field(default_factory=list)
    catalog: Optional[Dict[str, Any]] = None


@dataclass
class StageConfig:
    """Stage configuration."""

    project: ProjectConfig
    domain: DomainConfig
    stage: str
    initialization: Optional[InitializationConfig] = None
    deployment_configuration: Optional[DeploymentConfiguration] = None
    environment_variables: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowConfig:
    """Workflow configuration."""

    workflow_name: str
    connection_name: str
    engine: str = "MWAA"
    parameters: Dict[str, Any] = field(default_factory=dict)


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
    initialization: List[InitializationAction] = field(default_factory=list)
    tests: Optional[TestConfig] = None
    workflows: List[WorkflowConfig] = field(default_factory=list)
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

        content = ContentConfig(
            storage=storage_configs,
            git=git_configs,
            catalog=catalog,
        )

        # Parse initialization actions
        initialization = []
        for action_data in data.get("initialization", []):
            initialization.append(InitializationAction(**action_data))

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
                )

            # Parse initialization config
            stage_initialization = None
            init_data = stage_data.get("initialization")
            if init_data:
                init_project = None
                init_domain = None
                if "project" in init_data:
                    proj_data = init_data["project"]
                    init_project = ProjectConfig(
                        name=proj_data.get("name", project.name),
                        create=proj_data.get("create", False),
                        profile_name=proj_data.get("profileName"),
                        owners=proj_data.get("owners", []),
                        contributors=proj_data.get("contributors", []),
                        role=proj_data.get("role"),
                    )

                if "domain" in init_data:
                    domain_data = init_data["domain"]
                    init_domain = DomainInitConfig(
                        name=domain_data.get("name", domain.name),
                        region=domain_data.get("region", domain.region),
                        create=domain_data.get("create", False),
                    )

                # Parse connections
                connections = []
                connections_data = init_data.get("connections", [])
                for conn_data in connections_data:
                    connection = ConnectionConfig(
                        name=conn_data.get("name", ""),
                        type=conn_data.get("type", ""),
                        properties=conn_data.get("properties", {}),
                    )
                    connections.append(connection)

                # Parse environments
                environments = []
                for env_data in init_data.get("environments", []):
                    user_params = []
                    for param_data in env_data.get("user_parameters", []):
                        user_params.append(
                            UserParameter(
                                name=param_data.get("name", ""),
                                value=param_data.get("value", ""),
                            )
                        )
                    environments.append(
                        EnvironmentConfig(
                            environment_configuration_name=env_data.get("environment_configuration_name", ""),
                            user_parameters=user_params,
                        )
                    )

                stage_initialization = InitializationConfig(
                    project=init_project,
                    domain=init_domain,
                    environments=environments,
                    connections=connections,
                )

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
                )

            # Parse stage - derive from target name if not provided
            stage = stage_data.get("stage")
            if not stage:
                # Derive stage from target name
                stage = stage_name.upper()

            stages[stage_name] = StageConfig(
                project=project,
                domain=domain,
                stage=stage,
                initialization=stage_initialization,
                deployment_configuration=deployment_config,
                environment_variables=stage_data.get("environment_variables"),
            )

        # Parse workflows
        workflows = []
        workflows_data = data.get("workflows", [])
        for i, workflow_data in enumerate(workflows_data):
            workflow_name = workflow_data.get("workflowName", "")
            if not workflow_name.strip():
                raise ValueError(
                    f"workflow[{i}].workflowName is required and cannot be empty"
                )

            connection_name = workflow_data.get("connectionName", "")
            engine = workflow_data.get("engine", "MWAA")

            # connectionName is required for MWAA but optional for airflow-serverless
            if engine != "airflow-serverless" and not connection_name.strip():
                raise ValueError(
                    f"workflow[{i}].connectionName is required and cannot be empty for {engine} engine"
                )

            workflow = WorkflowConfig(
                workflow_name=workflow_name,
                connection_name=connection_name,
                engine=engine,
                parameters=workflow_data.get("parameters", {}),
            )
            workflows.append(workflow)

        # Also extract workflows from initialization actions
        for action in initialization:
            if action.type == "workflow":
                workflow = WorkflowConfig(
                    workflow_name=action.workflowName,
                    connection_name=action.connectionName or "",
                    engine=action.engine or "MWAA",
                    parameters={},
                )
                workflows.append(workflow)

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
            initialization=initialization,
            tests=tests,
            workflows=workflows,
            monitoring=monitoring,
        )

    def get_stage(self, stage_name: str) -> Optional[StageConfig]:
        """Get stage configuration by name."""
        return self.stages.get(stage_name)

    def get_workflows_for_stage(self, stage_name: str) -> List[WorkflowConfig]:
        """Get workflows that should be triggered for a stage."""
        # Return workflow-type initialization actions
        return [
            WorkflowConfig(
                workflow_name=action.workflowName,
                connection_name=action.connectionName or "",
                engine=action.engine or "MWAA",
                parameters=action.parameters,
            )
            for action in self.initialization
            if action.type == "workflow" and action.workflowName
        ]
