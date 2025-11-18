"""Tests for workflow helper functions."""

import pytest
from unittest.mock import MagicMock, patch

from smus_cicd.helpers import airflow_serverless, datazone


class TestWorkflowNameGeneration:
    """Test workflow name generation helper."""

    def test_generate_workflow_name_basic(self):
        """Test basic workflow name generation."""
        result = airflow_serverless.generate_workflow_name(
            bundle_name="MyApp",
            project_name="test-project",
            dag_name="etl_pipeline"
        )
        assert result == "MyApp_test_project_etl_pipeline"

    def test_generate_workflow_name_with_hyphens(self):
        """Test workflow name generation with hyphens."""
        result = airflow_serverless.generate_workflow_name(
            bundle_name="my-app",
            project_name="test-project",
            dag_name="etl-pipeline"
        )
        assert result == "my_app_test_project_etl_pipeline"

    def test_generate_workflow_name_mixed(self):
        """Test workflow name generation with mixed characters."""
        result = airflow_serverless.generate_workflow_name(
            bundle_name="MyApp-v2",
            project_name="prod-analytics",
            dag_name="data-processing-dag"
        )
        assert result == "MyApp_v2_prod_analytics_data_processing_dag"


class TestWorkflowArnLookup:
    """Test workflow ARN lookup helper."""

    def test_find_workflow_arn_success(self):
        """Test successful workflow ARN lookup."""
        with patch("smus_cicd.helpers.airflow_serverless.list_workflows") as mock_list:
            mock_list.return_value = [
                {"name": "app_project_dag1", "workflow_arn": "arn:aws:airflow:us-east-1:123:workflow/app_project_dag1"},
                {"name": "app_project_dag2", "workflow_arn": "arn:aws:airflow:us-east-1:123:workflow/app_project_dag2"},
            ]

            result = airflow_serverless.find_workflow_arn(
                workflow_name="app_project_dag1",
                region="us-east-1"
            )

            assert result == "arn:aws:airflow:us-east-1:123:workflow/app_project_dag1"
            mock_list.assert_called_once_with(region="us-east-1", connection_info=None)

    def test_find_workflow_arn_not_found(self):
        """Test workflow ARN lookup when workflow not found."""
        with patch("smus_cicd.helpers.airflow_serverless.list_workflows") as mock_list:
            mock_list.return_value = [
                {"name": "app_project_dag1", "workflow_arn": "arn:aws:airflow:us-east-1:123:workflow/app_project_dag1"},
            ]

            with pytest.raises(Exception, match="Workflow 'nonexistent' not found"):
                airflow_serverless.find_workflow_arn(
                    workflow_name="nonexistent",
                    region="us-east-1"
                )


class TestWorkflowStartVerification:
    """Test workflow start verification helper."""

    def test_start_workflow_run_verified_success_immediate(self):
        """Test workflow start with immediate success status."""
        with patch("smus_cicd.helpers.airflow_serverless.start_workflow_run") as mock_start:
            mock_start.return_value = {
                "success": True,
                "run_id": "run123",
                "status": "STARTING",
                "workflow_arn": "arn:aws:airflow:us-east-1:123:workflow/test"
            }

            result = airflow_serverless.start_workflow_run_verified(
                workflow_arn="arn:aws:airflow:us-east-1:123:workflow/test",
                region="us-east-1",
                verify_started=True
            )

            assert result["success"] is True
            assert result["run_id"] == "run123"
            assert result["status"] == "STARTING"

    def test_start_workflow_run_verified_with_retry(self):
        """Test workflow start with status verification retry."""
        with patch("smus_cicd.helpers.airflow_serverless.start_workflow_run") as mock_start, \
             patch("smus_cicd.helpers.airflow_serverless.get_workflow_status") as mock_status, \
             patch("smus_cicd.helpers.airflow_serverless.time.sleep"):

            mock_start.return_value = {
                "success": True,
                "run_id": "run123",
                "status": "READY",  # Not a running state
                "workflow_arn": "arn:aws:airflow:us-east-1:123:workflow/test"
            }

            mock_status.return_value = {
                "success": True,
                "status": "RUNNING"  # After retry, it's running
            }

            result = airflow_serverless.start_workflow_run_verified(
                workflow_arn="arn:aws:airflow:us-east-1:123:workflow/test",
                region="us-east-1",
                verify_started=True,
                wait_seconds=10
            )

            assert result["success"] is True
            assert result["status"] == "RUNNING"
            mock_status.assert_called_once()

    def test_start_workflow_run_verified_failure(self):
        """Test workflow start verification failure."""
        with patch("smus_cicd.helpers.airflow_serverless.start_workflow_run") as mock_start, \
             patch("smus_cicd.helpers.airflow_serverless.get_workflow_status") as mock_status, \
             patch("smus_cicd.helpers.airflow_serverless.time.sleep"):

            mock_start.return_value = {
                "success": True,
                "run_id": "run123",
                "status": "READY",
                "workflow_arn": "arn:aws:airflow:us-east-1:123:workflow/test"
            }

            mock_status.return_value = {
                "success": True,
                "status": "READY"  # Still not running after retry
            }

            with pytest.raises(Exception, match="may not have actually started"):
                airflow_serverless.start_workflow_run_verified(
                    workflow_arn="arn:aws:airflow:us-east-1:123:workflow/test",
                    region="us-east-1",
                    verify_started=True
                )

    def test_start_workflow_run_verified_no_verification(self):
        """Test workflow start without verification."""
        with patch("smus_cicd.helpers.airflow_serverless.start_workflow_run") as mock_start:
            mock_start.return_value = {
                "success": True,
                "run_id": "run123",
                "status": "READY",
                "workflow_arn": "arn:aws:airflow:us-east-1:123:workflow/test"
            }

            result = airflow_serverless.start_workflow_run_verified(
                workflow_arn="arn:aws:airflow:us-east-1:123:workflow/test",
                region="us-east-1",
                verify_started=False  # Skip verification
            )

            assert result["success"] is True
            assert result["status"] == "READY"  # Status not changed


