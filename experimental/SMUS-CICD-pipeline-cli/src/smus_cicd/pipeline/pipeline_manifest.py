"""Centralized pipeline manifest parsing and data model."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DomainConfig:
    """Domain configuration."""

    name: str
    region: str


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
    workflow: List[Dict[str, Any]] = field(default_factory=list)
    storage: List[Dict[str, Any]] = field(default_factory=list)
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
    profile_name: str = "All capabilities"
    owners: List[str] = field(default_factory=list)
    contributors: List[str] = field(default_factory=list)
    user_parameters: List[UserParameter] = field(default_factory=list)
    userParameters: List[EnvironmentUserParameters] = field(default_factory=list)


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
class InitializationConfig:
    """Initialization configuration."""

    project: Optional[ProjectConfig] = None
    domain: Optional[DomainInitConfig] = None
    environments: List[EnvironmentConfig] = field(default_factory=list)


@dataclass
@dataclass
class BundleTargetConfig:
    """Bundle target configuration."""

    storage: Optional[Dict[str, str]] = None
    workflows: Optional[Dict[str, str]] = None
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
    default: bool = False
    initialization: Optional[InitializationConfig] = None
    bundle_target_configuration: Optional[BundleTargetConfig] = None
    tests: Optional[TestConfig] = None
    environment_variables: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowConfig:
    """Workflow configuration."""

    workflow_name: str
    connection_name: str
    logging: str = "none"
    engine: str = "Workflows"
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineManifest:
    """Complete pipeline manifest data model."""

    pipeline_name: str
    bundle: BundleConfig
    targets: Dict[str, TargetConfig]
    workflows: List[WorkflowConfig] = field(default_factory=list)
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
            workflow=bundle_data.get("workflow", []),
            storage=bundle_data.get("storage", []),
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
                name=domain_data.get("name", ""), region=domain_data.get("region", "")
            )

            if not domain.name.strip():
                raise ValueError(
                    f"target '{target_name}' domain.name is required and cannot be empty"
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
                    profile_name=project_data.get("profileName", "All capabilities"),
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
                        profile_name=proj_data.get("profileName", "All capabilities"),
                        owners=proj_data.get("owners", []),
                        contributors=proj_data.get("contributors", []),
                    )

                if "domain" in init_data:
                    domain_data = init_data["domain"]
                    init_domain = DomainInitConfig(
                        name=domain_data.get("name", domain.name),
                        region=domain_data.get("region", domain.region),
                        create=domain_data.get("create", False),
                    )

                initialization = InitializationConfig(
                    project=init_project,
                    domain=init_domain,
                    environments=init_data.get("environments", []),
                )

            # Parse bundle target configuration
            bundle_target_config = None
            btc_data = target_data.get("bundle_target_configuration")
            if btc_data:
                bundle_target_config = BundleTargetConfig(
                    storage=btc_data.get("storage"),
                    workflows=btc_data.get("workflows"),
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
                default=target_data.get("default", False),
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
                logging=workflow_data.get("logging", "none"),
                engine=engine,
                parameters=workflow_data.get("parameters", {}),
            )
            workflows.append(workflow)

        return cls(
            pipeline_name=data.get("pipelineName", ""),
            bundle=bundle,
            targets=targets,
            workflows=workflows,
        )

    def get_default_target(self) -> Optional[str]:
        """Get the default target name."""
        for target_name, target_config in self.targets.items():
            if target_config.default:
                return target_name
        return None

    def get_target(self, target_name: str) -> Optional[TargetConfig]:
        """Get target configuration by name."""
        return self.targets.get(target_name)

    def get_workflows_for_target(self, target_name: str) -> List[WorkflowConfig]:
        """Get workflows that should be triggered for a target."""
        # For now, return all workflows. Could be enhanced to filter by target
        return self.workflows
