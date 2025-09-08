#!/usr/bin/env python3
"""
SMUS CI/CD CLI - Command Line Interface for SageMaker Unified Studio CI/CD Pipeline Management
"""

import typer
from rich.console import Console

from . import __version__
from .commands.bundle import bundle_command
from .commands.create import create_command_with_output
from .commands.delete import delete_command
from .commands.deploy import deploy_command

# Import command functions
from .commands.describe import describe_command
from .commands.monitor import monitor_command
from .commands.run import run_command
from .commands.test import test_command

console = Console()


def show_help_suggestion():
    """Show helpful suggestions for common mistakes."""
    console.print("\n[yellow]💡 Common usage patterns:[/yellow]")
    console.print("   [cyan]smus-cli describe -p my-pipeline.yaml -t dev[/cyan]")
    console.print("   [cyan]smus-cli monitor -p my-pipeline.yaml --output JSON[/cyan]")
    console.print("   [cyan]smus-cli deploy -p my-pipeline.yaml -t prod[/cyan]")

    console.print("\n[yellow]🔧 Universal switches (work on all commands):[/yellow]")
    console.print("   [green]--pipeline/-p[/green]  - Path to pipeline manifest")
    console.print("   [green]--target/-t[/green]    - Target environment")
    console.print("   [green]--output[/green]       - Output format (TEXT/JSON)")

    console.print("\n[yellow]📖 For detailed help:[/yellow]")
    console.print("   [cyan]smus-cli --help[/cyan]")
    console.print("   [cyan]smus-cli <command> --help[/cyan]")


app = typer.Typer(
    help="SMUS CI/CD CLI - Manage SageMaker Unified Studio CI/CD pipelines",
    no_args_is_help=True,
    add_completion=False,
    epilog="💡 Use 'smus-cli <command> --help' for command-specific help",
)


# Register commands with proper ordering
@app.command(
    "describe",
    help="1. Describe and validate pipeline manifest file. Example: smus-cli describe -p pipeline.yaml -t dev",
    rich_help_panel="Pipeline Commands",
)
def describe(
    targets: str = typer.Option(
        None,
        "--targets",
        "-t",
        help="Target name(s) - single target or comma-separated list (optional, defaults to all targets)",
    ),
    output: str = typer.Option(
        "TEXT", "--output", "-o", help="Output format: TEXT (default) or JSON"
    ),
    connections: bool = typer.Option(
        False, "--connections", "-c", help="Show connection information"
    ),
    connect: bool = typer.Option(
        False,
        "--connect",
        help="Connect to AWS account and pull additional information",
    ),
    workflows: bool = typer.Option(
        False,
        "--workflows",
        help="Show workflow information (for backward compatibility)",
    ),
    file_path: str = typer.Option(
        "pipeline.yaml", "--pipeline", "-p", help="Path to pipeline manifest file"
    ),
):
    """Describe and validate pipeline manifest file."""
    describe_command(file_path, targets, output, connections, connect)


@app.command(
    "bundle",
    help="2. Create bundle zip files by downloading from S3. Example: smus-cli bundle -p pipeline.yaml -t dev",
    rich_help_panel="Pipeline Commands",
)
def bundle(
    manifest_file: str = typer.Option(
        "pipeline.yaml", "--pipeline", "-p", help="Path to pipeline manifest file"
    ),
    output_dir: str = typer.Option(
        "./bundles", "--output-dir", "-d", help="Output directory for bundle files"
    ),
    output: str = typer.Option(
        "TEXT", "--output", "-o", help="Output format: TEXT (default) or JSON"
    ),
    targets: str = typer.Option(
        None,
        "--targets",
        "-t",
        help="Target name(s) - single target or comma-separated list (uses default target if not specified)",
    ),
    target_positional: str = typer.Argument(
        None, help="Target name (positional argument for backward compatibility)"
    ),
):
    """Create bundle zip files by downloading from S3 connection locations."""
    # Use positional argument if provided, otherwise use --targets flag
    final_targets = target_positional if target_positional else targets
    bundle_command(final_targets, manifest_file, output_dir, output)


@app.command(
    "deploy",
    help="3. Deploy bundle files to target (auto-initializes if needed). Example: smus-cli deploy -p pipeline.yaml -t prod",
    rich_help_panel="Pipeline Commands",
)
def deploy(
    manifest_file: str = typer.Option(
        "pipeline.yaml", "--pipeline", "-p", help="Path to pipeline manifest file"
    ),
    targets: str = typer.Option(
        None,
        "--targets",
        "-t",
        help="Target name(s) - single target or comma-separated list (uses default target if not specified)",
    ),
    target_positional: str = typer.Argument(
        None, help="Target name (positional argument for backward compatibility)"
    ),
):
    """Deploy bundle files to target's bundle_target_configuration (auto-initializes infrastructure if needed)."""
    # Use positional argument if provided, otherwise use --targets flag
    final_targets = target_positional if target_positional else targets
    deploy_command(final_targets, manifest_file)


