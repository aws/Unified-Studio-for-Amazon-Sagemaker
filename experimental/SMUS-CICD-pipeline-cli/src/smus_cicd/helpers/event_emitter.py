"""EventBridge event emitter for deployment monitoring."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .eventbridge_client import EventBridgeEmitter
from .logger import get_logger

logger = get_logger("deployment_event_emitter")


class DeploymentEventEmitter(EventBridgeEmitter):
    """Emit deployment lifecycle events to EventBridge."""

    EVENT_SOURCE = "com.amazon.smus.cicd"
    EVENT_VERSION = "1.0"

    def emit(
        self,
        detail_type: str,
        detail: Dict[str, Any],
        resources: Optional[List[str]] = None,
    ) -> bool:
        """
        Emit event to EventBridge.

        Args:
            detail_type: Event detail type
            detail: Event detail payload
            resources: Optional list of resource ARNs

        Returns:
            True if event emitted successfully, False otherwise
        """
        return self.emit_event(self.EVENT_SOURCE, detail_type, detail, resources)

    def _build_base_detail(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        stage: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build base event detail structure."""
        detail = {
            "version": self.EVENT_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "applicationName": bundle_name,
            "stage": stage,
            "status": status,
            "target": target,
        }

        if metadata:
            detail["metadata"] = metadata

        return detail

    def deploy_started(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        bundle_info: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit deploy started event."""
        detail = self._build_base_detail(
            bundle_name, target, "deploy", "started", metadata
        )
        detail["bundle"] = bundle_info

        return self.emit("SMUS-CICD-Deploy-Started", detail)

    def deploy_completed(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        deployment_summary: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit deploy completed event."""
        detail = self._build_base_detail(
            bundle_name, target, "deploy", "completed", metadata
        )
        detail.update(deployment_summary)

        return self.emit("SMUS-CICD-Deploy-Completed", detail)

    def deploy_failed(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        error: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit deploy failed event."""
        detail = self._build_base_detail(
            bundle_name, target, "deploy", "failed", metadata
        )
        detail["error"] = error

        return self.emit("SMUS-CICD-Deploy-Failed", detail)

    def project_init_started(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        project_config: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit project initialization started event."""
        detail = self._build_base_detail(
            bundle_name, target, "project-init", "started", metadata
        )
        detail["projectConfig"] = project_config

        return self.emit("SMUS-CICD-Deploy-ProjectInitialization-Started", detail)

    def project_init_completed(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        project_info: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit project initialization completed event."""
        detail = self._build_base_detail(
            bundle_name, target, "project-init", "completed", metadata
        )
        detail["projectInfo"] = project_info

        return self.emit("SMUS-CICD-Deploy-ProjectInitialization-Completed", detail)

    def project_init_failed(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        error: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit project initialization failed event."""
        detail = self._build_base_detail(
            bundle_name, target, "project-init", "failed", metadata
        )
        detail["error"] = error

        return self.emit("SMUS-CICD-Deploy-ProjectInitialization-Failed", detail)

    def bundle_upload_started(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        bundle_info: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit bundle upload started event."""
        detail = self._build_base_detail(
            bundle_name, target, "bundle-upload", "started", metadata
        )
        detail["bundle"] = bundle_info

        return self.emit("SMUS-CICD-Deploy-BundleUpload-Started", detail)

    def bundle_upload_completed(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        deployment_results: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit bundle upload completed event."""
        detail = self._build_base_detail(
            bundle_name, target, "bundle-upload", "completed", metadata
        )
        detail["deployment"] = deployment_results

        return self.emit("SMUS-CICD-Deploy-BundleUpload-Completed", detail)

    def bundle_upload_failed(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        error: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit bundle upload failed event."""
        detail = self._build_base_detail(
            bundle_name, target, "bundle-upload", "failed", metadata
        )
        detail["error"] = error

        return self.emit("SMUS-CICD-Deploy-BundleUpload-Failed", detail)

    def workflow_creation_started(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        workflows: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit workflow creation started event."""
        detail = self._build_base_detail(
            bundle_name, target, "workflow-creation", "started", metadata
        )
        detail["workflows"] = workflows

        return self.emit("SMUS-CICD-Deploy-WorkflowCreation-Started", detail)

    def workflow_creation_completed(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        workflow_results: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit workflow creation completed event."""
        detail = self._build_base_detail(
            bundle_name, target, "workflow-creation", "completed", metadata
        )
        detail["workflows"] = workflow_results

        return self.emit("SMUS-CICD-Deploy-WorkflowCreation-Completed", detail)

    def workflow_creation_failed(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        error: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit workflow creation failed event."""
        detail = self._build_base_detail(
            bundle_name, target, "workflow-creation", "failed", metadata
        )
        detail["error"] = error

        return self.emit("SMUS-CICD-Deploy-WorkflowCreation-Failed", detail)

    def catalog_assets_started(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        asset_configs: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit catalog assets processing started event."""
        detail = self._build_base_detail(
            bundle_name, target, "catalog-assets", "started", metadata
        )
        detail["assetConfigs"] = asset_configs

        return self.emit("SMUS-CICD-Deploy-CatalogAssets-Started", detail)

    def catalog_assets_completed(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        asset_results: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit catalog assets processing completed event."""
        detail = self._build_base_detail(
            bundle_name, target, "catalog-assets", "completed", metadata
        )
        detail["catalogAssets"] = asset_results

        return self.emit("SMUS-CICD-Deploy-CatalogAssets-Completed", detail)

    def catalog_assets_failed(
        self,
        bundle_name: str,
        target: Dict[str, Any],
        error: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit catalog assets processing failed event."""
        detail = self._build_base_detail(
            bundle_name, target, "catalog-assets", "failed", metadata
        )
        detail["error"] = error

        return self.emit("SMUS-CICD-Deploy-CatalogAssets-Failed", detail)


# Backward compatibility alias
EventEmitter = DeploymentEventEmitter
