"""Create command for SMUS CI/CD CLI."""

from pathlib import Path
from typing import List, Optional, Tuple

import boto3
import typer
from botocore.exceptions import ClientError


def create_command(
    pipeline_name: str,
    domain_id: Optional[str] = None,
    dev_project_id: Optional[str] = None,
    stages: List[str] = None,
    region: str = "us-east-1",
) -> None:
    """
    Create a new pipeline manifest with all required fields and commented optional fields.

    Args:
        pipeline_name: Name of the pipeline (required)
        domain_id: SageMaker Unified Studio domain ID (optional)
        dev_project_id: Development project ID to base other targets on (optional)
        stages: List of stages to create targets for (defaults to ["dev", "test", "prod"])
        region: AWS region (defaults to "us-east-1")
    """
    if stages is None:
        stages = ["dev", "test", "prod"]

    domain_name, dev_project_name = _resolve_aws_resources(
        domain_id, dev_project_id, region
    )

    manifest_content = _generate_manifest_content(
        pipeline_name, domain_name, dev_project_name, stages, region
    )

    output_path = _write_manifest_file(pipeline_name, manifest_content)

    _display_creation_summary(
        pipeline_name, domain_name, output_path, stages, domain_id, dev_project_id
    )


def create_command_with_output(
    pipeline_name: str,
    output_file: str,
    domain_id: Optional[str] = None,
    dev_project_id: Optional[str] = None,
    stages: List[str] = None,
    region: str = "us-east-1",
) -> None:
    """
    Create a new pipeline manifest with all required fields and commented optional fields.

    Args:
        pipeline_name: Name of the pipeline (required)
        output_file: Output file path for the manifest
        domain_id: SageMaker Unified Studio domain ID (optional)
        dev_project_id: Development project ID to base other targets on (optional)
        stages: List of stages to create targets for (defaults to ["dev", "test", "prod"])
        region: AWS region (defaults to "us-east-1")
    """
    if stages is None:
        stages = ["dev", "test", "prod"]

    domain_name, dev_project_name = _resolve_aws_resources(
        domain_id, dev_project_id, region
    )

    manifest_content = _generate_manifest_content(
        pipeline_name, domain_name, dev_project_name, stages, region
    )

    output_path = _write_manifest_file_to_path(output_file, manifest_content)

    _display_creation_summary(
        pipeline_name, domain_name, output_path, stages, domain_id, dev_project_id
    )


def _write_manifest_file_to_path(output_file: str, content: str) -> Path:
    """
    Write manifest content to specified file path.

    Args:
        output_file: Output file path
        content: Manifest content to write

    Returns:
        Path to the created file

    Raises:
        typer.Exit: If file creation fails
    """
    try:
        output_path = Path(output_file)

        # Create parent directories if they don't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(content)

        return output_path

    except Exception as e:
        typer.echo(f"❌ Error creating manifest: {str(e)}", err=True)
        raise typer.Exit(1)


def _resolve_aws_resources(
    domain_id: Optional[str], dev_project_id: Optional[str], region: str
) -> Tuple[str, str]:
    """
    Resolve AWS domain and project names from IDs.

    Args:
        domain_id: SageMaker Unified Studio domain ID
        dev_project_id: Development project ID
        region: AWS region

    Returns:
        Tuple of (domain_name, dev_project_name)
    """
    domain_name = "your-domain-name  # PLACEHOLDER: Replace with your SageMaker Unified Studio domain name"
    dev_project_name = (
        "dev-project-name  # PLACEHOLDER: Replace with your dev project name"
    )

    if domain_id and dev_project_id:
        try:
            domain_name, dev_project_name = _fetch_aws_resource_names(
                domain_id, dev_project_id, region
            )
        except ClientError as e:
            _handle_aws_error(e, domain_id, dev_project_id)
            domain_name = f"domain-{domain_id[-8:]}"
            dev_project_name = dev_project_id
        except Exception as e:
            _handle_general_error(e, domain_id, dev_project_id)
            domain_name = f"domain-{domain_id[-8:]}"
            dev_project_name = dev_project_id

    return domain_name, dev_project_name


