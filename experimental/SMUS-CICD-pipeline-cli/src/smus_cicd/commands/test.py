"""Test command implementation."""

import json
import os
import subprocess
import sys

import typer

from ..helpers.utils import get_datazone_project_info, load_config
from ..pipeline import PipelineManifest


def _display_target_summary(target_name: str, test_results: dict, output: str):
    """Display test summary for a single target."""
    if output.upper() == "JSON":
        return

    target_result = test_results.get(target_name, {})
    status = target_result.get("status", "unknown")

    if status == "skipped":
        typer.echo("  📊 Target Summary: ⚠️  Skipped")
    elif status == "error":
        reason = target_result.get("reason", "")
        if reason == "no_tests_configured":
            typer.echo("  📊 Target Summary: ❌ Failed (no tests configured)")
        else:
            typer.echo("  📊 Target Summary: ❌ Error")
    elif status == "passed":
        typer.echo("  📊 Target Summary: ✅ Passed")
    elif status == "failed":
        typer.echo("  📊 Target Summary: ❌ Failed")
    else:
        typer.echo("  📊 Target Summary: ❓ Unknown")
    typer.echo()  # Add blank line between targets


def test_command(
    targets: str = typer.Option(
        None,
        "--targets",
        help="Target name(s) - single target or comma-separated list (optional, defaults to all targets)",
    ),
    output: str = typer.Option(
        "TEXT", "--output", help="Output format: TEXT (default) or JSON"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed test output"),
    manifest_file: str = typer.Option(
        "pipeline.yaml", "--pipeline", "-p", help="Path to pipeline manifest file"
    ),
):
    """Run tests for pipeline targets."""
    try:
        # Ensure output has a default value
        if output is None:
            output = "TEXT"

        # Load pipeline manifest
        manifest = PipelineManifest.from_file(manifest_file)

        # Parse target list
        if targets:
            target_list = [t.strip() for t in targets.split(",")]
        else:
            target_list = list(manifest.targets.keys())

        # Validate targets exist
        for target_name in target_list:
            if target_name not in manifest.targets:
                typer.echo(f"❌ Error: Target '{target_name}' not found in manifest")
                raise typer.Exit(1)

        # Get the first target's domain for display (they should all be the same)
        first_target = next(iter(manifest.targets.values()))
        domain_config = first_target.domain

        if output.upper() != "JSON":
            typer.echo(f"Pipeline: {manifest.pipeline_name}")
            typer.echo(f"Domain: {domain_config.name} ({domain_config.region})")
            typer.echo()

        test_results = {}
        overall_success = True

        for target_name in target_list:
            target_config = manifest.targets[target_name]

            if output.upper() != "JSON":
                typer.echo(f"🎯 Target: {target_name}")

            # Check if target has tests configured
            if not target_config.tests:
                if output.upper() != "JSON":
                    typer.echo(f"  ❌ No tests configured for target '{target_name}'")
                test_results[target_name] = {
                    "status": "error",
                    "reason": "no_tests_configured",
                }
                overall_success = False
                _display_target_summary(target_name, test_results, output)
                continue

            # Prepare test environment
            test_folder = target_config.tests.folder
            if not os.path.exists(test_folder):
                if output.upper() != "JSON":
                    typer.echo(f"  ❌ Test folder not found: {test_folder}")
                test_results[target_name] = {
                    "status": "error",
                    "error": f"Test folder not found: {test_folder}",
                }
                overall_success = False
                _display_target_summary(target_name, test_results, output)
                continue

            # Load AWS config
            config = load_config()
            config["domain"] = {
                "name": target_config.domain.name,
                "region": target_config.domain.region,
            }
            config["region"] = target_config.domain.region
            config["domain_name"] = target_config.domain.name

            # Get project info for context
            project_info = get_datazone_project_info(target_config.project.name, config)

            if "error" in project_info:
                if output.upper() != "JSON":
                    typer.echo(
                        f"  ❌ Error getting project info: {project_info['error']}"
                    )
                test_results[target_name] = {
                    "status": "error",
                    "error": project_info["error"],
                }
                overall_success = False
                _display_target_summary(target_name, test_results, output)
                continue

            # Set environment variables for tests
            test_env = os.environ.copy()
            test_env.update(
                {
                    "SMUS_DOMAIN_ID": project_info.get("domainId", ""),
                    "SMUS_PROJECT_ID": project_info.get("id", ""),
                    "SMUS_PROJECT_NAME": target_config.project.name,
                    "SMUS_TARGET_NAME": target_name,
                    "SMUS_REGION": target_config.domain.region,
                    "SMUS_DOMAIN_NAME": target_config.domain.name,
                }
            )

            if output.upper() != "JSON":
                typer.echo(f"  📁 Test folder: {test_folder}")
                typer.echo(
                    f"  🔧 Project: {target_config.project.name} ({project_info.get('id', 'unknown')})"
                )

            # Run pytest on the test folder
            try:
                cmd = [sys.executable, "-m", "pytest", test_folder]
                if verbose:
                    cmd.append("-v")
                else:
                    cmd.extend(["-q", "--tb=short"])

                if output.upper() != "JSON":
                    typer.echo("  🧪 Running tests...")

                result = subprocess.run(
                    cmd, env=test_env, capture_output=True, text=True, cwd=os.getcwd()
                )

                test_output = result.stdout + result.stderr

                if result.returncode == 0:
                    if output.upper() != "JSON":
                        typer.echo("  ✅ Tests passed")
                        if verbose and test_output:
                            typer.echo(f"  Output:\n{test_output}")
                    test_results[target_name] = {
                        "status": "passed",
                        "output": test_output,
                        "project_id": project_info.get("id"),
                        "domain_id": project_info.get("domainId"),
                    }
                else:
                    if output.upper() != "JSON":
                        typer.echo("  ❌ Tests failed")
                        if test_output:
                            typer.echo(f"  Output:\n{test_output}")
                    test_results[target_name] = {
                        "status": "failed",
                        "output": test_output,
                        "project_id": project_info.get("id"),
                        "domain_id": project_info.get("domainId"),
                    }
                    overall_success = False

            except Exception as e:
                if output.upper() != "JSON":
                    typer.echo(f"  ❌ Error running tests: {e}")
                test_results[target_name] = {"status": "error", "error": str(e)}
                overall_success = False

            if output.upper() != "JSON":
                typer.echo()

        # Output results
        if output.upper() == "JSON":
            result_data = {
                "pipeline": manifest.pipeline_name,
                "domain": domain_config.name,
                "region": domain_config.region,
                "targets": test_results,
                "overall_success": overall_success,
            }
            typer.echo(json.dumps(result_data, indent=2))
        else:
            # Show overall result only
            total_targets = len(test_results)
            passed_targets = sum(
                1 for r in test_results.values() if r.get("status") == "passed"
            )
            failed_targets = sum(
                1 for r in test_results.values() if r.get("status") == "failed"
            )
            skipped_targets = sum(
                1 for r in test_results.values() if r.get("status") == "skipped"
            )
            error_targets = sum(
                1 for r in test_results.values() if r.get("status") == "error"
            )

            typer.echo("🎯 Overall Summary:")
            typer.echo(f"  📊 Total targets: {total_targets}")
            if passed_targets > 0:
                typer.echo(f"  ✅ Targets passed: {passed_targets}")
            if failed_targets > 0:
                typer.echo(f"  ❌ Targets failed: {failed_targets}")
            if skipped_targets > 0:
                typer.echo(f"  ⚠️  Targets skipped: {skipped_targets}")
            if error_targets > 0:
                typer.echo(f"  🚫 Targets with errors: {error_targets}")

        if not overall_success:
            raise typer.Exit(1)

    except Exception as e:
        if output.upper() == "JSON":
            # Only output error JSON if we haven't already output results
            if "test_results" not in locals() or not test_results:
                error_data = {"error": str(e)}
                typer.echo(json.dumps(error_data, indent=2))
        else:
            typer.echo(f"❌ Error running tests: {e}")
        raise typer.Exit(1)
