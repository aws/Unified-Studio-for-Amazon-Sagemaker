"""QuickSight dashboard deployment helper."""

import json
import time
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from .logger import get_logger

logger = get_logger("quicksight")


class QuickSightDeploymentError(Exception):
    """Exception raised for QuickSight deployment errors."""

    pass


def lookup_dashboard_by_name(
    name: str,
    aws_account_id: str,
    region: str,
) -> str:
    """
    Lookup dashboard ID by name.

    Args:
        name: Dashboard name to lookup
        aws_account_id: AWS account ID
        region: AWS region

    Returns:
        Dashboard ID

    Raises:
        QuickSightDeploymentError: If dashboard not found
    """
    try:
        client = boto3.client("quicksight", region_name=region)
        response = client.list_dashboards(AwsAccountId=aws_account_id)

        for dashboard in response.get("DashboardSummaryList", []):
            if dashboard.get("Name") == name:
                logger.info(
                    f"Found dashboard '{name}' with ID: {dashboard['DashboardId']}"
                )
                return dashboard["DashboardId"]

        raise QuickSightDeploymentError(
            f"Dashboard with name '{name}' not found in account {aws_account_id}"
        )
    except ClientError as e:
        raise QuickSightDeploymentError(f"Failed to lookup dashboard: {e}")


def export_dashboard(
    dashboard_id: str,
    aws_account_id: str,
    region: str,
) -> str:
    """
    Export QuickSight dashboard to asset bundle.

    Args:
        dashboard_id: Dashboard ID to export
        aws_account_id: AWS account ID
        region: AWS region

    Returns:
        Job ID for the export operation

    Raises:
        QuickSightDeploymentError: If export fails
    """
    try:
        client = boto3.client("quicksight", region_name=region)

        response = client.start_asset_bundle_export_job(
            AwsAccountId=aws_account_id,
            AssetBundleExportJobId=f"export-{dashboard_id}-{int(time.time())}",
            ResourceArns=[
                f"arn:aws:quicksight:{region}:{aws_account_id}:dashboard/{dashboard_id}"
            ],
            ExportFormat="QUICKSIGHT_JSON",
            IncludeAllDependencies=True,
        )

        job_id = response["AssetBundleExportJobId"]
        logger.info(f"Started dashboard export: {job_id}")
        return job_id

    except Exception as e:
        raise QuickSightDeploymentError(f"Failed to start export: {e}")


def poll_export_job(
    job_id: str,
    aws_account_id: str,
    region: str,
    timeout: int = 300,
) -> str:
    """
    Poll export job until completion.

    Args:
        job_id: Export job ID
        aws_account_id: AWS account ID
        region: AWS region
        timeout: Timeout in seconds

    Returns:
        Download URL for the exported bundle

    Raises:
        QuickSightDeploymentError: If export fails or times out
    """
    client = boto3.client("quicksight", region_name=region)
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = client.describe_asset_bundle_export_job(
                AwsAccountId=aws_account_id,
                AssetBundleExportJobId=job_id,
            )

            status = response["JobStatus"]
            logger.info(f"Export job {job_id}: {status}")

            if status == "SUCCESSFUL":
                return response["DownloadUrl"]
            elif status == "FAILED":
                errors = response.get("Errors", [])
                raise QuickSightDeploymentError(f"Export failed: {errors}")

            time.sleep(5)

        except QuickSightDeploymentError:
            raise
        except ClientError as e:
            raise QuickSightDeploymentError(f"Export job failed: {e}")
        except Exception as e:
            logger.warning(f"Error polling export: {e}")
            time.sleep(5)

    raise QuickSightDeploymentError(f"Export timed out after {timeout}s")