def _fetch_aws_resource_names(
    domain_id: str, dev_project_id: str, region: str
) -> Tuple[str, str]:
    """
    Fetch actual AWS resource names from their IDs.

    Args:
        domain_id: SageMaker Unified Studio domain ID
        dev_project_id: Development project ID
        region: AWS region

    Returns:
        Tuple of (domain_name, dev_project_name)

    Raises:
        ClientError: If AWS API calls fail
    """
    datazone_client = boto3.client("datazone", region_name=region)

    # Get domain info
    domain_response = datazone_client.get_domain(identifier=domain_id)
    domain_name = domain_response["name"]
    typer.echo(f"✅ Found domain: {domain_name} ({domain_id})")

    # Get dev project info
    project_response = datazone_client.get_project(
        domainIdentifier=domain_id, identifier=dev_project_id
    )
    dev_project_name = project_response["name"]
    typer.echo(f"✅ Found dev project: {dev_project_name} ({dev_project_id})")

    return domain_name, dev_project_name


def _handle_aws_error(error: ClientError, domain_id: str, dev_project_id: str) -> None:
    """Handle AWS ClientError exceptions."""
    typer.echo(f"⚠️  AWS Error: {error.response['Error']['Message']}", err=True)
    typer.echo("📝 Using provided IDs as names (AWS lookup failed)", err=True)


def _handle_general_error(
    error: Exception, domain_id: str, dev_project_id: str
) -> None:
    """Handle general exceptions during AWS resource validation."""
    typer.echo(f"⚠️  Error validating AWS resources: {str(error)}", err=True)
    typer.echo("📝 Using provided IDs as names (AWS lookup failed)", err=True)


def _generate_manifest_content(
    pipeline_name: str,
    domain_name: str,
    dev_project_name: str,
    stages: List[str],
    region: str,
) -> str:
    """
    Generate the complete manifest file content.

    Args:
        pipeline_name: Name of the pipeline
        domain_name: Domain name or placeholder
        dev_project_name: Dev project name or placeholder
        stages: List of stages to create
        region: AWS region

    Returns:
        Complete manifest content as string
    """
    targets_config = _generate_targets_section(stages, dev_project_name)

    return f"""# SMUS CI/CD Pipeline Manifest
# Generated template with required fields and optional field examples

pipelineName: {pipeline_name}

domain:
  name: {domain_name}
  region: {region}

# Bundle configuration (optional)
bundle:
  bundlesDirectory: ./bundles
  workflow:
    - connectionName: default.s3_shared
      include:
        - 'workflows'
      exclude:
        - '.ipynb_checkpoints/'
        - '__pycache__/'
        - '*.pyc'
        - '.libs.json'
  storage:
    - connectionName: default.s3_shared
      include:
        - '*'
      exclude:
        - '.ipynb_checkpoints/'
        - '__pycache__/'
        - '*.pyc'
        - '.libs.json'

targets:
{targets_config}
# Workflows configuration (optional)
# workflows:
#   - workflowName: your_workflow_name
#     connectionName: project.workflow_mwaa
#     triggerPostDeployment: true
#     logging: console
#     engine: MWAA
#     # parameters:
#     #   env: production
#     #   timeout: 3600
#
#   - workflowName: another_workflow
#     connectionName: project.workflow_mwaa
#     triggerPostDeployment: false
#     logging: none
#     engine: MWAA
"""


def _generate_targets_section(stages: List[str], dev_project_name: str) -> str:
    """
    Generate the targets section of the manifest.

    Args:
        stages: List of stage names
        dev_project_name: Development project name

    Returns:
        Formatted targets section as string
    """
    targets_config = ""

    for i, stage in enumerate(stages):
        stage_upper = stage.upper()
        project_name, create_project = _determine_project_config(
            stage, dev_project_name
        )
        default_comment = _get_default_comment(i)

        targets_config += f"""  {stage}:
    stage: {stage_upper}
    project:
      name: {project_name}
      create: {str(create_project).lower()}  # {'Auto-create project' if create_project else 'Use existing project'}
{default_comment}

    # Bundle target configuration
    bundle_target_configuration:
      storage:
        connectionName: default.s3_shared
        directory: 'src'
      workflows:
        connectionName: default.s3_shared
        directory: 'workflows'

    # Test configuration (optional)
    tests:
      folder: ./tests

"""

    return targets_config


