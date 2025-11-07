"""Centralized pipeline manifest parsing and data model."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
class BundleConfig:
    """Bundle configuration."""

    bundles_directory: str = "./bundles"
    storage: List[Dict[str, Any]] = field(
        default_factory=list
    )  # Unified storage (includes workflows)
    git: List[Dict[str, Any]] = field(default_factory=list)  # Changed from dict to list
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
class BundleTargetConfig:
    """Bundle target configuration."""

    storage: List[Dict[str, str]] = field(default_factory=list)  # Changed to list
    git: List[Dict[str, str]] = field(default_factory=list)  # Changed to list
    catalog: Optional[Dict[str, Any]] = None


@dataclass
class TestConfig:
    """Test configuration."""

    folder: str


@dataclass
class TargetConfig:
    """Target configuration."""

    project: ProjectConfig
    domain: DomainConfig
    stage: str
    initialization: Optional[InitializationConfig] = None
    bundle_target_configuration: Optional[BundleTargetConfig] = None
    tests: Optional[TestConfig] = None
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
class PipelineManifest:
    """Complete pipeline manifest data model."""

    pipeline_name: str
    bundle: BundleConfig
    targets: Dict[str, TargetConfig]
    workflows: List[WorkflowConfig] = field(default_factory=list)
    monitoring: Optional[MonitoringConfig] = None
    _file_path: Optional[str] = field(default=None, init=False)

    @classmethod
    def from_file(cls, manifest_file: str) -> "PipelineManifest":
        """Load pipeline manifest from YAML file with validation."""
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
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineManifest":
        """Create pipeline manifest from dictionary."""
        # Validate required top-level fields
        if not data.get("pipelineName"):
            raise ValueError("pipelineName is required and cannot be empty")

        if "targets" not in data:
            raise ValueError("targets configuration is required")

        targets_data = data.get("targets", {})
        if not targets_data:
            raise ValueError("at least one target must be defined")

        # Parse bundle configuration
        bundle_data = data.get("bundle", {})

        # Parse catalog configuration
        catalog = None
        catalog_data = bundle_data.get("catalog")
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

        bundle = BundleConfig(
            bundles_directory=bundle_data.get("bundlesDirectory", "./bundles"),
            storage=bundle_data.get("storage", []),
            git=bundle_data.get("git", []),
            catalog=catalog,
        )

        # Parse targets
        targets = {}
        for target_name, target_data in targets_data.items():
            if not target_data:
                raise ValueError(
                    f"target '{target_name}' configuration cannot be empty"
                )

            # Parse domain config
            domain_data = target_data.get("domain")
            if not domain_data:
                raise ValueError(
                    f"target '{target_name}' must have a domain configuration"
                )

            domain = DomainConfig(
                region=domain_data.get("region", ""),
                name=domain_data.get("name"),
                tags=domain_data.get("tags"),
            )

            if not domain.region.strip():
                raise ValueError(
                    f"target '{target_name}' domain.region is required and cannot be empty"
                )

            # Parse project config
            project_data = target_data.get("project")
            if not project_data:
                raise ValueError(
                    f"target '{target_name}' must have a project configuration"
                )

            if isinstance(project_data, str):
                # Handle simple string format: project: "project-name"
                if not project_data.strip():
                    raise ValueError(
                        f"target '{target_name}' project name cannot be empty"
                    )
                project = ProjectConfig(name=project_data)
            else:
                # Handle object format
                project_name = project_data.get("name", "")
                if not project_name.strip():
                    raise ValueError(
                        f"target '{target_name}' project.name is required and cannot be empty"
                    )

                project = ProjectConfig(
                    name=project_name,
                    create=project_data.get("create", False),
                    profile_name=project_data.get("profileName"),
                    owners=project_data.get("owners", []),
                    contributors=project_data.get("contributors", []),
                )

            # Parse initialization config
            initialization = None
            init_data = target_data.get("initialization")
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

                initialization = InitializationConfig(
                    project=init_project,
                    domain=init_domain,
                    environments=init_data.get("environments", []),
                    connections=connections,
                )

            # Parse bundle target configuration
            bundle_target_config = None
            btc_data = target_data.get("bundle_target_configuration")
            if btc_data:
                bundle_target_config = BundleTargetConfig(
                    storage=btc_data.get("storage", []),
                    git=btc_data.get("git", []),
                    catalog=btc_data.get("catalog"),
                )

            # Parse stage - derive from target name if not provided
            stage = target_data.get("stage")
            if not stage:
                # Derive stage from target name
                stage = target_name.upper()

            # Parse tests configuration
            tests = None
            tests_data = target_data.get("tests")
            if tests_data:
                tests = TestConfig(folder=tests_data.get("folder"))

            targets[target_name] = TargetConfig(
                project=project,
                domain=domain,
                stage=stage,
                initialization=initialization,
                bundle_target_configuration=bundle_target_config,
                tests=tests,
                environment_variables=target_data.get("environment_variables"),
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
            pipeline_name=data.get("pipelineName", ""),
            bundle=bundle,
            targets=targets,
            workflows=workflows,
            monitoring=monitoring,
        )

    def get_target(self, target_name: str) -> Optional[TargetConfig]:
        """Get target configuration by name."""
        return self.targets.get(target_name)

    def get_workflows_for_target(self, target_name: str) -> List[WorkflowConfig]:
        """Get workflows that should be triggered for a target."""
        # For now, return all workflows. Could be enhanced to filter by target
        return self.workflows
