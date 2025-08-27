"""Delete command for SMUS CI/CD CLI."""

import typer
from typing import Optional, List
from rich.console import Console
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
import time

from ..pipeline import PipelineManifest
from ..helpers.datazone import (
    get_domain_id_by_name, 
    get_project_id_by_name, 
    delete_project, 
    get_project_status
)
from ..helpers.cloudformation import delete_project_stack

console = Console()

def delete_command(
    pipeline: str = typer.Option("pipeline.yaml", "--pipeline", "-p", help="Path to pipeline manifest file"),
    targets: Optional[str] = typer.Option(None, "--targets", "-t", help="Target name(s) - single target or comma-separated list"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    async_mode: bool = typer.Option(False, "--async", help="Don't wait for deletion to complete"),
    output: str = typer.Option("TEXT", "--output", "-o", help="Output format: TEXT (default) or JSON")
):
    """
    Delete projects and environments that were deployed during initialize.
    
    Example: smus-cli delete --targets test --force
    """
    try:
        # Parse manifest
        manifest = PipelineManifest.from_file(pipeline)
        
        # Determine targets to delete
        if targets:
            target_list = [t.strip() for t in targets.split(",")]
        else:
            target_list = list(manifest.targets.keys())
        
        # Validate targets exist in manifest
        invalid_targets = [t for t in target_list if t not in manifest.targets]
        if invalid_targets:
            console.print(f"[red]Error: Target(s) not found in manifest: {', '.join(invalid_targets)}[/red]")
            console.print(f"Available targets: {', '.join(manifest.targets.keys())}")
            raise typer.Exit(1)
        
        # Show what will be deleted
        if output.upper() != "JSON":
            console.print(f"[yellow]Pipeline:[/yellow] {manifest.pipeline_name}")
            console.print(f"[yellow]Domain:[/yellow] {manifest.domain.name} ({manifest.domain.region})")
            console.print()
            console.print("[yellow]Targets to delete:[/yellow]")
            
            for target_name in target_list:
                target = manifest.targets[target_name]
                console.print(f"  - {target_name}: {target.project.name}")
        
        # Confirmation prompt (unless --force)
        if not force:
            if output.upper() != "JSON":
                console.print()
                console.print("[red]⚠️  WARNING: This will permanently delete the above projects and all their resources![/red]")
            if not Confirm.ask("Are you sure you want to continue?"):
                if output.upper() != "JSON":
                    console.print("Deletion cancelled.")
                return  # Just return instead of raising Exit
        
        # Get domain ID
        domain_id = get_domain_id_by_name(manifest.domain.name, manifest.domain.region)
        if not domain_id:
            console.print(f"[red]Error: Domain '{manifest.domain.name}' not found[/red]")
            raise typer.Exit(1)
        
        # Delete each target
        results = []
        for target_name in target_list:
            target = manifest.targets[target_name]
            if output.upper() != "JSON":
                console.print(f"\n[blue]🗑️  Deleting target: {target_name}[/blue]")
            
            try:
                # Check if project exists
                project_id = get_project_id_by_name(target.project.name, domain_id, manifest.domain.region)
                
                if project_id:
                    # Delete project first
                    delete_project(manifest.domain.name, project_id, manifest.domain.region)
                else:
                    if output.upper() != "JSON":
                        console.print(f"[yellow]⚠️  Project {target.project.name} not found - skipping project deletion[/yellow]")
                
                # Always try to delete CloudFormation stack (even if project was not found)
                delete_project_stack(
                    target.project.name, 
                    manifest.domain.name, 
                    manifest.domain.region,
                    manifest.pipeline_name,
                    target_name,
                    output
                )
                
                if not project_id:
                    results.append({
                        "target": target_name,
                        "project_name": target.project.name,
                        "status": "stack_cleanup_only",
                        "message": "Project not found, cleaned up CloudFormation stack"
                    })
                    continue
                
                if async_mode:
                    if output.upper() != "JSON":
                        console.print(f"[green]✅ Deletion initiated for {target.project.name}[/green]")
                    results.append({
                        "target": target_name,
                        "project_name": target.project.name,
                        "project_id": project_id,
                        "status": "deletion_initiated",
                        "message": "Deletion started (async mode)"
                    })
                else:
                    # Delete and wait for completion
                    if output.upper() != "JSON":
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            console=console
                        ) as progress:
                            task = progress.add_task(f"Deleting {target.project.name}...", total=None)
                            
                            # Wait for deletion to complete
                            while True:
                                status = get_project_status(manifest.domain.name, project_id, manifest.domain.region)
                                if status is None:  # Project no longer exists
                                    break
                                if status in ["DELETE_FAILED"]:
                                    raise Exception(f"Project deletion failed with status: {status}")
                                time.sleep(10)
                    else:
                        # Wait for deletion without progress bar for JSON output
                        while True:
                            status = get_project_status(manifest.domain.name, project_id, manifest.domain.region)
                            if status is None:  # Project no longer exists
                                break
                            if status in ["DELETE_FAILED"]:
                                raise Exception(f"Project deletion failed with status: {status}")
                            time.sleep(10)
                    
                    if output.upper() != "JSON":
                        console.print(f"[green]✅ Successfully deleted {target.project.name}[/green]")
                    results.append({
                        "target": target_name,
                        "project_name": target.project.name,
                        "project_id": project_id,
                        "status": "deleted",
                        "message": "Successfully deleted"
                    })
                    
            except Exception as e:
                if output.upper() != "JSON":
                    console.print(f"[red]❌ Failed to delete {target.project.name}: {str(e)}[/red]")
                results.append({
                    "target": target_name,
                    "project_name": target.project.name,
                    "status": "error",
                    "message": str(e)
                })
        
        # Output results
        if output.upper() == "JSON":
            import json
            print(json.dumps({
                "pipeline": manifest.pipeline_name,
                "domain": manifest.domain.name,
                "results": results
            }, indent=2))
        else:
            console.print(f"\n[blue]🎯 Deletion Summary[/blue]")
            for result in results:
                status_icon = {
                    "deleted": "✅",
                    "deletion_initiated": "🚀", 
                    "not_found": "⚠️",
                    "error": "❌"
                }.get(result["status"], "❓")
                console.print(f"  {status_icon} {result['target']}: {result['message']}")
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)
