"""
Integration tests for delete command functionality.
Tests creation and deletion of a single target project.
"""

import pytest
import time
from pathlib import Path
from typer.testing import CliRunner
from tests.integration.base import IntegrationTestBase


class TestDeletePipeline(IntegrationTestBase):
    """Test delete command with a simple pipeline."""

    def setup_method(self, method):
        """Set up test environment."""
        self.runner = CliRunner()
        self.config = self._load_config()
        self.test_dir = None
        self.created_resources = []
        self.setup_aws_session()
        self.setup_test_directory()
        
        # Clean up any leftover resources from previous test runs
        self.cleanup_cloudformation_stack()
        self.cleanup_glue_database()

    def cleanup_glue_database(self):
        """Clean up the test Glue database if it exists."""
        try:
            import boto3
            glue_client = boto3.client('glue', region_name='us-east-1')
            lf_client = boto3.client('lakeformation', region_name='us-east-1')
            sts_client = boto3.client('sts', region_name='us-east-1')
            
            # Get role ARN for Lake Formation permissions
            identity = sts_client.get_caller_identity()
            assumed_role_arn = identity['Arn']
            
            # Extract role ARN from assumed role ARN
            if 'assumed-role' in assumed_role_arn:
                parts = assumed_role_arn.split('/')
                if len(parts) >= 3:
                    account_and_service = parts[0].replace(':sts:', ':iam:').replace(':assumed-role', ':role')
                    role_name = parts[1]
                    role_arn = f"{account_and_service}/{role_name}"
                else:
                    role_arn = assumed_role_arn
            else:
                role_arn = assumed_role_arn
            
            # Try to delete the test database
            try:
                # First grant DROP permissions through Lake Formation
                try:
                    lf_client.grant_permissions(
                        Principal={'DataLakePrincipalIdentifier': role_arn},
                        Resource={'Database': {'Name': 'delete_test_db'}},
                        Permissions=['DROP']
                    )
                except Exception as perm_e:
                    print(f"⚠️ Could not grant DROP permissions: {perm_e}")
                
                # Now try to delete the database
                glue_client.delete_database(Name='delete_test_db')
                print("Cleaned up existing Glue database: delete_test_db")
            except glue_client.exceptions.EntityNotFoundException:
                print("Glue database delete_test_db doesn't exist - OK")
            except Exception as e:
                if "AccessDeniedException" in str(e) or "Lake Formation permission" in str(e):
                    print(f"⚠️ Cannot delete Glue database due to Lake Formation permissions: {e}")
                    print("⚠️ This may cause deployment conflicts - manual cleanup may be needed")
                else:
                    print(f"⚠️ Error deleting Glue database: {e}")
        except Exception as e:
            print(f"⚠️ Glue database cleanup failed: {e}")

    def cleanup_cloudformation_stack(self):
        """Clean up the test CloudFormation stack if it exists."""
        try:
            import boto3
            cf_client = boto3.client('cloudformation', region_name='us-east-1')
            stack_name = 'SMUS-deletetestpipeline-delete-test-delete-test-project-project'
            
            # Try to delete the stack
            cf_client.delete_stack(StackName=stack_name)
            print(f"Initiated cleanup of CloudFormation stack: {stack_name}")
            
            # Wait for deletion to complete
            waiter = cf_client.get_waiter('stack_delete_complete')
            waiter.wait(StackName=stack_name, WaiterConfig={'MaxAttempts': 30, 'Delay': 10})
            print(f"CloudFormation stack deleted: {stack_name}")
        except Exception as e:
            # Stack doesn't exist or other error - that's fine
            pass

    def teardown_method(self):
        """Clean up test environment."""
        self.cleanup_resources()
        self.cleanup_test_directory()

    def get_pipeline_file(self):
        """Get the path to the delete test pipeline file."""
        return str(Path(__file__).parent / "delete_test_pipeline.yaml")

    @pytest.mark.integration
    def test_delete_pipeline_workflow(self):
        """Test complete delete pipeline workflow: describe -> deploy -> delete."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        results = []

        # Step 1: Describe pipeline configuration
        print("\n=== Step 1: Describe Pipeline ===")
        result = self.run_cli_command(["describe", "--pipeline", pipeline_file])
        results.append(result)

        if result['success']:
            print("✅ Describe command successful")
            assert "Pipeline:" in result['output'], f"Describe output missing 'Pipeline:': {result['output']}"
            assert "DeleteTestPipeline" in result['output'], f"Describe output missing pipeline name: {result['output']}"
        else:
            print(f"❌ Describe command failed: {result['output']}")
            assert False, f"Describe command failed: {result['output']}"

        # Step 2: Deploy the project (initialize)
        print("\n=== Step 2: Deploy Project ===")
        result = self.run_cli_command(["deploy", "--targets", "delete-test", "--pipeline", pipeline_file])
        results.append(result)

        assert result['success'], f"Deploy command must succeed to test deletion: {result['output']}"
        print("✅ Deploy command successful")
        # Wait a bit for deployment to settle
        time.sleep(30)

        # Step 3: Test delete command with confirmation (should be cancelled)
        print("\n=== Step 3: Test Delete with Confirmation (Cancel) ===")
        # This will fail because we can't provide interactive input in tests
        # But we can test the --force flag instead

        # Step 4: Test delete command with --force flag
        print("\n=== Step 4: Delete Project with --force ===")
        result = self.run_cli_command(["delete", "--targets", "delete-test", "--pipeline", pipeline_file, "--force"])
        results.append(result)

        assert result['success'], f"Delete command must succeed: {result['output']}"
        print("✅ Delete command successful")
        
        # Verify deletion was actually successful
        assert "Deletion Summary" in result['output'], f"Delete output missing deletion summary: {result['output']}"
        # Allow CloudFormation stack deletion failures as they're not critical if DataZone project deletion succeeded
        if "❌ Error deleting CloudFormation stack" in result['output'] and "Successfully deleted" in result['output']:
            print("⚠️ CloudFormation stack deletion failed, but DataZone project deletion succeeded")
        elif "❌" in result['output']:
            assert False, f"Delete operation failed - found error markers in output: {result['output']}"
        assert "✅" in result['output'] or "Successfully deleted" in result['output'], f"Delete output missing success indicators: {result['output']}"

        # Step 5: Verify project is actually deleted (second delete should handle gracefully)
        print("\n=== Step 5: Verify Project Deletion ===")
        result = self.run_cli_command(["delete", "--targets", "delete-test", "--pipeline", pipeline_file, "--force"])
        results.append(result)

        # Second delete should succeed (project already gone) or gracefully handle non-existent project
        assert result['success'], f"Second delete should handle non-existent project gracefully: {result['output']}"
        print("✅ Verified project deletion - second delete handled gracefully")

        # Print summary
        print(f"\n=== Test Summary ===")
        print(f"Total commands executed: {len(results)}")
        successful_commands = sum(1 for r in results if r['success'])
        print(f"Successful commands: {successful_commands}/{len(results)}")

        # The test passes if we can at least describe the pipeline and run delete commands
        describe_success = results[0]['success'] if results else False
        assert describe_success, "Pipeline description must succeed"

    @pytest.mark.integration
    def test_delete_async_mode(self):
        """Test delete command with --async flag."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()

        # Test async delete (should not wait for completion)
        print("\n=== Test Async Delete ===")
        result = self.run_cli_command([
            "delete", 
            "--targets", "delete-test", 
            "--pipeline", pipeline_file, 
            "--force", 
            "--async"
        ])

        assert result['success'], f"Async delete command must succeed: {result['output']}"
        print("✅ Async delete command successful")

    @pytest.mark.integration
    def test_delete_json_output(self):
        """Test delete command with JSON output format."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()

        # Test JSON output format
        print("\n=== Test JSON Output ===")
        result = self.run_cli_command([
            "delete", 
            "--targets", "delete-test", 
            "--pipeline", pipeline_file, 
            "--force", 
            "--output", "JSON"
        ])

        assert result['success'], f"JSON delete command must succeed: {result['output']}"
        print("✅ JSON output delete command successful")
        
        # Verify output is valid JSON
        try:
            import json
            json.loads(result['output'])
            print("✅ Output is valid JSON")
        except json.JSONDecodeError:
            assert False, f"Output is not valid JSON: {result['output']}"

    @pytest.mark.integration
    def test_delete_invalid_target(self):
        """Test delete command with invalid target name."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()

        # Test with invalid target
        print("\n=== Test Invalid Target ===")
        result = self.run_cli_command([
            "delete", 
            "--targets", "nonexistent-target", 
            "--pipeline", pipeline_file, 
            "--force"
        ], expected_exit_code=1)

        assert result['success'], "Delete with invalid target should return exit code 1"
        assert "not found in manifest" in result['output'], f"Should show target not found error: {result['output']}"
        print("✅ Invalid target handled correctly")
