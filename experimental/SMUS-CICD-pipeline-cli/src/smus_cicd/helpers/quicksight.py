"""QuickSight dashboard deployment helper."""

import time
from typing import Any, Dict, List, Optional

import boto3

from .logger import get_logger

logger = get_logger("quicksight")


class QuickSightDeploymentError(Exception):
    """Exception raised for QuickSight deployment errors."""

    pass


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
            grant_permissions.append(
                {
                    "Principal": perm.get("principal", ""),
                    "Actions": perm.get("actions", ["quicksight:DescribeDashboard"]),
                }
            )

        client.update_dashboard_permissions(
            AwsAccountId=aws_account_id,
            DashboardId=dashboard_id,
            GrantPermissions=grant_permissions,
        )

        logger.info(f"Granted permissions to dashboard {dashboard_id}")
        return True

    except Exception as e:
        raise QuickSightDeploymentError(f"Failed to grant permissions: {e}")


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
                                "quicksight:PassDataSource",
                            ],
                        }
                    ],
                )

        except Exception as e:
            logger.warning(f"Failed to grant permissions to {arn}: {e}")


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