def import_dashboard(
    bundle_url: str,
    aws_account_id: str,
    region: str,
    override_parameters: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Import QuickSight dashboard from asset bundle.

    Args:
        bundle_url: URL to the asset bundle
        aws_account_id: AWS account ID
        region: AWS region
        override_parameters: Optional parameters to override

    Returns:
        Job ID for the import operation

    Raises:
        QuickSightDeploymentError: If import fails
    """
    try:
        client = boto3.client("quicksight", region_name=region)

        import_params = {
            "AwsAccountId": aws_account_id,
            "AssetBundleImportJobId": f"import-{int(time.time())}",
            "AssetBundleImportSource": {"Body": _download_bundle(bundle_url)},
        }

        if override_parameters:
            import_params["OverrideParameters"] = override_parameters
            logger.info(
                f"Override parameters being sent to API: {json.dumps(override_parameters, indent=2)}"
            )

        response = client.start_asset_bundle_import_job(**import_params)

        job_id = response["AssetBundleImportJobId"]
        logger.info(f"Started dashboard import: {job_id}")
        return job_id

    except Exception as e:
        raise QuickSightDeploymentError(f"Failed to start import: {e}")


def poll_import_job(
    job_id: str,
    aws_account_id: str,
    region: str,
    timeout: int = 300,
) -> Dict[str, Any]:
    """
    Poll import job until completion.

    Args:
        job_id: Import job ID
        aws_account_id: AWS account ID
        region: AWS region
        timeout: Timeout in seconds

    Returns:
        Import job result details

    Raises:
        QuickSightDeploymentError: If import fails or times out
    """
    client = boto3.client("quicksight", region_name=region)
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = client.describe_asset_bundle_import_job(
                AwsAccountId=aws_account_id,
                AssetBundleImportJobId=job_id,
            )

            status = response["JobStatus"]
            logger.info(f"Import job {job_id}: {status}")

            if status == "SUCCESSFUL":
                return response
            elif status == "FAILED":
                errors = response.get("Errors", [])
                raise QuickSightDeploymentError(f"Import failed: {errors}")

            time.sleep(5)

        except QuickSightDeploymentError:
            raise
        except ClientError as e:
            raise QuickSightDeploymentError(f"Import job failed: {e}")
        except Exception as e:
            logger.warning(f"Error polling import: {e}")
            time.sleep(5)

    raise QuickSightDeploymentError(f"Import timed out after {timeout}s")


def grant_dashboard_permissions(
    dashboard_id: str,
    aws_account_id: str,
    region: str,
    permissions: List[Dict[str, str]],
) -> bool:
    """
    Grant permissions to QuickSight dashboard.

    Args:
        dashboard_id: Dashboard ID
        aws_account_id: AWS account ID
        region: AWS region
        permissions: List of permission grants

    Returns:
        True if successful

    Raises:
        QuickSightDeploymentError: If permission grant fails
    """
    if not permissions:
        return True

    try:
        client = boto3.client("quicksight", region_name=region)

        grant_permissions = []
        for perm in permissions:
            principal = perm.get("principal", "")
            actions = perm.get("actions", ["quicksight:DescribeDashboard"])

            logger.info(f"Expanding principal: {principal}")
            # Expand wildcards in principal
            expanded_principals = expand_principal_wildcards(
                principal, aws_account_id, region
            )
            logger.info(
                f"Expanded to {len(expanded_principals)} principals: {expanded_principals}"
            )

            for expanded_principal in expanded_principals:
                grant_permissions.append(
                    {
                        "Principal": expanded_principal,
                        "Actions": actions,
                    }
                )

        logger.info(
            f"Granting {len(grant_permissions)} permission sets to dashboard {dashboard_id}"
        )
        if grant_permissions:
            client.update_dashboard_permissions(
                AwsAccountId=aws_account_id,
                DashboardId=dashboard_id,
                GrantPermissions=grant_permissions,
            )
            logger.info(
                f"Granted permissions to dashboard {dashboard_id} for {len(grant_permissions)} principals"
            )

        return True

    except Exception as e:
        raise QuickSightDeploymentError(f"Failed to grant permissions: {e}")


def grant_dataset_permissions(
    dataset_id: str,
    aws_account_id: str,
    region: str,
    permissions: List[Dict[str, str]],
) -> bool:
    """Grant permissions to QuickSight dataset."""
    try:
        client = boto3.client("quicksight", region_name=region)

        expanded_perms = []
        for perm in permissions:
            expanded = expand_principal_wildcards(
                perm["principal"], aws_account_id, region
            )
            for exp_principal in expanded:
                expanded_perms.append(
                    {"Principal": exp_principal, "Actions": perm["actions"]}
                )

        client.update_data_set_permissions(
            AwsAccountId=aws_account_id,
            DataSetId=dataset_id,
            GrantPermissions=expanded_perms,
        )
        logger.info(f"Granted permissions to dataset {dataset_id}")
        return True
    except Exception as e:
        raise QuickSightDeploymentError(f"Failed to grant dataset permissions: {e}")


def grant_data_source_permissions(
    data_source_id: str,
    aws_account_id: str,
    region: str,
    permissions: List[Dict[str, str]],
) -> bool:
    """Grant permissions to QuickSight data source."""
    try:
        client = boto3.client("quicksight", region_name=region)

        expanded_perms = []
        for perm in permissions:
            expanded = expand_principal_wildcards(
                perm["principal"], aws_account_id, region
            )
            for exp_principal in expanded:
                expanded_perms.append(
                    {"Principal": exp_principal, "Actions": perm["actions"]}
                )

        client.update_data_source_permissions(
            AwsAccountId=aws_account_id,
            DataSourceId=data_source_id,
            GrantPermissions=expanded_perms,
        )
        logger.info(f"Granted permissions to data source {data_source_id}")
        return True
    except Exception as e:
        raise QuickSightDeploymentError(f"Failed to grant data source permissions: {e}")


def grant_asset_bundle_permissions(
    import_result: Dict[str, Any],
    aws_account_id: str,
    region: str,
    principal: str,
) -> None:
    """
    Grant permissions to all assets imported in a bundle.

    Args:
        import_result: Result from poll_import_job
        aws_account_id: AWS account ID
        region: AWS region
        principal: Principal ARN to grant permissions to
    """
    client = boto3.client("quicksight", region_name=region)

    created_arns = import_result.get("CreatedArns", [])

    for arn in created_arns:
        try:
            parts = arn.split(":")
            resource_part = parts[-1]
            resource_type, resource_id = resource_part.split("/", 1)

            logger.info(f"Granting permissions to {resource_type}: {resource_id}")

            if resource_type == "dashboard":
                client.update_dashboard_permissions(
                    AwsAccountId=aws_account_id,
                    DashboardId=resource_id,
                    GrantPermissions=[
                        {
                            "Principal": principal,
                            "Actions": [
                                "quicksight:DescribeDashboard",
                                "quicksight:QueryDashboard",
                                "quicksight:UpdateDashboard",
                                "quicksight:DeleteDashboard",
                            ],
                        }
                    ],
                )
            elif resource_type == "dataset":
                client.update_data_set_permissions(
                    AwsAccountId=aws_account_id,
                    DataSetId=resource_id,
                    GrantPermissions=[
                        {
                            "Principal": principal,
                            "Actions": [
                                "quicksight:DescribeDataSet",
                                "quicksight:PassDataSet",
                                "quicksight:DescribeIngestion",
                            ],
                        }
                    ],
                )
            elif resource_type == "datasource":
                client.update_data_source_permissions(
                    AwsAccountId=aws_account_id,
                    DataSourceId=resource_id,
                    GrantPermissions=[
                        {
                            "Principal": principal,
                            "Actions": [
                                "quicksight:DescribeDataSource",
                                "quicksight:DescribeDataSourcePermissions",
                                "quicksight:PassDataSource",
                                "quicksight:UpdateDataSource",
                                "quicksight:UpdateDataSourcePermissions",
                            ],
                        }
                    ],
                )

        except Exception as e:
            logger.warning(f"Failed to grant permissions to {arn}: {e}")


def expand_principal_wildcards(
    principal: str, account_id: str, region: str
) -> List[str]:
    """
    Expand wildcard patterns in QuickSight principal ARNs.

    Example: arn:aws:quicksight:us-east-2:*:user/default/Admin/*
    Returns: List of actual user ARNs matching the pattern
    """
    import boto3

    if "*" not in principal:
        return [principal]

    # Replace account wildcard
    principal = principal.replace(":*:", f":{account_id}:")

    # Check if there's a user wildcard
    if not principal.endswith("/*"):
        return [principal]

    # Extract the prefix pattern
    prefix = principal.split("user/default/")[-1].rstrip("/*")

    try:
        client = boto3.client("quicksight", region_name=region)
        response = client.list_users(AwsAccountId=account_id, Namespace="default")

        expanded = []
        for user in response.get("UserList", []):
            user_name = user["UserName"]
            if user_name.startswith(prefix):
                user_arn = user["Arn"]
                expanded.append(user_arn)

        return expanded if expanded else [principal]
    except Exception as e:
        logger.warning(f"Failed to expand wildcard {principal}: {e}")
        return [principal]


def _download_bundle(url_or_path: str) -> bytes:
    """Download asset bundle from URL or read from local file."""
    import os

    # Check if it's a local file path
    if os.path.exists(url_or_path):
        with open(url_or_path, "rb") as f:
            return f.read()

    # Otherwise treat as URL
    import requests

    response = requests.get(url_or_path, timeout=60)
    response.raise_for_status()
    return response.content


def trigger_dataset_ingestion(
    dataset_id: str,
    aws_account_id: str,
    region: str,
    wait: bool = False,
    timeout: int = 300,
    ingestion_type: str = "FULL_REFRESH",
) -> Dict[str, Any]:
    """
    Trigger QuickSight dataset ingestion to refresh data.

    Args:
        dataset_id: Dataset ID to refresh
        aws_account_id: AWS account ID
        region: AWS region
        wait: Whether to wait for ingestion to complete
        timeout: Maximum seconds to wait (default: 300)
        ingestion_type: FULL_REFRESH or INCREMENTAL_REFRESH (default: FULL_REFRESH)

    Returns:
        Dict with ingestion_id, status, and success

    Raises:
        QuickSightDeploymentError: If ingestion fails
    """
    try:
        client = boto3.client("quicksight", region_name=region)

        # Create ingestion
        ingestion_id = f"ingestion-{int(time.time())}"
        response = client.create_ingestion(
            DataSetId=dataset_id,
            IngestionId=ingestion_id,
            AwsAccountId=aws_account_id,
            IngestionType=ingestion_type,
        )

        logger.info(
            f"Started dataset ingestion: {ingestion_id} (type: {ingestion_type})"
        )

        result = {
            "ingestion_id": ingestion_id,
            "arn": response.get("Arn"),
            "status": response.get("IngestionStatus", "INITIALIZED"),
            "success": True,
            "dataset_id": dataset_id,
        }

        # Optionally wait for completion
        if wait:
            logger.info(f"Waiting for ingestion to complete (timeout: {timeout}s)...")
            start_time = time.time()

            while time.time() - start_time < timeout:
                status_response = client.describe_ingestion(
                    AwsAccountId=aws_account_id,
                    DataSetId=dataset_id,
                    IngestionId=ingestion_id,
                )

                status = status_response["Ingestion"]["IngestionStatus"]
                result["status"] = status

                if status == "COMPLETED":
                    logger.info("Ingestion completed successfully")
                    return result
                elif status in ["FAILED", "CANCELLED"]:
                    error_info = status_response["Ingestion"].get("ErrorInfo", {})
                    raise QuickSightDeploymentError(
                        f"Ingestion {status.lower()}: {error_info.get('Message', 'Unknown error')}"
                    )

                time.sleep(5)

            raise QuickSightDeploymentError(
                f"Ingestion timed out after {timeout}s (status: {result['status']})"
            )

        return result

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        raise QuickSightDeploymentError(
            f"Failed to trigger ingestion: {error_code} - {error_msg}"
        )


def list_datasets(
    aws_account_id: str,
    region: str,
) -> List[Dict[str, Any]]:
    """
    List all QuickSight datasets in the account.

    Args:
        aws_account_id: AWS account ID
        region: AWS region

    Returns:
        List of dataset summaries

    Raises:
        QuickSightDeploymentError: If listing fails
    """
    try:
        client = boto3.client("quicksight", region_name=region)
        datasets = []
        next_token = None

        while True:
            params = {"AwsAccountId": aws_account_id, "MaxResults": 100}
            if next_token:
                params["NextToken"] = next_token

            response = client.list_data_sets(**params)
            datasets.extend(response.get("DataSetSummaries", []))

            next_token = response.get("NextToken")
            if not next_token:
                break

        return datasets

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        raise QuickSightDeploymentError(
            f"Failed to trigger ingestion: {error_code} - {error_msg}"
        )
