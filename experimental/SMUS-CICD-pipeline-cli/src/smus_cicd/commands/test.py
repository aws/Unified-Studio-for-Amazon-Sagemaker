"""Test command implementation."""

import json
import os
import subprocess
import sys

import typer

from ..helpers.utils import get_datazone_project_info, load_config
from ..pipeline import BundleManifest


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
    test_output: str = typer.Option(
        None,
        "--test-output",
        help="Test output mode: console (stream test output directly)",
    ),
    manifest_file: str = typer.Option(
        "bundle.yaml", "--bundle", "-b", help="Path to bundle manifest file"
    ),
):
    """Run tests for pipeline targets."""
    try:
        # Ensure output has a default value
        if output is None:
            output = "TEXT"

        # Load pipeline manifest
        manifest = BundleManifest.from_file(manifest_file)

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
            typer.echo(f"Pipeline: {manifest.bundle_name}")
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
            test_folder = os.path.abspath(target_config.tests.folder)
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
            # Build domain config with name and tags for proper resolution
            domain_dict = {"region": target_config.domain.region}
            if target_config.domain.name:
                domain_dict["name"] = target_config.domain.name
            if target_config.domain.tags:
                domain_dict["tags"] = target_config.domain.tags
            config["domain"] = domain_dict
            config["region"] = target_config.domain.region

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

            # Get domain name from domain_id if not provided
            domain_name = target_config.domain.name
            if not domain_name and project_info.get("domainId"):
                import boto3

                try:
                    datazone_client = boto3.client(
                        "datazone", region_name=target_config.domain.region
                    )
                    domain_response = datazone_client.get_domain(
                        identifier=project_info["domainId"]
                    )
                    domain_name = domain_response.get("name", "")
                except Exception:
                    domain_name = ""

            # Generate test configuration
            from ..helpers.test_config import generate_test_config

            test_config = generate_test_config(
                project_name=target_config.project.name,
                project_id=project_info.get(
                    "project_id", project_info.get("projectId", "")
                ),
                domain_id=project_info.get("domainId", ""),
                domain_name=domain_name,
                region=target_config.domain.region,
                target_name=target_name,
                env_vars=target_config.environment_variables or {},
            )

            # Write config file
            config_file = os.path.join(test_folder, ".smus_test_config.json")
            with open(config_file, "w") as f:
                json.dump(test_config, f, indent=2)

            # Write conftest.py dynamically
            conftest_content = '''"""Pytest configuration for pipeline tests - Auto-generated by SMUS CLI."""
import json
import os
import pytest


@pytest.fixture(scope="session")
def smus_config():
    """Load SMUS test configuration from JSON file."""
    config_file = os.path.join(os.path.dirname(__file__), ".smus_test_config.json")
    with open(config_file, 'r') as f:
        return json.load(f)
'''
            conftest_file = os.path.join(test_folder, "conftest.py")
            with open(conftest_file, "w") as f:
                f.write(conftest_content)

            if output.upper() != "JSON":
                typer.echo(f"  📝 Created config files in {test_folder}")

            # Set environment variables for tests (fallback)
            test_env = os.environ.copy()
            test_env.update(
                {
                    "SMUS_DOMAIN_ID": project_info.get("domainId", ""),
                    "SMUS_PROJECT_ID": project_info.get(
                        "project_id", project_info.get("projectId", "")
                    ),
                    "SMUS_PROJECT_NAME": target_config.project.name,
                    "SMUS_TARGET_NAME": target_name,
                    "SMUS_REGION": target_config.domain.region,
                    "SMUS_DOMAIN_NAME": domain_name or "",
                    "SMUS_TEST_CONFIG": config_file,
                }
            )

            if output.upper() != "JSON":
                typer.echo(f"  📁 Test folder: {test_folder}")
                typer.echo(
                    f"  🔧 Project: {target_config.project.name} ({project_info.get('project_id', project_info.get('projectId', 'unknown'))})"
                )

            # Run pytest on the test folder
            try:
                cmd = [sys.executable, "-m", "pytest", "."]
                if verbose:
                    cmd.append("-v")
                else:
                    cmd.extend(["-q", "--tb=short"])

                if output.upper() != "JSON":
                    typer.echo("  🧪 Running tests...")

                # Stream output directly to console if test_output is 'console'
                if test_output and test_output.lower() == "console":
                    result = subprocess.run(cmd, env=test_env, cwd=test_folder)
                    test_output_text = ""
                else:
                    result = subprocess.run(
                        cmd,
                        env=test_env,
                        capture_output=True,
                        text=True,
                        cwd=test_folder,
                    )
                    test_output_text = result.stdout + result.stderr

                if result.returncode == 0:
                    if output.upper() != "JSON":
                        typer.echo("  ✅ Tests passed")
                        if verbose and test_output_text:
                            typer.echo(f"  Output:\n{test_output_text}")
                    test_results[target_name] = {
                        "status": "passed",
                        "output": test_output_text,
                        "project_id": project_info.get("id"),
                        "domain_id": project_info.get("domainId"),
                    }
                else:
                    if output.upper() != "JSON":
                        typer.echo("  ❌ Tests failed")
                        if test_output_text:
                            typer.echo(f"  Output:\n{test_output_text}")
                    test_results[target_name] = {
                        "status": "failed",
                        "output": test_output_text,
                        "project_id": project_info.get("id"),
                        "domain_id": project_info.get("domainId"),
                    }
                    overall_success = False

            except Exception as e:
                if output.upper() != "JSON":
                    typer.echo(f"  ❌ Error running tests: {e}")
                test_results[target_name] = {"status": "error", "error": str(e)}
                overall_success = False
            finally:
                # Cleanup generated files
                try:
                    if os.path.exists(config_file):
                        os.remove(config_file)
                    if os.path.exists(conftest_file):
                        os.remove(conftest_file)
                except Exception:
                    pass

            if output.upper() != "JSON":
                typer.echo()

        # Output results
        if output.upper() == "JSON":
            result_data = {
                "bundle": manifest.bundle_name,
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
