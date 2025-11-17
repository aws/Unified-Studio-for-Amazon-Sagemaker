"""QuickSight bootstrap action handler."""

from typing import Any, Dict, List

from ...helpers import quicksight
from ...helpers.logger import get_logger
from ..models import BootstrapAction

logger = get_logger("bootstrap.handlers.quicksight")


def handle_quicksight_action(
    action: BootstrapAction, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle QuickSight actions."""
    service, api = action.type.split(".", 1)

    if api == "refresh_dataset":
        return refresh_dataset(action, context)
    else:
        raise ValueError(f"Unknown QuickSight action: {api}")


def refresh_dataset(action: BootstrapAction, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trigger QuickSight dataset ingestion to refresh data.

    Action parameters:
        refreshScope: IMPORTED (default), ALL, or SPECIFIC
        datasetIds: List of dataset IDs (required if refreshScope=SPECIFIC)
        ingestionType: FULL_REFRESH (default) or INCREMENTAL_REFRESH
        wait: Whether to wait for completion (optional, default: false)
        timeout: Maximum seconds to wait (optional, default: 300)
        region: AWS region override (optional)
    """
    target_config = context.get("target_config")
    if not target_config:
        raise ValueError("Missing target_config in context")

    # Get AWS account ID from current session
    import boto3
    aws_account_id = boto3.client("sts").get_caller_identity()["Account"]

    # Get parameters
    refresh_scope = action.parameters.get("refreshScope", "IMPORTED")
    dataset_ids = action.parameters.get("datasetIds", [])
    ingestion_type = action.parameters.get("ingestionType", "FULL_REFRESH")
    wait = action.parameters.get("wait", False)
    timeout = action.parameters.get("timeout", 300)
    region = action.parameters.get("region") or target_config.domain.region

    # Validate parameters
    if refresh_scope not in ["IMPORTED", "ALL", "SPECIFIC"]:
        raise ValueError(
            f"refreshScope must be IMPORTED, ALL, or SPECIFIC (got: {refresh_scope})"
        )

    if refresh_scope == "SPECIFIC" and not dataset_ids:
        raise ValueError("datasetIds is required when refreshScope=SPECIFIC")

    if ingestion_type not in ["FULL_REFRESH", "INCREMENTAL_REFRESH"]:
        raise ValueError(
            f"ingestionType must be FULL_REFRESH or INCREMENTAL_REFRESH (got: {ingestion_type})"
        )

    # Determine which datasets to refresh
    datasets_to_refresh = []

    if refresh_scope == "SPECIFIC":
        datasets_to_refresh = dataset_ids
        logger.info(f"Refreshing {len(datasets_to_refresh)} specific datasets")

    elif refresh_scope == "ALL":
        # Get all datasets in the account
        all_datasets = quicksight.list_datasets(
            aws_account_id=aws_account_id, region=region
        )
        datasets_to_refresh = [ds["DataSetId"] for ds in all_datasets]
        logger.info(f"Refreshing ALL {len(datasets_to_refresh)} datasets in account")

    elif refresh_scope == "IMPORTED":
        # Get datasets imported by deploy command from context
        config = context.get("config", {})
        imported_datasets = config.get("imported_quicksight_datasets", [])
        
        if not imported_datasets:
            logger.warning("No imported QuickSight datasets found in deployment context, skipping refresh")
            return {
                "action": "quicksight.refresh_dataset",
                "refresh_scope": refresh_scope,
                "datasets_refreshed": 0,
                "results": [],
            }
        
        datasets_to_refresh = imported_datasets
        logger.info(f"Refreshing {len(datasets_to_refresh)} imported datasets")

    # Trigger ingestion for each dataset
    results = []
    for dataset_id in datasets_to_refresh:
        try:
            logger.info(f"Triggering ingestion for dataset: {dataset_id}")
            result = quicksight.trigger_dataset_ingestion(
                dataset_id=dataset_id,
                aws_account_id=aws_account_id,
                region=region,
                wait=wait,
                timeout=timeout,
                ingestion_type=ingestion_type,
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to refresh dataset {dataset_id}: {e}")
            results.append({
                "dataset_id": dataset_id,
                "success": False,
                "error": str(e),
            })

    successful = sum(1 for r in results if r.get("success", False))
    logger.info(
        f"Dataset refresh complete: {successful}/{len(results)} successful"
    )

    return {
        "action": "quicksight.refresh_dataset",
        "refresh_scope": refresh_scope,
        "ingestion_type": ingestion_type,
        "datasets_refreshed": successful,
        "total_datasets": len(results),
        "results": results,
    }
