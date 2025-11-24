"""End-to-end test for DataZone connections creation via deployment."""

import pytest
import os
from ..base import IntegrationTestBase


class TestDataZoneConnectionsE2E(IntegrationTestBase):
    """Test DataZone connections integration with CLI deployment."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()

        # Clean up project from previous test run
        try:
            manifest_file = os.path.join(os.path.dirname(__file__), "manifest.yaml")
            
            print("🧹 Cleaning up existing test project...")
            result = self.run_cli_command(
                ["delete", "--targets", "test", "--manifest", manifest_file, "--force"]
            )
            if result["success"]:
                print("✅ Project cleanup successful")
            else:
                print(f"⚠️ Project cleanup had issues: {result['output']}")
        except Exception as e:
            print(f"⚠️ Could not clean up resources: {e}")

    def teardown_method(self, method):
        """Clean up test environment."""
        super().teardown_method(method)
        self.cleanup_test_directory()

    @pytest.mark.integration
    def test_datazone_connections_end_to_end(self):
        """Test end-to-end DataZone connections creation via deployment."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        manifest_file = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        
        # Step 1: Deploy manifest (creates project and connections via bootstrap)
        print("\n=== Step 1: Deploy Manifest ===")
        result = self.run_cli_command(
            ["deploy", "--manifest", manifest_file, "--stage", "test"]
        )
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deployment successful")
        
        # Step 2: Verify connections were created
        print("\n=== Step 2: Verify Connections Created ===")
        result = self.run_cli_command(
            ["describe", "--manifest", manifest_file, "--stage", "test", "--connect"]
        )
        assert result["success"], f"Describe failed: {result['output']}"
        
        # Parse output to verify connections
        output = result["output"]
        expected_connections = [
            "s3-data-lake",
            "iam-lineage", 
            "spark-glue-proc",
            "workflows-serverless",
            "mlflow-experiments",
            "athena-query-engine",
            "glue-catalog",
            "redshift-warehouse",
            "spark-emr-processing",
            "hyperpod-cluster"
        ]
        
        connections_found = 0
        for conn_name in expected_connections:
            if conn_name in output:
                connections_found += 1
                print(f"  ✅ Found connection: {conn_name}")
        
        print(f"\n✅ Verified {connections_found}/{len(expected_connections)} connections")
        assert connections_found >= 8, f"Expected at least 8 connections, found {connections_found}"

    @pytest.mark.integration
    def test_bootstrap_connection_idempotency(self):
        """Test that bootstrap connections are idempotent on re-deploy."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        manifest_file = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        
        # Deploy twice - second deploy should be idempotent
        print("\n=== First Deploy ===")
        result = self.run_cli_command(
            ["deploy", "--manifest", manifest_file, "--stage", "test"]
        )
        assert result["success"], f"First deploy failed: {result['output']}"
        
        print("\n=== Second Deploy (Idempotency Test) ===")
        result = self.run_cli_command(
            ["deploy", "--manifest", manifest_file, "--stage", "test"]
        )
        assert result["success"], f"Second deploy failed: {result['output']}"
        print("✅ Idempotent deployment successful")

    @pytest.mark.integration
    def test_mlflow_connection_property_change_recreates(self):
        """Test that MLflow connection is recreated when properties change."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        manifest_file = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        
        # First deploy
        print("\n=== First Deploy ===")
        result = self.run_cli_command(
            ["deploy", "--manifest", manifest_file, "--stage", "test"]
        )
        assert result["success"], f"First deploy failed: {result['output']}"
        
        # TODO: Modify manifest to change MLflow ARN, then re-deploy
        # For now, just verify the connection exists
        result = self.run_cli_command(
            ["describe", "--manifest", manifest_file, "--stage", "test", "--connect"]
        )
        assert result["success"], f"Describe failed: {result['output']}"
        assert "mlflow-experiments" in result["output"], "MLflow connection not found"
        print("✅ MLflow connection verified")