class TestWorkflowLogs:
    """Test workflow logs helper."""

    def test_get_workflow_logs(self):
        """Test workflow logs retrieval."""
        with patch("smus_cicd.helpers.airflow_serverless.get_cloudwatch_logs") as mock_logs:
            mock_logs.return_value = [
                {
                    "timestamp": 1700000000000,
                    "log_stream_name": "dag/task1",
                    "message": "Task started"
                },
                {
                    "timestamp": 1700000001000,
                    "log_stream_name": "dag/task2",
                    "message": "Task completed"
                }
            ]

            result = airflow_serverless.get_workflow_logs(
                workflow_arn="arn:aws:airflow:us-east-1:123:workflow/test_workflow",
                run_id="run123",
                region="us-east-1",
                max_lines=100
            )

            assert len(result) == 2
            assert "[dag/task1]" in result[0]
            assert "Task started" in result[0]
            assert "[dag/task2]" in result[1]
            assert "Task completed" in result[1]


class TestDataZoneConnectionDetection:
    """Test DataZone connection detection helpers."""

    def test_is_connection_serverless_airflow_true(self):
        """Test serverless Airflow connection detection (no MWAA ARN)."""
        with patch("smus_cicd.helpers.datazone._get_datazone_client") as mock_client:
            mock_dz = MagicMock()
            mock_client.return_value = mock_dz
            mock_dz.list_connections.return_value = {
                "items": [
                    {
                        "name": "default.workflow_serverless",
                        "type": "WORKFLOWS_MWAA",
                        "physicalEndpoints": []  # No MWAA ARN = serverless
                    }
                ]
            }

            result = datazone.is_connection_serverless_airflow(
                connection_name="default.workflow_serverless",
                domain_id="dzd_123",
                project_id="prj_456",
                region="us-east-1"
            )

            assert result is True

    def test_is_connection_serverless_airflow_false(self):
        """Test MWAA connection detection (has MWAA ARN)."""
        with patch("smus_cicd.helpers.datazone._get_datazone_client") as mock_client:
            mock_dz = MagicMock()
            mock_client.return_value = mock_dz
            mock_dz.list_connections.return_value = {
                "items": [
                    {
                        "name": "default.workflow_mwaa",
                        "type": "WORKFLOWS_MWAA",
                        "physicalEndpoints": [
                            {
                                "glueConnection": "arn:aws:airflow:us-east-1:123:environment/my-mwaa"
                            }
                        ]
                    }
                ]
            }

            result = datazone.is_connection_serverless_airflow(
                connection_name="default.workflow_mwaa",
                domain_id="dzd_123",
                project_id="prj_456",
                region="us-east-1"
            )

            assert result is False

    def test_target_uses_serverless_airflow_true(self):
        """Test target uses serverless Airflow."""
        manifest = MagicMock()
        manifest.content.workflows = [
            {"connectionName": "default.workflow_serverless"}
        ]

        target_config = MagicMock()
        target_config.domain.region = "us-east-1"
        target_config.domain.name = "test-domain"
        target_config.domain.tags = {}
        target_config.project.name = "test-project"

        with patch("smus_cicd.helpers.datazone.resolve_domain_id") as mock_resolve, \
             patch("smus_cicd.helpers.datazone.get_project_id_by_name") as mock_project, \
             patch("smus_cicd.helpers.datazone.is_connection_serverless_airflow") as mock_check:

            mock_resolve.return_value = ("dzd_123", "test-domain")
            mock_project.return_value = "prj_456"
            mock_check.return_value = True

            result = datazone.target_uses_serverless_airflow(manifest, target_config)

            assert result is True
            mock_check.assert_called_once()

    def test_target_uses_serverless_airflow_no_workflows(self):
        """Test target with no workflows."""
        manifest = MagicMock()
        manifest.content.workflows = None

        target_config = MagicMock()

        result = datazone.target_uses_serverless_airflow(manifest, target_config)

        assert result is False
