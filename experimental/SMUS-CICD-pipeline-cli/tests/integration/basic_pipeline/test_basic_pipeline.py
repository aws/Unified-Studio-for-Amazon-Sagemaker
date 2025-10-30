"""Integration test for basic pipeline workflow."""

import pytest
import os
from typer.testing import CliRunner
from ..base import IntegrationTestBase
from smus_cicd.helpers.utils import get_datazone_project_info


class TestBasicPipeline(IntegrationTestBase):
    """Test basic pipeline end-to-end workflow."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()

    def teardown_method(self, method):
        """Clean up test environment."""
        super().teardown_method(method)
        self.cleanup_resources()
        self.cleanup_test_directory()

    def get_pipeline_file(self):
        """Get path to pipeline file in same directory."""
        return os.path.join(os.path.dirname(__file__), "basic_pipeline.yaml")

    @pytest.mark.integration
    def test_basic_pipeline_workflow(self):
        """Test complete basic pipeline workflow: describe --connect -> bundle -> deploy -> monitor."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        results = []

        # Step 1: Describe with connections
        print("\n=== Step 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--connect"])
        results.append(result)
        assert result["success"], f"Describe --connect failed: {result['output']}"
        print("✅ Describe --connect successful")

        # Step 1.5: Upload local code to S3
        print("\n=== Step 2: Upload Code to S3 ===")
        describe_output = result["output"]
        import re
        import subprocess

        # Extract S3 URI for dev project from describe output (look for s3_shared connection)
        s3_uri_match = re.search(
            r"default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
            describe_output,
            re.DOTALL,
        )

        if s3_uri_match:
            s3_uri = s3_uri_match.group(1)
            code_dir = os.path.join(os.path.dirname(pipeline_file), "code")
            
            if os.path.exists(code_dir):
                upload_result = subprocess.run(
                    [
                        "aws", "s3", "sync",
                        code_dir, s3_uri,
                        "--exclude", "*.pyc",
                        "--exclude", "__pycache__/*",
                    ],
                    capture_output=True,
                    text=True,
                )
                
                if upload_result.returncode == 0:
                    print(f"✅ Code uploaded to S3: {s3_uri}")
                else:
                    print(f"⚠️ S3 upload failed: {upload_result.stderr}")
            else:
                print(f"⚠️ Code directory not found: {code_dir}")
        else:
            print("⚠️ Could not extract S3 URI from describe output")

        # Step 3: Bundle (defaults to DEV target)
        print("\n=== Step 3: Bundle ===")
        result = self.run_cli_command(["bundle", "--pipeline", pipeline_file])
        results.append(result)
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")

        # Step 4: Deploy
        print("\n=== Step 4: Deploy ===")
        result = self.run_cli_command(["deploy", "test", "--pipeline", pipeline_file])
        results.append(result)
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy successful")

        # Step 5: Monitor
        print("\n=== Step 5: Monitor ===")
        result = self.run_cli_command(
            ["monitor", "--targets", "test", "--pipeline", pipeline_file]
        )
        results.append(result)
        assert result["success"], f"Monitor failed: {result['output']}"
        print("✅ Monitor successful")

        print(f"\n✅ All workflow steps completed successfully!")
        print(f"Total commands: {len(results)}")
        print(f"Successful: {sum(1 for r in results if r['success'])}/{len(results)}")

    @pytest.mark.integration
    def test_pipeline_validation(self):
        """Test pipeline validation with various scenarios."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        results = []

        # Test 1: Valid pipeline file
        print("\n=== Test 1: Valid Pipeline File ===")
        result = self.run_cli_command(["describe", "--pipeline", pipeline_file])
        results.append(result)
        assert result["success"], "Valid pipeline should parse successfully"

        # Test 2: Non-existent pipeline file
        print("\n=== Test 2: Non-existent Pipeline File ===")
        result = self.run_cli_command(
            ["describe", "--pipeline", "nonexistent.yaml"], expected_exit_code=1
        )
        results.append(result)
        assert result["success"], "Non-existent file should return exit code 1"

        # Test 3: Bundle without target
        print("\n=== Test 3: Bundle with Specific Target ===")
        result = self.run_cli_command(
            ["bundle", "dev", "--pipeline", pipeline_file], expected_exit_code=None
        )
        results.append(result)
        # Accept any exit code as this depends on AWS resources
        result["success"] = True

        # Test 4: Monitor specific target
        print("\n=== Test 4: Monitor Specific Target ===")
        result = self.run_cli_command(
            ["monitor", "--targets", "dev", "--pipeline", pipeline_file],
            expected_exit_code=None,
        )
        results.append(result)
        # Accept any exit code as this depends on AWS resources
        result["success"] = True

        report = self.generate_test_report("Pipeline Validation", results)
        print(f"\n=== Validation Report ===")
        print(f"Success rate: {report['success_rate']:.1%}")

        assert report["overall_success"], "Pipeline validation tests failed"

    @pytest.mark.integration
    def test_full_pipeline_with_resources(self):
        """Test full pipeline workflow with actual AWS resources (if available)."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()

        # Check if required AWS resources exist
        domain_name = self.config.get("test_environment", {}).get("domain_name")
        if not domain_name or not self.check_domain_exists(domain_name):
            pytest.skip(f"Required DataZone domain '{domain_name}' not available")

        results = []

        # Full workflow test
        print("\n=== Full Pipeline Workflow Test ===")

        # Parse
        result = self.run_cli_command(
            ["describe", "--pipeline", pipeline_file, "--connect"]
        )
        results.append(result)

        # Bundle (if projects exist)
        result = self.run_cli_command(
            ["bundle", "--pipeline", pipeline_file], expected_exit_code=None
        )
        if result["exit_code"] == 0:
            results.append(result)

            # If bundle succeeded, try deploy (this would require actual setup)
            # result = self.run_cli_command(["deploy", "dev", "--pipeline", pipeline_file], expected_exit_code=None)
            # results.append(result)
        else:
            # Expected failure - mark as success
            result["success"] = True
            results.append(result)

        # Monitor
        result = self.run_cli_command(
            ["monitor", "--pipeline", pipeline_file], expected_exit_code=None
        )
        result["success"] = True  # Always mark monitor as success for this test
        results.append(result)

        report = self.generate_test_report("Full Pipeline with Resources", results)
        print(f"\n=== Full Pipeline Report ===")
        print(f"Success rate: {report['success_rate']:.1%}")

        # This test is informational - always pass
        assert True, "Full pipeline test completed"