def _determine_project_config(stage: str, dev_project_name: str) -> Tuple[str, bool]:
    """
    Determine project name and creation flag for a stage.

    Args:
        stage: Stage name (e.g., "dev", "test", "prod")
        dev_project_name: Development project name template

    Returns:
        Tuple of (project_name, create_project_flag)
    """
    if stage == "dev":
        return dev_project_name, False

    # Generate project names based on dev project name + stage
    if (
        dev_project_name
        != "dev-project-name  # PLACEHOLDER: Replace with your dev project name"
    ):
        # Use dev project name as base and append stage
        base_name = dev_project_name.replace("-dev", "").replace("_dev", "")
        project_name = f"{base_name}-{stage}"
        create_project = True
    else:
        project_name = f"{stage}-project-name  # PLACEHOLDER: Replace with your {stage} project name"
        create_project = True

    return project_name, create_project


def _get_default_comment(index: int) -> str:
    """Get appropriate default comment for target based on its position."""
    if index == 0:
        return "    default: true  # Default target for operations"
    else:
        return "    # default: true  # Uncomment to make this the default target"


def _write_manifest_file(pipeline_name: str, content: str) -> Path:
    """
    Write manifest content to file.

    Args:
        pipeline_name: Name of the pipeline (used for filename)
        content: Manifest content to write

    Returns:
        Path to the created file

    Raises:
        typer.Exit: If file creation fails
    """
    try:
        output_file = f"{pipeline_name}.yaml"
        output_path = Path.cwd() / output_file

        with open(output_path, "w") as f:
            f.write(content)

        return output_path

    except Exception as e:
        typer.echo(f"❌ Error creating manifest: {str(e)}", err=True)
        raise typer.Exit(1)


def _display_creation_summary(
    pipeline_name: str,
    domain_name: str,
    output_path: Path,
    stages: List[str],
    domain_id: Optional[str],
    dev_project_id: Optional[str],
) -> None:
    """
    Display summary of manifest creation and next steps.

    Args:
        pipeline_name: Name of the created pipeline
        domain_name: Domain name used
        output_path: Path to the created manifest file
        stages: List of stages that were created
        domain_id: Domain ID if provided
        dev_project_id: Dev project ID if provided
    """
    typer.echo(f"✅ Pipeline manifest created: {output_path}")
    typer.echo(f"📝 Pipeline name: {pipeline_name}")
    typer.echo(f"🌐 Domain: {domain_name}")
    typer.echo(f"📁 Output file: {output_path.absolute()}")
    typer.echo(f"🎯 Stages: {', '.join(stages)}")
    typer.echo()

    _validate_created_manifest(output_path, domain_id, dev_project_id)
    _display_next_steps(domain_id, dev_project_id)


def _validate_created_manifest(
    output_path: Path, domain_id: Optional[str], dev_project_id: Optional[str]
) -> None:
    """Validate the created manifest if AWS resources were provided."""
    if domain_id and dev_project_id:
        typer.echo("🔍 Testing created manifest...")
        try:
            from .describe import describe_command

            describe_command(
                str(output_path),
                targets=None,
                connect=False,
                output="TEXT",
                connections=False,
            )
            typer.echo("✅ Manifest validation successful!")
        except Exception as e:
            typer.echo(f"⚠️  Manifest validation failed: {str(e)}")


def _display_next_steps(
    domain_id: Optional[str], dev_project_id: Optional[str]
) -> None:
    """Display appropriate next steps based on whether AWS resources were provided."""
    typer.echo()
    typer.echo("📋 Next steps:")

    if not domain_id or not dev_project_id:
        typer.echo("1. Edit the manifest file and replace PLACEHOLDER values")
        typer.echo("2. Update domain name and region")
        typer.echo("3. Configure target project names")
    else:
        typer.echo("1. Review and adjust target project names if needed")
        typer.echo("2. Set create: true for projects that need to be created")

    typer.echo("4. Add workflows if needed")
    typer.echo("5. Validate with: smus-cli describe --pipeline <manifest-file>")
