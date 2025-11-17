"""Delete command for SMUS CI/CD CLI."""

import json
import time
from typing import Optional

import boto3
import typer
from rich.console import Console
from rich.prompt import Confirm

from ..application import ApplicationManifest
from ..helpers.datazone import get_domain_id_by_name

console = Console()


def delete_command(
    pipeline: str = typer.Option(
        "bundle.yaml", "--bundle", "-b", help="Path to bundle manifest file"
    ),
    targets: Optional[str] = typer.Option(
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
    """
    Delete projects and environments that were deployed during initialize.

    Example: smus-cli delete --targets test --force
    """
    try:
        # Parse manifest
        manifest = ApplicationManifest.from_file(pipeline)

        # Determine targets to delete
        if targets:
            target_list = [t.strip() for t in targets.split(",")]
        else:
            target_list = list(manifest.stages.keys())

        # Validate targets exist in manifest
        invalid_targets = [t for t in target_list if t not in manifest.stages]
        if invalid_targets:
            console.print(
                f"[red]Error: Target(s) not found in manifest: {', '.join(invalid_targets)}[/red]"
            )
            console.print(f"Available targets: {', '.join(manifest.stages.keys())}")
            raise typer.Exit(1)

        # Show what will be deleted
        if output.upper() != "JSON":
            console.print(f"[yellow]Pipeline:[/yellow] {manifest.application_name}")
            console.print()
            console.print("[yellow]Targets to delete:[/yellow]")

            for stage_name in target_list:
                target = manifest.stages[stage_name]
                console.print(
                    f"  - {stage_name}: {target.project.name} (Domain: {target.domain.name})"
                )

        # Confirmation prompt (unless --force)
        if not force:
            if output.upper() != "JSON":
                console.print()
                console.print(
                    "[red]⚠️  WARNING: This will permanently delete the above projects and all their resources![/red]"
                )
            if not Confirm.ask("Are you sure you want to continue?"):
                if output.upper() != "JSON":
                    console.print("Deletion cancelled.")
                return  # Just return instead of raising Exit

        # Delete each target
        results = []
        for stage_name in target_list:
            target = manifest.stages[stage_name]
            if output.upper() != "JSON":
                console.print(f"\n[blue]🗑️  Deleting target: {stage_name}[/blue]")

            try:
                # Get domain ID for this target
                domain_id = get_domain_id_by_name(
                    target.domain.name, target.domain.region
                )
                if not domain_id:
                    console.print(
                        f"[red]Error: Domain '{target.domain.name}' not found[/red]"
                    )
                    results.append(
                        {
                            "target": stage_name,
                            "project_name": target.project.name,
                            "status": "error",
                            "message": f"Domain '{target.domain.name}' not found",
                        }
                    )
                    continue

                # Initialize DataZone client
                dz = boto3.client("datazone", region_name=target.domain.region)

                # Find the project
                project_id = None
                try:
                    projects = dz.list_projects(domainIdentifier=domain_id)
                    for project in projects.get("items", []):
                        if project["name"] == target.project.name:
                            project_id = project["id"]
                            break
                except Exception as e:
                    console.print(f"[red]Error listing projects: {e}[/red]")
                    results.append(
                        {
                            "target": stage_name,
                            "project_name": target.project.name,
                            "status": "error",
                            "message": f"Error listing projects: {e}",
                        }
                    )
                    continue

                if not project_id:
                    if output.upper() != "JSON":
                        console.print(
                            f"[yellow]⚠️  Project '{target.project.name}' not found (already deleted?)[/yellow]"
                        )
                    results.append(
                        {
                            "target": stage_name,
                            "project_name": target.project.name,
                            "status": "not_found",
                            "message": "Project not found",
                        }
                    )
                    continue

                # Delete environments first
                if output.upper() != "JSON":
                    console.print("  🔍 Checking for environments...")

                try:
                    envs = dz.list_environments(
                        domainIdentifier=domain_id, projectIdentifier=project_id
                    )
                    env_count = len(envs.get("items", []))

                    if env_count > 0:
                        if output.upper() != "JSON":
                            console.print(
                                f"  🗑️  Deleting {env_count} environment(s)..."
                            )

                        for env in envs.get("items", []):
                            env_id = env["id"]
                            env_name = env.get("name", env_id)

                            if output.upper() != "JSON":
                                console.print(f"    - Deleting environment: {env_name}")

                            dz.delete_environment(
                                domainIdentifier=domain_id, identifier=env_id
                            )

                            # Wait for environment deletion
                            if not async_mode:
                                for i in range(60):
                                    try:
                                        dz.get_environment(
                                            domainIdentifier=domain_id,
                                            identifier=env_id,
                                        )
                                        time.sleep(2)
                                    except dz.exceptions.ResourceNotFoundException:
                                        if output.upper() != "JSON":
                                            console.print(
                                                f"    ✅ Environment {env_name} deleted after {i*2}s"
                                            )
                                        break
                    else:
                        if output.upper() != "JSON":
                            console.print(f"  ℹ️  No environments to delete")

                except Exception as e:
                    console.print(
                        f"[yellow]⚠️  Error deleting environments: {e}[/yellow]"
                    )

                # Delete the project
                if output.upper() != "JSON":
                    console.print(f"  🗑️  Deleting project: {target.project.name}")

                dz.delete_project(domainIdentifier=domain_id, identifier=project_id)

                # Wait for project deletion
                if not async_mode:
                    if output.upper() != "JSON":
                        console.print(f"  ⏳ Waiting for project deletion...")

                    for i in range(60):
                        try:
                            proj = dz.get_project(
                                domainIdentifier=domain_id, identifier=project_id
                            )
                            status = proj.get("projectStatus", "UNKNOWN")
                            if output.upper() != "JSON" and i % 5 == 0:
                                console.print(f"    Status: {status} (check {i+1}/60)")
                            time.sleep(2)
                        except dz.exceptions.ResourceNotFoundException:
                            if output.upper() != "JSON":
                                console.print(f"  ✅ Project deleted after {i*2}s")
                            break

                if async_mode:
                    if output.upper() != "JSON":
                        console.print(
                            f"[green]✅ Project deletion initiated for {target.project.name}[/green]"
                        )
                    results.append(
                        {
                            "target": stage_name,
                            "project_name": target.project.name,
                            "status": "deletion_initiated",
                            "message": "Project deletion started (async mode)",
                        }
                    )
                else:
                    if output.upper() != "JSON":
                        console.print(
                            f"[green]✅ Successfully deleted project {target.project.name}[/green]"
                        )
                    results.append(
                        {
                            "target": stage_name,
                            "project_name": target.project.name,
                            "status": "deleted",
                            "message": "Successfully deleted project and environments",
                        }
                    )

            except Exception as e:
                if output.upper() != "JSON":
                    console.print(
                        f"[red]❌ Failed to delete {target.project.name}: {str(e)}[/red]"
                    )
                results.append(
                    {
                        "target": stage_name,
                        "project_name": target.project.name,
                        "status": "error",
                        "message": str(e),
                    }
                )

        # Output results
        if output.upper() == "JSON":
            print(
                json.dumps(
                    {
                        "bundle": manifest.application_name,
                        "results": results,
                    },
                    indent=2,
                )
            )
        else:
            console.print("\n[blue]🎯 Deletion Summary[/blue]")
            for result in results:
                status_icon = {
                    "deleted": "✅",
                    "deletion_initiated": "🚀",
                    "not_found": "⚠️",
                    "error": "❌",
                }.get(result["status"], "❓")
                console.print(
                    f"  {status_icon} {result['target']}: {result['message']}"
                )

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)
