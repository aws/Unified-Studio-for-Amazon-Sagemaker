"""Bootstrap handler for creating MWAA Serverless workflows."""

import os
import tempfile
from typing import Any, Dict, Optional

import boto3
import typer

from ...helpers import airflow_serverless, datazone
from ...helpers.bundle_storage import ensure_bundle_local
from ...helpers.context_resolver import ContextResolver
from ..models import BootstrapAction


def handle_workflow_create(
    action: BootstrapAction,
    context: Dict[str, Any],
) -> bool:
    """
    Create MWAA Serverless workflows from workflows section in manifest.

    Properties:
    - workflowName (optional): Specific workflow to create, omit to create all

    Args:
        action: Bootstrap action configuration (BootstrapAction object)
        context: Execution context containing target_config, config, manifest, metadata

    Returns:
        True if successful, False otherwise
    """
    # Extract from context
    target_config = context["target_config"]
    config = context["config"]
    manifest = context["manifest"]
    metadata = context.get("metadata", {})

    workflow_name_filter = action.parameters.get("workflowName")

    # Get workflows from manifest
    if not hasattr(manifest.content, "workflows") or not manifest.content.workflows:
        typer.echo("📋 No workflows configured in manifest")
        return True

    workflows_to_create = manifest.content.workflows
    if workflow_name_filter:
        workflows_to_create = [
            wf
            for wf in workflows_to_create
            if wf.get("workflowName") == workflow_name_filter
        ]
        if not workflows_to_create:
            typer.echo(f"❌ Workflow '{workflow_name_filter}' not found in manifest")
            return False

    typer.echo(f"🚀 Creating {len(workflows_to_create)} MWAA Serverless workflow(s)...")

    # Get required info from context
    project_name = target_config.project.name
    region = config["region"]
    stage_name = config.get("stage_name", "unknown")

    # Get project info from metadata (resolved once in deploy)
    project_info = metadata.get("project_info", {})
    project_id = project_info.get("project_id")
    domain_id = project_info.get("domain_id")

    if not project_id or not domain_id:
        typer.echo("❌ Project info not available in context")
        return False

    # Get S3 location from metadata (set by deploy)
    s3_bucket = metadata.get("s3_bucket")
    s3_prefix = metadata.get("s3_prefix")
    bundle_path = metadata.get("bundle_path")

    if not s3_bucket or s3_prefix is None:
        typer.echo(
            "❌ S3 location not available. Workflows must be deployed before creation."
        )
        return False

    # Ensure bundle is local if needed
    if bundle_path:
        ensure_bundle_local(bundle_path, region)

    # Get role ARN - need domain_name not domain_id
    domain_name = target_config.domain.name
    role_arn = datazone.get_project_user_role_arn(project_name, domain_name, region)
    if not role_arn:
        typer.echo("❌ No project user role found")
        return False

    # Initialize context resolver
    resolver = ContextResolver(
        project_name=project_name,
        domain_id=domain_id,
        region=region,
        domain_name=domain_name,
        stage_name=stage_name,
        env_vars=target_config.environment_variables or {},
    )

    s3_client = boto3.client("s3", region_name=region)
    workflows_created = []

    # Find DAG files in S3
    from ...commands.deploy import _find_dag_files_in_s3, _generate_workflow_name

    dag_files_in_s3 = _find_dag_files_in_s3(
        s3_client, s3_bucket, s3_prefix, manifest, target_config
    )

    if not dag_files_in_s3:
        typer.echo("⚠️ No DAG files found in S3")
        return True

    # Filter by workflow name if specified
    if workflow_name_filter:
        dag_files_in_s3 = [
            (s3_key, wf_name)
            for s3_key, wf_name in dag_files_in_s3
            if wf_name == workflow_name_filter
        ]

    for s3_key, workflow_name_from_yaml in dag_files_in_s3:
        workflow_name = _generate_workflow_name(
            manifest.application_name,
            workflow_name_from_yaml,
            target_config,
        )

        # Download, resolve variables, upload
        temp_yaml = tempfile.NamedTemporaryFile(mode="w+", suffix=".yaml", delete=False)
        try:
            s3_client.download_file(s3_bucket, s3_key, temp_yaml.name)

            with open(temp_yaml.name, "r") as f:
                original_content = f.read()

            typer.echo(f"🔍 DEBUG: Original content length: {len(original_content)}")
            resolved_content = resolver.resolve(original_content)

            with open(temp_yaml.name, "w") as f:
                f.write(resolved_content)

            s3_client.upload_file(temp_yaml.name, s3_bucket, s3_key)
            typer.echo(f"✅ Resolved variables in {s3_key}")
            typer.echo(f"🔍 DEBUG: Resolved content preview (first 500 chars):\n{resolved_content[:500]}")
        except Exception as e:
            typer.echo(f"❌ Error resolving variables in {s3_key}: {e}")
            return False
        finally:
            os.unlink(temp_yaml.name)

        # Create workflow
        s3_location = f"s3://{s3_bucket}/{s3_key}"
        
        # Verify the YAML in S3 before creating workflow
        typer.echo(f"🔍 DEBUG: About to create/update workflow from S3: {s3_location}")
        verify_temp = tempfile.NamedTemporaryFile(mode="r", suffix=".yaml", delete=False)
        try:
            s3_client.download_file(s3_bucket, s3_key, verify_temp.name)
            with open(verify_temp.name, "r") as f:
                s3_content = f.read()
            typer.echo(f"🔍 DEBUG: S3 YAML content (first 800 chars):\n{s3_content[:800]}")
            if "SMUSCICDTestRole" in s3_content:
                typer.echo("⚠️ WARNING: S3 YAML still contains 'SMUSCICDTestRole'!")
            if "{proj.iam_role_name}" in s3_content:
                typer.echo("⚠️ WARNING: S3 YAML still contains unresolved '{proj.iam_role_name}'!")
        finally:
            os.unlink(verify_temp.name)

        result = airflow_serverless.create_workflow(
            workflow_name=workflow_name,
            dag_s3_location=s3_location,
            role_arn=role_arn,
            description=f"SMUS CI/CD workflow for {manifest.application_name}",
            tags={
                "Pipeline": manifest.application_name,
                "Target": target_config.project.name,
                "STAGE": stage_name.upper(),
                "CreatedBy": "SMUS-CICD",
            },
            datazone_domain_id=domain_id,
            datazone_domain_region=region,
            datazone_project_id=project_id,
            region=region,
        )

        if result.get("success"):
            workflow_arn = result["workflow_arn"]
            workflows_created.append({"name": workflow_name, "arn": workflow_arn})
            typer.echo(f"✅ Created workflow: {workflow_name}")
            typer.echo(f"   ARN: {workflow_arn}")

            # Validate status
            workflow_status = airflow_serverless.get_workflow_status(
                workflow_arn, region=region
            )
            if workflow_status.get("success"):
                status = workflow_status.get("status")
                typer.echo(f"   Status: {status}")
                if status == "FAILED":
                    typer.echo(f"❌ Workflow {workflow_name} is in FAILED state")
                    return False
        else:
            typer.echo(
                f"❌ Failed to create workflow {workflow_name}: {result.get('error')}"
            )
            return False

    if workflows_created:
        typer.echo(f"\n🎉 Successfully created {len(workflows_created)} workflow(s)")
        return True
    else:
        typer.echo("⚠️ No workflows were created")
        return True