@app.command(
    "monitor",
    help="4. Monitor workflow status. Example: smus-cli monitor -p pipeline.yaml -t dev",
    rich_help_panel="Pipeline Commands",
)
def monitor(
    manifest_file: str = typer.Option(
        "pipeline.yaml", "--pipeline", "-p", help="Path to pipeline manifest file"
    ),
    output: str = typer.Option(
        "TEXT", "--output", "-o", help="Output format: TEXT (default) or JSON"
    ),
    targets: str = typer.Option(
        None,
        "--targets",
        "-t",
        help="Target name(s) - single target or comma-separated list (shows all targets if not specified)",
    ),
):
    """Monitor workflow status across target environments."""
    monitor_command(targets, manifest_file, output)


@app.command(
    "create",
    help="0. Create new pipeline manifest. Example: smus-cli create --output pipeline.yaml --name 'MyPipeline'",
    rich_help_panel="Pipeline Commands",
)
def create(
    output: str = typer.Option(
        "pipeline.yaml",
        "--output",
        "-o",
        help="Output file path for the pipeline manifest",
    ),
    name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="Pipeline name (optional, defaults to 'YourPipelineName')",
    ),
    domain_id: str = typer.Option(
        None, "--domain-id", help="SageMaker Unified Studio domain ID"
    ),
    dev_project_id: str = typer.Option(
        None, "--dev-project-id", help="Development project ID to base other targets on"
    ),
    stages: str = typer.Option(
        "dev,test,prod",
        "--stages",
        help="Comma-separated list of stages to create targets for",
    ),
    region: str = typer.Option("us-east-1", "--region", help="AWS region"),
):
    """Create a new pipeline manifest with all required fields and commented optional fields."""
    # If no name provided, use default expected by tests
    if not name:
        name = "YourPipelineName"

    stages_list = [s.strip() for s in stages.split(",")]

    # Update create_command to accept output parameter
    create_command_with_output(
        name, output, domain_id, dev_project_id, stages_list, region
    )


@app.command(
    "run",
    help="6. Run Airflow CLI commands. Example: smus-cli run --workflow dag --command version -p pipeline.yaml",
    rich_help_panel="Pipeline Commands",
)
def run(
    workflow: str = typer.Option(
        None, "--workflow", "-w", help="Workflow name to target (required)"
    ),
    command: str = typer.Option(
        None, "--command", "-c", help="Airflow command to execute (required)"
    ),
    targets: str = typer.Option(
        None,
        "--targets",
        "-t",
        help="Target name(s) - single target or comma-separated list (optional, defaults to first available)",
    ),
    manifest_file: str = typer.Option(
        "pipeline.yaml", "--pipeline", "-p", help="Path to pipeline manifest file"
    ),
    output: str = typer.Option(
        "TEXT", "--output", "-o", help="Output format: TEXT (default) or JSON"
    ),
):
    """Run Airflow CLI commands on specified workflow environments."""
    run_command(manifest_file, workflow, command, targets, output)


@app.command(
    "test",
    help="6. Run tests for pipeline targets. Example: smus-cli test --targets marketing-test-stage",
    rich_help_panel="Pipeline Commands",
)
def test(
    targets: str = typer.Option(
        None,
        "--targets",
        "-t",
        help="Target name(s) - single target or comma-separated list (optional, defaults to all targets)",
    ),
    output: str = typer.Option(
        "TEXT", "--output", "-o", help="Output format: TEXT (default) or JSON"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed test output"
    ),
    file_path: str = typer.Option(
        "pipeline.yaml", "--pipeline", "-p", help="Path to pipeline manifest file"
    ),
):
    """Run tests for pipeline targets."""
    test_command(targets, output, verbose, file_path)


@app.command(
    "delete",
    help="7. Delete projects and environments. Example: smus-cli delete --targets marketing-test-stage --force",
    rich_help_panel="Pipeline Commands",
)
def delete(
    pipeline: str = typer.Option(
        "pipeline.yaml", "--pipeline", "-p", help="Path to pipeline manifest file"
    ),
    targets: str = typer.Option(
        None,
        "--targets",
        "-t",
        help="Target name(s) - single target or comma-separated list",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    async_mode: bool = typer.Option(
        False, "--async", help="Don't wait for deletion to complete"
    ),
    output: str = typer.Option(
        "TEXT", "--output", "-o", help="Output format: TEXT (default) or JSON"
    ),
):
    """Delete projects and environments that were deployed during initialize."""
    delete_command(pipeline, targets, force, async_mode, output)


@app.callback()
def main():
    """
    SMUS CI/CD CLI - Manage SageMaker Unified Studio CI/CD pipelines

    Universal switches that work on all commands:
    • --pipeline/-p : Path to pipeline manifest file
    • --target/-t   : Target environment
    • --output      : Output format (TEXT/JSON)
    """
    pass


def cli_error_handler():
    """Handle CLI errors and provide helpful suggestions."""
    # Always print version for debugging
    console.print(f"[dim]SMUS CI/CD CLI v{__version__}[/dim]")

    try:
        app()
    except typer.Exit as e:
        if e.exit_code != 0:
            show_help_suggestion()
        raise
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        show_help_suggestion()
        raise typer.Exit(1)


if __name__ == "__main__":
    cli_error_handler()
