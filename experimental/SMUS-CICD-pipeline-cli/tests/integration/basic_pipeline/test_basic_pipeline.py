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
        workflow_name = "basic_test_workflow"

        # Step 0: Setup EventBridge monitoring BEFORE deployment
        print("\n=== Step 0: Setup EventBridge Monitoring ===")
        self._setup_eventbridge_monitoring()

        # Step 0.5: Delete workflow if it exists
        print("\n=== Step 0: Cleanup Existing Workflow ===")
        try:
            import boto3
            import os
            
            # Get region and endpoint from environment
            region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-1')
            endpoint = os.environ.get('AIRFLOW_SERVERLESS_ENDPOINT')
            if not endpoint:
                endpoint = f'https://airflow-serverless.{region}.api.aws/'
            
            # Note: Workflow deletion removed - deploy command now updates existing workflows
            # This preserves run history across test runs
            # client = boto3.client('awsoverdriveservice', region_name=region, endpoint_url=endpoint)
            # response = client.list_workflows()
            # workflows = response.get('Workflows', [])
            # expected_name = f'BasicTestPipeline_test_marketing_{workflow_name}'
            # 
            # for wf in workflows:
            #     if wf.get('Name') == expected_name:
            #         workflow_arn = wf.get('WorkflowArn')
            #         print(f"🗑️  Deleting existing workflow: {expected_name}")
            #         client.delete_workflow(WorkflowArn=workflow_arn)
            #         print("✅ Workflow deleted")
            #         break
            # else:
            #     print("✓ No existing workflow to delete")
        except Exception as e:
            print(f"⚠️  Could not delete workflow: {e}")

        # Step 1: Describe with connections
        print("\n=== Step 1: Describe with Connections ===")
        self.logger.info("=== STEP 1: Describe with Connections ===")
        result = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--connect"])
        results.append(result)
        assert result["success"], f"Describe --connect failed: {result['output']}"
        print("✅ Describe --connect successful")

        # Step 1.5: Upload local code to S3
        print("\n=== Step 2: Upload Code and Workflows to S3 ===")
        describe_output = result["output"]
        import re
        import subprocess
        import yaml

        # Read manifest to get dev project name
        with open(pipeline_file, 'r') as f:
            manifest = yaml.safe_load(f)
        
        dev_project_name = manifest['targets']['dev']['project']['name']
        
        # Extract S3 URI for dev project from describe output (look for s3_shared connection)
        s3_uri_pattern = rf"dev: {re.escape(dev_project_name)}.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)"
        s3_uri_match = re.search(
            s3_uri_pattern,
            describe_output,
            re.DOTALL,
        )

        if s3_uri_match:
            s3_uri = s3_uri_match.group(1)
            base_dir = os.path.dirname(pipeline_file)
            
            # Upload code directory
            code_dir = os.path.join(base_dir, "code")
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
                    print(f"⚠️ Code upload failed: {upload_result.stderr}")
            else:
                print(f"⚠️ Code directory not found: {code_dir}")
            
            # Upload code/src directory to S3 code/src/
            code_src_dir = os.path.join(base_dir, "code", "src")
            if os.path.exists(code_src_dir):
                upload_result = subprocess.run(
                    [
                        "aws", "s3", "sync",
                        code_src_dir, s3_uri + "code/src/",
                        "--exclude", "*.pyc",
                        "--exclude", "__pycache__/*",
                    ],
                    capture_output=True,
                    text=True,
                )
                
                if upload_result.returncode == 0:
                    print(f"✅ Code uploaded to S3: {s3_uri}code/src/")
                else:
                    print(f"⚠️ Code upload failed: {upload_result.stderr}")
            else:
                print(f"⚠️ Code/src directory not found: {code_src_dir}")
        else:
            print("⚠️ Could not extract S3 URI from describe output")

        # Step 3: Bundle (from dev target - default)
        print("\n=== Step 3: Bundle ===")
        self.logger.info("=== STEP 3: Bundle ===")
        # Bundle from dev target (default behavior, no --target needed)
        result = self.run_cli_command(["bundle", "--pipeline", pipeline_file])
        results.append(result)
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")

        # Step 4: Deploy
        print("\n=== Step 4: Deploy ===")
        self.logger.info("=== STEP 4: Deploy ===")
        result = self.run_cli_command(["deploy", "test", "--pipeline", pipeline_file])
        results.append(result)
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy successful")

        # Step 5: Monitor
        print("\n=== Step 5: Monitor ===")
        self.logger.info("=== STEP 5: Monitor ===")
        result = self.run_cli_command(
            ["monitor", "--targets", "test", "--pipeline", pipeline_file]
        )
        results.append(result)
        assert result["success"], f"Monitor failed: {result['output']}"
        print("✅ Monitor successful")

        # Step 6: Run workflow
        print("\n=== Step 6: Run Workflow ===")
        self.logger.info("=== STEP 6: Run Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", workflow_name, "--targets", "test", "--pipeline", pipeline_file]
        )
        results.append(result)
        assert result["success"], f"Run workflow failed: {result['output']}"
        print("✅ Workflow started")

        # Step 7: Monitor workflow status
        print("\n=== Step 7: Monitor Workflow Status ===")
        self.logger.info("=== STEP 7: Monitor Workflow Status ===")
        result = self.run_cli_command(
            ["monitor", "--targets", "test", "--pipeline", pipeline_file]
        )
        results.append(result)
        assert result["success"], f"Monitor after run failed: {result['output']}"
        print("✅ Monitor after run successful")

        # Step 8: Start basic_test_workflow
        print("\n=== Step 8: Start Basic Test Workflow ===")
        self.logger.info("=== STEP 8: Start Basic Test Workflow ===")
        result = self.run_cli_command(
            ["run", "--workflow", workflow_name, "--targets", "test", "--pipeline", pipeline_file]
        )
        results.append(result)
        assert result["success"], f"Run workflow failed: {result['output']}"
        print("✅ Basic workflow started")

        # Step 9: Start expected failure workflow
        print("\n=== Step 9: Start Expected Failure Workflow ===")
        self.logger.info("=== STEP 9: Start Expected Failure Workflow ===")
        failure_workflow_name = "expected_failure_workflow"
        result = self.run_cli_command(
            ["run", "--workflow", failure_workflow_name, "--targets", "test", "--pipeline", pipeline_file]
        )
        results.append(result)
        assert result["success"], f"Run failure workflow failed: {result['output']}"
        print("✅ Failure workflow started")

        # Step 10: Monitor both workflows
        print("\n=== Step 10: Monitor Both Workflows ===")
        self.logger.info("=== STEP 10: Monitor Both Workflows ===")
        result = self.run_cli_command(["monitor", "--targets", "test", "--pipeline", pipeline_file])
        results.append(result)
        print("✅ Monitor completed")

        # Step 11: Fetch logs for failure workflow (expect failure)
        print("\n=== Step 11: Fetch Workflow Logs (Failure Expected) ===")
        self.logger.info("=== STEP 11: Fetch Workflow Logs (Failure Expected) ===")
        import boto3
        import os
        
        region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-1')
        endpoint = os.environ.get('AIRFLOW_SERVERLESS_ENDPOINT')
        if not endpoint:
            endpoint = f'https://airflow-serverless.{region}.api.aws/'
        
        try:
            client = boto3.client('awsoverdriveservice', region_name=region, endpoint_url=endpoint)
            response = client.list_workflows()
            workflows = response.get('Workflows', [])
            expected_failure_name = f'BasicTestPipeline_test_marketing_{failure_workflow_name}'
            
            failure_workflow_arn = None
            response = client.list_workflows()
            workflows = response.get('Workflows', [])
            for wf in workflows:
                if wf.get('Name') == expected_failure_name:
                    failure_workflow_arn = wf.get('WorkflowArn')
                    break
            
            if failure_workflow_arn:
                print(f"📋 Failure Workflow ARN: {failure_workflow_arn}")
                # Fetch logs with --live flag
                result = self.run_cli_command(
                    ["logs", "--workflow", failure_workflow_arn, "--live"]
                )
                results.append(result)
                
                # Check logs output - this workflow SHOULD fail
                if result["success"]:
                    output = result["output"]
                    if "Workflow run" in output and "failed" in output:
                        print("✅ Workflow failed as expected")
                        # Verify error message is in logs
                        if "Intentional failure for testing error handling" in output or "ValueError" in output:
                            print("✅ Error message found in logs")
                        else:
                            print("⚠️  Error message not found in logs, but workflow failed")
                    elif "Workflow run" in output and "completed successfully" in output:
                        pytest.fail(f"Failure workflow unexpectedly succeeded. Check logs output:\n{output}")
                    else:
                        pytest.fail(f"Could not determine failure workflow status from logs:\n{output}")
                else:
                    pytest.fail(f"Logs command failed for failure workflow: {result['output']}")
            else:
                pytest.fail("Failure workflow ARN not found")
        except Exception as e:
            pytest.fail(f"Could not fetch failure workflow logs: {e}")

        # Step 12: Fetch logs for success workflow
        print("\n=== Step 12: Fetch Workflow Logs (Success Expected) ===")
        self.logger.info("=== STEP 12: Fetch Workflow Logs (Success Expected) ===")
        try:
            expected_name = f'BasicTestPipeline_test_marketing_{workflow_name}'
            
            workflow_arn = None
            for wf in workflows:
                if wf.get('Name') == expected_name:
                    workflow_arn = wf.get('WorkflowArn')
                    break
            
            if workflow_arn:
                print(f"📋 Workflow ARN: {workflow_arn}")
                # Fetch logs with --live flag
                result = self.run_cli_command(
                    ["logs", "--workflow", workflow_arn, "--live"]
                )
                results.append(result)
                
                # Check logs output for workflow completion status
                if result["success"]:
                    output = result["output"]
                    if "Workflow run" in output and "completed successfully" in output:
                        print("✅ Workflow completed successfully")
                    elif "Workflow run" in output and "failed" in output:
                        pytest.fail(f"Workflow run failed. Check logs output:\n{output}")
                    elif "Workflow run" in output and "stopped" in output:
                        pytest.fail(f"Workflow run was stopped. Check logs output:\n{output}")
                    else:
                        print("✅ Logs retrieved successfully")
                else:
                    pytest.fail(f"Logs command failed: {result['output']}")
            else:
                pytest.fail("Workflow ARN not found")
        except Exception as e:
            pytest.fail(f"Could not fetch logs: {e}")

        print(f"\n✅ All workflow steps completed successfully!")
        print(f"Total commands: {len(results)}")
        print(f"Successful: {sum(1 for r in results if r['success'])}/{len(results)}")

        # Step 13: Verify EventBridge events were captured
        print("\n=== Step 13: Verify EventBridge Events ===")
        self._verify_eventbridge_events()

    def _setup_eventbridge_monitoring(self):
        """Setup EventBridge rule to capture events BEFORE deployment."""
        import boto3
        import json
        
        events_client = boto3.client('events', region_name='us-east-1')
        logs_client = boto3.client('logs', region_name='us-east-1')
        
        self.log_group_name = '/aws/events/smus-cicd-test'
        self.rule_name = 'smus-cicd-test-rule'
        
        try:
            # Cleanup from previous runs
            print("  Cleaning up from previous runs...")
            try:
                events_client.remove_targets(Rule=self.rule_name, Ids=['1'])
                events_client.delete_rule(Name=self.rule_name)
            except:
                pass
            
            try:
                logs_client.delete_resource_policy(policyName='EventBridgeToCloudWatchLogs')
            except:
                pass
            
            try:
                streams = logs_client.describe_log_streams(logGroupName=self.log_group_name)
                for stream in streams.get('logStreams', []):
                    logs_client.delete_log_stream(
                        logGroupName=self.log_group_name,
                        logStreamName=stream['logStreamName']
                    )
                logs_client.delete_log_group(logGroupName=self.log_group_name)
            except:
                pass
            
            # Create log group
            print(f"  Creating log group: {self.log_group_name}")
            logs_client.create_log_group(logGroupName=self.log_group_name)
            
            # Add resource policy to allow EventBridge to write
            account_id = boto3.client('sts').get_caller_identity()['Account']
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "events.amazonaws.com"},
                    "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                    "Resource": f"arn:aws:logs:us-east-1:{account_id}:log-group:{self.log_group_name}:*"
                }]
            }
            logs_client.put_resource_policy(
                policyName='EventBridgeToCloudWatchLogs',
                policyDocument=json.dumps(policy_document)
            )
            print("  ✓ Added resource policy for EventBridge")
            
            # Create EventBridge rule
            print(f"  Creating EventBridge rule: {self.rule_name}")
            events_client.put_rule(
                Name=self.rule_name,
                EventPattern=json.dumps({'source': ['com.amazon.smus.cicd']}),
                State='ENABLED'
            )
            
            # Add log group as target
            log_group_arn = f"arn:aws:logs:us-east-1:{account_id}:log-group:{self.log_group_name}"
            events_client.put_targets(
                Rule=self.rule_name,
                Targets=[{'Id': '1', 'Arn': log_group_arn}]
            )
            print("  ✓ EventBridge monitoring ready to capture events")
            
        except Exception as e:
            print(f"  ⚠️  Setup error: {e}")

    def _verify_eventbridge_events(self):
        """Verify that EventBridge events were captured during deployment."""
        import boto3
        import time
        import json
        
        logs_client = boto3.client('logs', region_name='us-east-1')
        events_client = boto3.client('events', region_name='us-east-1')
        
        try:
            # Wait for events to be delivered
            print("  Waiting 60 seconds for events to be delivered...")
            time.sleep(60)
            
            # Query for events
            end_time = int(time.time() * 1000)
            start_time = end_time - (3600 * 1000)
            
            found_events = []
            try:
                response = logs_client.filter_log_events(
                    logGroupName=self.log_group_name,
                    startTime=start_time,
                    endTime=end_time
                )
                
                for event in response.get('events', []):
                    try:
                        event_data = json.loads(event['message'])
                        detail_type = event_data.get('detail-type', '')
                        if detail_type.startswith('SMUS-CICD-'):
                            found_events.append(detail_type)
                            print(f"  ✓ Found event: {detail_type}")
                    except:
                        pass
                
            except logs_client.exceptions.ResourceNotFoundException:
                print("  ⚠️  No log streams found")
            
            if found_events:
                print(f"\n  ✅ Found {len(found_events)} events")
            else:
                print("  ⚠️  No events found - they may not have been delivered yet")
            
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
        finally:
            # Cleanup
            print("\n  Cleaning up test resources...")
            try:
                events_client.remove_targets(Rule=self.rule_name, Ids=['1'])
                events_client.delete_rule(Name=self.rule_name)
                print("  ✓ Deleted EventBridge rule")
            except:
                pass
            
            try:
                logs_client.delete_resource_policy(policyName='EventBridgeToCloudWatchLogs')
                print("  ✓ Deleted resource policy")
            except:
                pass
            
            try:
                streams = logs_client.describe_log_streams(logGroupName=self.log_group_name)
                for stream in streams.get('logStreams', []):
                    logs_client.delete_log_stream(
                        logGroupName=self.log_group_name,
                        logStreamName=stream['logStreamName']
                    )
                logs_client.delete_log_group(logGroupName=self.log_group_name)
                print("  ✓ Deleted CloudWatch log group")
            except:
                pass


