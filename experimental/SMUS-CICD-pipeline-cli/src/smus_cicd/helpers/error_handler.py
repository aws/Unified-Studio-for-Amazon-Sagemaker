"""Error handling utilities for SMUS CLI."""

import typer


def handle_error(message: str, exit_code: int = 1) -> None:
    """Handle errors consistently across the CLI."""
    typer.echo(f"❌ Error: {message}", err=True)
    raise typer.Exit(exit_code)


def handle_warning(message: str) -> None:
    """Handle warnings consistently across the CLI."""
    typer.echo(f"⚠️ Warning: {message}")


def handle_success(message: str) -> None:
    """Handle success messages consistently across the CLI."""
    typer.echo(f"✅ {message}")


def handle_info(message: str) -> None:
    """Handle info messages consistently across the CLI."""
    typer.echo(f"ℹ️ {message}")


def validate_target_exists(
    target_name: str, manifest, context: str = "operation"
) -> None:
    """Validate that a target exists in the manifest."""
    if not manifest.get_target(target_name):
        available_targets = list(manifest.targets.keys())
        handle_error(
            f"Target '{target_name}' not found in manifest for {context}. "
            f"Available targets: {', '.join(available_targets)}"
        )


def validate_required_config(
    config_value, config_name: str, context: str = "operation"
) -> None:
    """Validate that a required configuration value is present."""
    if not config_value:
        handle_error(f"{config_name} is required for {context}")
