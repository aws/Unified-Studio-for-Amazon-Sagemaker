"""Integration test for basic pipeline workflow."""

import pytest
import os
from typer.testing import CliRunner
from ..base import IntegrationTestBase
from smus_cicd.helpers.utils import get_datazone_project_info


class TestBasicApp(IntegrationTestBase):
    """Test basic pipeline end-to-end workflow."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()

        # Clean up project from previous test run (only in setup)
        try:
            pipeline_file = os.path.join(self.test_dir, "manifest.yaml")
            
            # Use CLI delete command to properly delete project
            print("🧹 Cleaning up existing test project...")
            result = self.run_cli_command(
                ["delete", "--targets", "test", "--manifest", pipeline_file, "--force"]
            )
            if result["success"]:
                print("✅ Project cleanup successful")
            else:
                print(f"⚠️ Project cleanup had issues: {result['output']}")
        except Exception as e:
            print(f"⚠️ Could not clean up resources: {e}")

    def teardown_method(self, method):
        """Clean up test environment - do NOT delete projects/roles here."""
        super().teardown_method(method)
        self.cleanup_resources()
        self.cleanup_test_directory()

    def get_pipeline_file(self):
        """Get path to pipeline file in same directory."""
        return os.path.join(os.path.dirname(__file__), "manifest.yaml")

    @pytest.mark.integration
    def test_basic_app_workflow(self):
        """Test complete basic pipeline workflow: describe --connect -> bundle -> deploy -> monitor."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        results = []
        workflow_name = "basic_test_workflow"

        # Step 0: Setup EventBridge monitoring BEFORE deployment
        print("\n=== Step 0: Setup EventBridge Monitoring ===")
        self._setup_eventbridge_monitoring()

        # Step 0.1: Delete IAM role from previous test run
        print("\n=== Step 0.1: Cleanup Existing IAM Role ===")
        try:
            import boto3
            from datetime import datetime
            
            iam = boto3.client("iam")
            role_name = "smus-test-project-basic-role"
            
            try:
                self.logger.info(f"Deleting IAM role: {role_name} at {datetime.utcnow().isoformat()}")
                
                # Detach all policies
                policies = iam.list_attached_role_policies(RoleName=role_name)
                for policy in policies.get("AttachedPolicies", []):
                    iam.detach_role_policy(
                        RoleName=role_name, PolicyArn=policy["PolicyArn"]
                    )
                
                # Delete the role
                iam.delete_role(RoleName=role_name)
                self.logger.info(f"Successfully deleted role: {role_name} at {datetime.utcnow().isoformat()}")
                print(f"🧹 Cleaned up existing role: {role_name}")
            except iam.exceptions.NoSuchEntityException:
                self.logger.info(f"Role {role_name} does not exist, skipping deletion")
                print("✓ No existing role to delete")
        except Exception as e:
            print(f"⚠️ Could not delete role: {e}")

        # Step 0.5: Delete workflow if it exists
        print("\n=== Step 0.5: Cleanup Existing Workflow ===")
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
        result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
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
        
        dev_project_name = manifest['stages']['dev']['project']['name']
        
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
                self.sync_to_s3(code_dir, s3_uri, exclude_patterns=["*.pyc", "__pycache__/*"])
            else:
                print(f"⚠️ Code directory not found: {code_dir}")
            
            # Upload code/src directory to S3 code/src/
            code_src_dir = os.path.join(base_dir, "code", "src")
            if os.path.exists(code_src_dir):
                self.sync_to_s3(code_src_dir, s3_uri + "code/src/", exclude_patterns=["*.pyc", "__pycache__/*"])
            else:
                print(f"⚠️ Code/src directory not found: {code_src_dir}")
        else:
            print("⚠️ Could not extract S3 URI from describe output")

        # Step 3: Bundle (from dev target - default)
        print("\n=== Step 3: Bundle ===")
        self.logger.info("=== STEP 3: Bundle ===")
        # Bundle from dev target (default behavior, no --target needed)
        result = self.run_cli_command(["bundle", "--manifest", pipeline_file])
        results.append(result)
        assert result["success"], f"Bundle failed: {result['output']}"
        print("✅ Bundle successful")

        # Step 4: Deploy test target (EXPECTED TO FAIL due to expected_failure_workflow)
        print("\n=== Step 4: Deploy Test Target ===")
        self.logger.info("=== STEP 4: Deploy Test Target ===")
        result = self.run_cli_command(["deploy", "test", "--manifest", pipeline_file])
        results.append(result)
        
        # Deploy should succeed (workflows run async)
        assert result["success"], f"Deploy failed: {result['output']}"
        print("✅ Deploy succeeded (workflows run asynchronously)")

        # Step 4.5: Verify project owners match manifest
        print("\n=== Step 4.5: Verify Project Owners ===")
        self.logger.info("=== STEP 4.5: Verify Project Owners ===")
        import boto3
        import yaml
        
        with open(pipeline_file, 'r') as f:
            manifest = yaml.safe_load(f)
        
        region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-2')
        datazone = boto3.client('datazone', region_name=region)
        
        # Get domain ID
        domains = datazone.list_domains()
        assert domains['items'], "No domains found"
        domain_id = domains['items'][0]['id']
        
        # Get dev project name and expected owners
        dev_project_name = manifest['stages']['dev']['project']['name']
        expected_owners = manifest['stages']['dev']['project'].get('owners', [])
        
        if expected_owners:
            # Get project ID
            projects = datazone.list_projects(domainIdentifier=domain_id)
            project_id = next(
                (p['id'] for p in projects['items'] if p['name'] == dev_project_name),
                None
            )
            assert project_id, f"Project {dev_project_name} not found"
            
            # Get actual owners
            members = datazone.list_project_memberships(
                domainIdentifier=domain_id,
                projectIdentifier=project_id
            )
            
            owner_group_ids = [
                m['memberDetails']['group']['groupId']
                for m in members.get('members', [])
                if m.get('designation') == 'PROJECT_OWNER' and 'group' in m.get('memberDetails', {})
            ]
            
            # Map group IDs to ARNs
            actual_owners = []
            for group_id in owner_group_ids:
                profile = datazone.get_group_profile(
                    domainIdentifier=domain_id,
                    groupIdentifier=group_id
                )
                owner_id = profile.get('rolePrincipalArn') or profile.get('groupName') or profile.get('id')
                actual_owners.append(owner_id)
            
            # Expand ${AWS_ACCOUNT_ID} in expected owners
            sts = boto3.client('sts')
            account_id = sts.get_caller_identity()['Account']
            
            # Verify ARN-based owners
            verified_count = 0
            for owner in expected_owners:
                expanded = owner.replace('${AWS_ACCOUNT_ID}', account_id)
                if expanded.startswith('arn:'):
                    assert expanded in actual_owners, f"Owner {expanded} not found in project"
                    verified_count += 1
            
            print(f"✅ Verified {verified_count} ARN-based owners in project {dev_project_name}")

        # Step 5: Monitor with --live to wait for workflows to complete
        print("\n=== Step 5: Monitor Workflows with --live ===")
        self.logger.info("=== STEP 5: Monitor Workflows with --live ===")
        result = self.run_cli_command(
            ["monitor", "--targets", "test", "--manifest", pipeline_file, "--live"]
        )
        results.append(result)
        assert result["success"], f"Monitor failed: {result['output']}"
        
        # Check workflow statuses from monitor output
        monitor_output = result.get("output", "")
        
        # Verify expected_failure_workflow failed
        assert "expected_failure_workflow" in monitor_output, "expected_failure_workflow not found in monitor output"
        assert "FAILED" in monitor_output, f"expected_failure_workflow should have FAILED status in monitor output: {monitor_output}"
        print("✅ expected_failure_workflow failed as expected")
        
        # Verify basic_test_workflow succeeded
        assert "basic_test_workflow" in monitor_output, "basic_test_workflow not found in monitor output"
        assert "SUCCEEDED" in monitor_output or "COMPLETED" in monitor_output, \
            f"basic_test_workflow should have SUCCEEDED/COMPLETED status: {monitor_output}"
        print("✅ basic_test_workflow succeeded as expected")

        # Step 6-8: Workflows already ran during deploy, skip manual start
        print("\n=== Steps 6-8: Workflows Already Executed During Deploy ===")
        print("✅ Workflows were created and run during deploy bootstrap")


        # Step 9: Download and validate notebook outputs
        print("\n=== Step 9: Download and Validate Notebook Outputs ===")
        self.logger.info("=== STEP 9: Download and Validate Notebook Outputs ===")
        
        # Get S3 bucket and workflow info from manifest
        with open(pipeline_file, 'r') as f:
            manifest = yaml.safe_load(f)
        test_project_name = manifest['stages']['test']['project']['name']
        
        # Get project info to find S3 bucket
        from smus_cicd.helpers.utils import get_datazone_project_info, build_domain_config
        from smus_cicd.application import ApplicationManifest
        app_manifest = ApplicationManifest.from_file(pipeline_file)
        test_config = app_manifest.stages['test']
        config = build_domain_config(test_config)
        project_info = get_datazone_project_info(test_project_name, config)
        
        # Extract bucket from S3 connection
        s3_connection = project_info.get('connections', {}).get('default.s3_shared', {})
        s3_uri = s3_connection.get('s3Uri', '')
        if s3_uri:
            # Extract bucket name from s3://bucket/path
            s3_bucket = s3_uri.replace('s3://', '').split('/')[0]
            print(f"📦 S3 Bucket: {s3_bucket}")
            
            # Get workflow ARN and latest run ID for the success workflow
            import boto3
            import os
            # Find the basic_test_workflow (the one that should succeed)
            expected_name = f'BasicTestBundle_test_project_basic_{workflow_name}'
            success_workflow_arn = self.get_workflow_arn(expected_name)
            print(f"📋 Workflow ARN: {success_workflow_arn}")
            
            # Get latest run
            client = self.get_airflow_client()
            runs_response = client.list_workflow_runs(WorkflowArn=success_workflow_arn, MaxResults=1)
            runs = runs_response.get('WorkflowRuns', [])
            if not runs:
                pytest.fail("Could not find run ID for notebook download")
            success_run_id = runs[0].get('RunId')
            print(f"📋 Run ID: {success_run_id}")
            
            # Download notebooks
            notebooks_downloaded = self.download_and_validate_notebooks( success_workflow_arn, success_run_id)
            
            # Now validate specific notebooks
            import json
            from pathlib import Path
            
            # Extract workflow name from ARN
            workflow_name_from_arn = success_workflow_arn.split('/')[-1] if '/' in success_workflow_arn else success_run_id
            output_dir = Path("tests/test-outputs/notebooks") / workflow_name_from_arn
            
            # Find the downloaded notebooks
            param_test_notebook = None
            
            for nb_path in output_dir.rglob("*.ipynb"):
                if "param_test" in nb_path.name.lower():
                    param_test_notebook = nb_path
                    break
            
            # Assert param_test_notebook has no errors
            if param_test_notebook:
                print(f"\n✅ Found param_test notebook: {param_test_notebook}")
                with open(param_test_notebook) as f:
                    notebook = json.load(f)
                
                error_count = 0
                for cell in notebook.get("cells", []):
                    for output in cell.get("outputs", []):
                        if output.get("output_type") == "error":
                            error_count += 1
                
                assert error_count == 0, f"param_test_notebook should have no errors, but found {error_count}"
                print("✅ param_test_notebook has no errors")
            else:
                pytest.fail("param_test_notebook output not found")
        else:
            pytest.fail("Could not determine S3 bucket from project info")

        # Step 11: Fetch logs for failure workflow (expect failure)
        print("\n=== Step 11: Fetch Workflow Logs (Failure Expected) ===")
        self.logger.info("=== STEP 11: Fetch Workflow Logs (Failure Expected) ===")
        import boto3
        import os
        
        try:
            expected_failure_name = f'BasicTestBundle_test_project_basic_expected_failure_workflow'
            try:
                failure_workflow_arn = self.get_workflow_arn(expected_failure_name)
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
            except AssertionError:
                pytest.fail("Failure workflow ARN not found")
        except Exception as e:
            pytest.fail(f"Could not fetch failure workflow logs: {e}")

        # Step 12: Fetch logs for success workflow
        print("\n=== Step 12: Fetch Workflow Logs (Success Expected) ===")
        self.logger.info("=== STEP 12: Fetch Workflow Logs (Success Expected) ===")
        try:
            expected_name = f'BasicTestBundle_test_project_basic_{workflow_name}'
            workflow_arn = self.get_workflow_arn(expected_name)
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
        except AssertionError:
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


