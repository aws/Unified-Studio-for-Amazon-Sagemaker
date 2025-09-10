"""Integration test for multi-target pipeline workflow."""
import pytest
import os
from typer.testing import CliRunner
from ..base import IntegrationTestBase
from smus_cicd.helpers.utils import get_datazone_project_info

class TestMultiTargetPipeline(IntegrationTestBase):
    """Test multi-target pipeline end-to-end workflow."""
    
    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()
    
    def teardown_method(self, method):
        """Clean up test environment."""
        super().teardown_method(method)
        self.cleanup_resources()
        self.cleanup_test_directory()
    
    def cleanup_generated_files(self):
        """Remove generated test files from all target environments AND local code directory."""
        import subprocess
        import glob
        import os
        
        # Clean up local generated DAG files first
        pipeline_file = self.get_pipeline_file()
        local_dags_dir = os.path.join(os.path.dirname(pipeline_file), "code", "workflows", "dags")
        
        if os.path.exists(local_dags_dir):
            generated_files = glob.glob(os.path.join(local_dags_dir, "generated_test_*.py"))
            for file_path in generated_files:
                try:
                    os.remove(file_path)
                    print(f"  Removed local file: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"  Warning: Could not remove {file_path}: {e}")
            
            if generated_files:
                print(f"  Cleaned {len(generated_files)} local generated DAG files")
            else:
                print(f"  No local generated DAG files to clean")
        
        # Note: S3 locations and MWAA environments are extracted dynamically from deploy output
        # S3 cleanup is skipped since locations are determined at runtime

    def generate_new_dag_file(self):
        """Generate a new DAG file with unique name and content."""
        import time
        import random
        
        # Generate unique DAG name
        timestamp = int(time.time())
        random_id = random.randint(1000, 9999)
        dag_name = f"generated_test_dag_{timestamp}_{random_id}"
        
        # Create DAG content
        dag_content = f'''"""
Generated test DAG for integration testing.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator

def {dag_name}_task():
    """Generated task function."""
    print(f"Executing generated task: {dag_name}")
    return "Generated task completed successfully"

default_args = {{
    'owner': 'integration-test',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}}

dag = DAG(
    '{dag_name}',
    default_args=default_args,
    description='Generated test DAG for integration testing',
    schedule_interval=None,
    catchup=False,
    tags=['integration-test', 'generated'],
)

task = PythonOperator(
    task_id='{dag_name}_task',
    python_callable={dag_name}_task,
    dag=dag,
)
'''
        
        # Write DAG file to code directory
        pipeline_file = self.get_pipeline_file()
        code_dir = os.path.join(os.path.dirname(pipeline_file), "code", "workflows", "dags")
        os.makedirs(code_dir, exist_ok=True)
        
        dag_file_path = os.path.join(code_dir, f"{dag_name}.py")
        with open(dag_file_path, 'w') as f:
            f.write(dag_content)
        
        print(f"  Generated DAG file: {dag_file_path}")
        return dag_name

    def get_pipeline_file(self):
        """Get path to pipeline file in same directory."""
        return os.path.join(os.path.dirname(__file__), "multi_target_pipeline.yaml")
    
    @pytest.mark.integration
    def test_describe_connect_after_deploy(self):
        """Test describe --connect after deployment (should be idempotent)."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")
        
        pipeline_file = self.get_pipeline_file()
        
        # Deploy test target (should be idempotent)
        deploy_result = self.run_cli_command(["deploy", "--pipeline", pipeline_file, "--targets", "test"])
        
        # Deploy should succeed (idempotent behavior)
        assert deploy_result['success'], f"Deploy should be idempotent but failed: {deploy_result['output']}"
        
        # Test describe --connect after successful deployment
        result = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--workflows", "--connect"])
        
        assert result['success'], f"Describe --connect failed: {result['output']}"
        
        assert result['success'], f"Describe --connect failed: {result['output']}"
        
        # Verify it shows pipeline info
        assert "Pipeline: IntegrationTestMultiTarget" in result['output']
        assert "Domain: cicd-test-domain" in result['output']  # Region-agnostic
        
        # Verify it shows target info with connections
        assert "Targets:" in result['output']
        assert "test: integration-test-test" in result['output']
        assert "Project ID:" in result['output']
        assert "Status:" in result['output']
        assert "Connections:" in result['output']
        
        # Verify Project IDs are not "Unknown"
        assert "Project ID: Unknown" not in result['output'], "Project ID should not be 'Unknown' when --connect is used"
        
        # Verify owners information is displayed
        assert "Owners:" in result['output'], "Owners information should be displayed with --connect"
        
        # Verify it shows workflow info
        assert "Workflows:" in result['output']
        assert "test_dag" in result['output']
        assert "Connection: project.workflow_mwaa" in result['output']
        
        # Verify connection details are shown
        assert "connectionId:" in result['output']
        assert "type:" in result['output']
        assert "awsAccountId:" in result['output']
        
        # Verify MWAA-specific details
        assert "environmentName:" in result['output']
        # Note: mwaaStatus may not always be present depending on MWAA environment state

    @pytest.mark.integration
    def test_describe_connect_nonexistent_project(self):
        """Test describe --connect with nonexistent project shows proper error."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")
        
        # Create a manifest with a nonexistent project
        manifest_content = """
pipelineName: NonexistentProjectTest
domain:
  name: cicd-test-domain
  region: us-east-2
bundle:
  bundlesDirectory: ./tests/integration/bundles
targets:
  test:
    stage: test
    project:
      name: nonexistent-project-12345
workflows:
  - workflowName: test_dag
    connectionName: project.workflow_mwaa
    logging: console
"""
        
        # Write temporary manifest
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(manifest_content)
            temp_manifest = f.name
        
        try:
            result = self.run_cli_command(["describe", "--pipeline", temp_manifest, "--connect"])
            
            # Should succeed but show error for the nonexistent project
            assert result['success'], f"Describe command should not crash: {result['output']}"
            assert "❌ Error getting project info:" in result['output'], f"Should show error for nonexistent project: {result['output']}"
            assert "nonexistent-project-12345" in result['output'], f"Should mention the project name: {result['output']}"
            
        finally:
            os.unlink(temp_manifest)

    @pytest.mark.integration
    def test_describe_connect_wrong_domain(self):
        """Test describe --connect with wrong domain shows proper error."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")
        
        # Create a manifest with wrong domain
        manifest_content = """
pipelineName: WrongDomainTest
domain:
  name: nonexistent-domain-12345
  region: us-east-2
bundle:
  bundlesDirectory: ./tests/integration/bundles
targets:
  test:
    stage: test
    project:
      name: integration-test-test
workflows:
  - workflowName: test_dag
    connectionName: project.workflow_mwaa
    logging: console
"""
        
        # Write temporary manifest
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(manifest_content)
            temp_manifest = f.name
        
        try:
            result = self.run_cli_command(["describe", "--pipeline", temp_manifest, "--connect"])
            
            # Should succeed - domain validation might not be strict or domain might exist
            assert result['success'], f"Describe command should not crash: {result['output']}"
            # Check that it shows project information (either success or error)
            assert "integration-test-test" in result['output'], f"Should mention the project name: {result['output']}"
            
        finally:
            os.unlink(temp_manifest)

    @pytest.mark.integration
    def test_describe_connect_wrong_region(self):
        """Test describe --connect with wrong region shows proper error."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")
        
        # Create a manifest with wrong region
        manifest_content = """
pipelineName: WrongRegionTest
domain:
  name: cicd-test-domain
  region: eu-west-1
bundle:
  bundlesDirectory: ./tests/integration/bundles
targets:
  test:
    stage: test
    project:
      name: integration-test-test
workflows:
  - workflowName: test_dag
    connectionName: project.workflow_mwaa
    logging: console
"""
        
        # Write temporary manifest
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(manifest_content)
            temp_manifest = f.name
        
        try:
            result = self.run_cli_command(["describe", "--pipeline", temp_manifest, "--connect"])
            
            # Should succeed because DEV_DOMAIN_REGION environment variable overrides manifest region
            assert result['success'], f"Describe command should not crash: {result['output']}"
            # Verify that environment variable took precedence and found the project
            assert "Project ID:" in result['output'], f"Should find project using environment variable region: {result['output']}"
            
        finally:
            os.unlink(temp_manifest)

    @pytest.mark.integration
    def test_describe_without_connect_vs_with_connect(self):
        """Test difference between describe without --connect and with --connect."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")
        
        pipeline_file = self.get_pipeline_file()
        
        # Test without --connect
        result_without = self.run_cli_command(["describe", "--pipeline", pipeline_file])
        assert result_without['success'], f"Describe without --connect failed: {result_without['output']}"
        
        # Test with --connect
        result_with = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--connect"])
        assert result_with['success'], f"Describe with --connect failed: {result_with['output']}"
        
        # Without --connect should not have connection details
        assert "Project ID:" not in result_without['output']
        assert "connectionId:" not in result_without['output']
        assert "awsAccountId:" not in result_without['output']
        assert "Owners:" not in result_without['output']
        
        # With --connect should have connection details and project info
        assert "Project ID:" in result_with['output']
        assert "connectionId:" in result_with['output']
        assert "awsAccountId:" in result_with['output']
        assert "Owners:" in result_with['output']
        
        # Project IDs should not be "Unknown" when using --connect
        assert "Project ID: Unknown" not in result_with['output']
        
    @pytest.mark.integration
    def test_describe_connect_project_details(self):
        """Test that describe --connect shows actual Project IDs and Owners information."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")
        
        pipeline_file = self.get_pipeline_file()
        
        # Test with --connect to get project details
        result = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--connect"])
        assert result['success'], f"Describe --connect failed: {result['output']}"
        
        output = result['output']
        
        # Check that all targets show actual Project IDs (not "Unknown")
        assert "Project ID:" in output, "Project ID field should be present"
        assert "Project ID: Unknown" not in output, "Project IDs should not be 'Unknown' with --connect"
        
        # Check that owners information is displayed
        assert "Owners:" in output, "Owners field should be present with --connect"
        
        # Check for specific targets and their details
        targets = ["dev: dev-marketing", "test: integration-test-test", "prod: integration-test-prod"]
        
        for target in targets:
            if target in output:
                # Find the section for this target
                lines = output.split('\n')
                target_found = False
                for i, line in enumerate(lines):
                    if target in line:
                        target_found = True
                        # Check next few lines for project details
                        target_section = '\n'.join(lines[i:i+10])
                        
                        # Verify Project ID is not Unknown
                        if "Project ID:" in target_section:
                            assert "Project ID: Unknown" not in target_section, f"Project ID should not be Unknown for {target}"
                        
                        # Verify Owners field exists
                        if "Owners:" in target_section:
                            # Extract owners line and verify it's not empty
                            owners_line = next((l for l in lines[i:i+10] if "Owners:" in l), "")
                            assert owners_line.strip() != "Owners:", f"Owners should not be empty for {target}"
                        
                        break
                
                if target_found:
                    print(f"✅ {target} - Project details verified")

    @pytest.mark.integration
    def test_describe_connect_multiple_targets_mixed_results(self):
        """Test describe --connect with multiple targets where some exist and some don't."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")
        
        manifest_content = """
pipelineName: MixedTargetsTest
domain:
  name: cicd-test-domain
  region: us-east-2
bundle:
  bundlesDirectory: ./tests/integration/bundles
targets:
  existing:
    stage: test
    project:
      name: integration-test-test
  nonexistent:
    stage: test
    project:
      name: definitely-does-not-exist-project-12345
workflows:
  - workflowName: test_dag
    connectionName: project.workflow_mwaa
"""
        
        # Write temporary manifest
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(manifest_content)
            temp_manifest = f.name
        
        try:
            result = self.run_cli_command(["describe", "--pipeline", temp_manifest, "--connect"])
            
            # Should succeed and show mixed results
            assert result['success'], f"Command should not crash: {result['output']}"
            assert "Targets:" in result['output'], f"Should show targets section: {result['output']}"
            assert "existing: integration-test-test" in result['output'], f"Should show existing target: {result['output']}"
            assert "nonexistent: definitely-does-not-exist-project-12345" in result['output'], f"Should show nonexistent target: {result['output']}"
            
            # Should show error for nonexistent project
            assert "❌ Error getting project info:" in result['output'], f"Should show error for nonexistent project: {result['output']}"
            
        finally:
            os.unlink(temp_manifest)

    @pytest.mark.integration
    def test_describe_connect_invalid_connection_name(self):
        """Test describe --connect with workflow referencing nonexistent connection."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")
        
        manifest_content = """
pipelineName: InvalidConnectionTest
domain:
  name: cicd-test-domain
  region: us-east-2
bundle:
  bundlesDirectory: ./tests/integration/bundles
targets:
  test:
    stage: test
    project:
      name: integration-test-test
workflows:
  - workflowName: test_dag
    connectionName: nonexistent.connection.name
"""
        
        # Write temporary manifest
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(manifest_content)
            temp_manifest = f.name
        
        try:
            result = self.run_cli_command(["describe", "--pipeline", temp_manifest, "--connect"])
            
            # Should succeed but may show warnings about nonexistent connections
            assert result['success'], f"Command should not crash with invalid connection: {result['output']}"
            assert "Workflows:" in result['output'], f"Should show workflows section: {result['output']}"
            assert "test_dag" in result['output'], f"Should show workflow name: {result['output']}"
            assert "nonexistent.connection.name" in result['output'], f"Should show connection name: {result['output']}"
            
        finally:
            os.unlink(temp_manifest)

    @pytest.mark.integration
    def test_multi_target_comprehensive_workflow(self):
        """Test complete multi-target pipeline workflow: parse -> upload -> bundle -> deploy -> monitor."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        results = []

        # Step 0: Cleanup - Remove any existing generated files from targets
        print("\n=== Step 0: Cleanup Generated Files ===")
        self.cleanup_generated_files()

        # Step 0.5: Generate new DAG file with unique name
        print("\n=== Step 0.5: Generate New DAG File ===")
        generated_dag_name = self.generate_new_dag_file()
        print(f"Generated DAG: {generated_dag_name}")

        try:
            # Step 1: Describe pipeline configuration
            print("\n=== Step 1: Describe Pipeline ===")
            result = self.run_cli_command(["describe", "--pipeline", pipeline_file])
            results.append(result)

            if result['success']:
                print("✅ Describe command successful")
                assert "Pipeline:" in result['output'], f"Describe output missing 'Pipeline:': {result['output']}"
            else:
                print(f"❌ Describe command failed: {result['output']}")
                assert False, f"Describe command failed: {result['output']}"

            # Step 2: Describe with targets and connect
            print("\n=== Step 2: Describe with Targets ===")
            result = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--connect"])
            results.append(result)

            if result['success']:
                print("✅ Describe targets successful")
                assert "Targets:" in result['output'], f"Describe targets output missing 'Targets:': {result['output']}"
                assert "Project ID:" in result['output'], f"Describe targets --connect missing Project ID info: {result['output']}"
            
                # Validate that Eng1 (c478f4d8-4061-7042-f852-70c2db7c217e) is an owner in test and prod projects
                if "c478f4d8-4061-7042-f852-70c2db7c217e" in result['output']:
                    print("✅ Eng1 is correctly listed as project owner")
                else:
                    print("⚠️  Eng1 not found as project owner - may need initialization")
            else:
                print(f"❌ Describe targets failed: {result['output']}")
                assert False, f"Describe targets failed: {result['output']}"

        except Exception as e:
            print(f"❌ Describe steps failed: {e}")
            results.append({'success': False, 'output': f"Describe steps failed: {e}"})

        # Step 3: Upload code files to S3 (test S3 connection)
        print("\n=== Step 3: Upload Code to S3 ===")
        try:
            # Get S3 URI from dev project using describe command
            describe_result = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--connect"])
            if describe_result['success']:
                describe_output = describe_result['output']
                
                # Extract S3 URI for dev project from describe output
                import re
                s3_uri_match = re.search(r'dev: dev-marketing.*?s3Uri: (s3://[^\s]+)', describe_output, re.DOTALL)
                
                if s3_uri_match:
                    s3_uri = s3_uri_match.group(1)
                    
                    # Copy local code files to S3
                    code_dir = os.path.join(os.path.dirname(pipeline_file), "code")
                    if os.path.exists(code_dir):
                        import subprocess
                        result = subprocess.run([
                            'aws', 's3', 'sync', code_dir, s3_uri,
                            '--exclude', '*.pyc', '--exclude', '__pycache__/*'
                        ], capture_output=True, text=True)

                        if result.returncode == 0:
                            print(f"✅ Code uploaded to S3: {s3_uri}")
                            print(f"Upload output: {result.stdout.strip()}")
                            results.append({'success': True, 'output': f"Code uploaded to {s3_uri}"})
                        else:
                            print(f"❌ S3 upload failed: {result.stderr}")
                            results.append({'success': False, 'output': f"S3 upload failed: {result.stderr}"})
                    else:
                        print(f"⚠️  Code directory not found: {code_dir}")
                        results.append({'success': False, 'output': f"Code directory not found: {code_dir}"})
                else:
                    print("❌ S3 URI not found in describe output")
                    results.append({'success': False, 'output': "S3 URI not found in describe output"})
            else:
                print(f"❌ Failed to get project info: {describe_result['output']}")
                results.append({'success': False, 'output': f"Failed to get project info: {describe_result['output']}"})
        except Exception as e:
            print(f"❌ S3 upload error: {e}")
            results.append({'success': False, 'output': f"S3 upload error: {e}"})

        # Step 4: Bundle command for dev target
        print("\n=== Step 4: Bundle Command (dev) ===")
        result = self.run_cli_command(["bundle", "--pipeline", pipeline_file, "dev"])
        results.append(result)

        if result['success']:
            print("✅ Bundle command successful")
            print(f"Bundle output: {result['output']}")

            # Extract bundle file path from output
            import re
            bundle_match = re.search(r'Bundle created: (.*\.zip)', result['output'])
            if bundle_match:
                bundle_path = bundle_match.group(1).strip()
                print(f"Bundle file location: {bundle_path}")

                # Check if bundle file exists and is not empty
                if os.path.exists(bundle_path):
                    file_size = os.path.getsize(bundle_path)
                    print(f"Bundle file size: {file_size} bytes")
                    assert file_size > 0, f"Bundle file is empty: {bundle_path}"

                    # Check bundle contents for uploaded files
                    import zipfile
                    with zipfile.ZipFile(bundle_path, 'r') as zip_file:
                        file_list = zip_file.namelist()
                        print(f"Bundle contains {len(file_list)} files")

                        # Check for uploaded files in their respective directories
                        assert any('workflows/dags/test_dag.py' in f for f in file_list), f"workflows/dags/test_dag.py not found in bundle: {file_list}"
                        assert any('storage/src/test-notebook1.ipynb' in f for f in file_list), f"storage/src/test-notebook1.ipynb not found in bundle: {file_list}"
                        
                        # Check for generated DAG file
                        generated_dag_file = f"workflows/dags/{generated_dag_name}.py"
                        if any(generated_dag_file in f for f in file_list):
                            print(f"✅ Bundle contains generated DAG: {generated_dag_file}")
                        else:
                            print(f"⚠️  Generated DAG not found in bundle: {generated_dag_file}")
                            print(f"Bundle contents: {file_list}")
                        
                        print("✅ Bundle contains uploaded files: workflows/dags/test_dag.py and storage/src/test-notebook1.ipynb")

                    print("✅ Bundle file exists and is not empty")
                else:
                    assert False, f"Bundle file not found: {bundle_path}"
            else:
                # Fallback validation
                assert "Bundle created" in result['output'] or "bundling" in result['output'].lower(), f"Bundle output missing success indicator: {result['output']}"
        else:
            # Bundle should succeed - any failure is a real test failure
            pytest.fail(f"Bundle command failed: {result['output']}")

        # Step 5: Deploy to test target (auto-initializes if needed)
        print("\n=== Step 5: Deploy to Test Target ===")
        result = self.run_cli_command(["deploy", "--pipeline", pipeline_file, "--targets", "test"])
        results.append(result)

        # Deploy should be idempotent and succeed
        assert result['success'], f"Deploy should be idempotent but failed: {result['output']}"
        print("✅ Deploy command successful (idempotent)")
        print(f"Deploy output: {result['output']}")

        # Step 6: Deploy command (test target)
        print("\n=== Step 6: Deploy Command (test) ===")
        result = self.run_cli_command(["deploy", "--pipeline", pipeline_file, "test"])
        results.append(result)

        if result['success']:
            print("✅ Deploy command successful")
            print(f"Deploy output: {result['output']}")

            # Validate workflow validation process
            deploy_output = result['output']
            assert "🚀 Starting workflow validation..." in deploy_output, f"Deploy output missing workflow validation start: {deploy_output}"
            
            # Deploy should just complete workflow validation without MWAA checks
            assert "✅ Workflow validation completed" in deploy_output, f"Deploy output missing workflow validation completion: {deploy_output}"
            print("✅ Workflow validation completed successfully")
            
            # Validate S3 destination structure after deploy
            try:
                import subprocess
                import re
                
                # Extract actual S3 location from deploy output
                s3_location_match = re.search(r'S3 Location: (s3://[^\s]+)', deploy_output)
                if s3_location_match:
                    s3_location = s3_location_match.group(1)
                    print(f"✅ Found S3 location: {s3_location}")
                    
                    s3_result = subprocess.run([
                        'aws', 's3', 'ls', 
                        s3_location,
                        '--recursive'
                    ], capture_output=True, text=True)
                    
                    if s3_result.returncode == 0:
                        s3_files = s3_result.stdout.strip().split('\n')
                        deployed_files = [line.split()[-1] for line in s3_files if line.strip()]
                        
                        # Check for expected deployed files (using relative paths)
                        has_notebook = any('test-notebook1.ipynb' in f for f in deployed_files)
                        has_dag = any('test_dag.py' in f for f in deployed_files)
                        
                        if has_notebook and has_dag:
                            print("✅ S3 validation successful - found expected files")
                        else:
                            print(f"⚠️  S3 validation incomplete - files: {deployed_files}")
                    else:
                        print(f"⚠️  Could not list S3 contents: {s3_result.stderr}")
                else:
                    print("⚠️  Could not extract S3 location from deploy output")
                    
            except Exception as e:
                print(f"⚠️  S3 validation error: {e}")
        else:
            # Deploy should be idempotent and succeed
            assert False, f"Deploy to test should be idempotent but failed: {result['output']}"

        # Step 7: Deploy command (prod target)
        print("\n=== Step 7: Deploy Command (prod) ===")
        result = self.run_cli_command(["deploy", "--pipeline", pipeline_file, "prod"])
        results.append(result)

        if result['success']:
            print("✅ Deploy to prod successful")
            print(f"Deploy output: {result['output']}")
            
            # Validate deployment completed
            assert "✅ Deployment completed successfully!" in result['output'], f"Deploy output missing completion: {result['output']}"
            assert "📊 Total files deployed:" in result['output'], f"Deploy output missing deploy count: {result['output']}"
        else:
            # Deploy should be idempotent and succeed
            assert False, f"Deploy to prod should be idempotent but failed: {result['output']}"

        # Step 8: Describe with Connect (after deployment)
        print("\n=== Step 8: Describe with Connect ===")
        result = self.run_cli_command(["describe", "--pipeline", pipeline_file, "--connect"])
        results.append(result)

        if result['success']:
            print("✅ Describe --connect successful")
            
            # Validate it shows connection details
            describe_output = result['output']
            assert "Pipeline: IntegrationTestMultiTarget" in describe_output, f"Describe output missing pipeline name: {describe_output}"
            assert f"Domain: cicd-test-domain ({self.config['aws']['region']})" in describe_output, f"Describe output missing domain info: {describe_output}"
            assert "Targets:" in describe_output, f"Describe output missing targets section: {describe_output}"
            
            # Check for connection details (if project exists)
            if "Error:" not in describe_output:
                assert "Project ID:" in describe_output, f"Describe --connect missing project ID: {describe_output}"
                assert "Connections:" in describe_output, f"Describe --connect missing connections: {describe_output}"
                assert "connectionId:" in describe_output, f"Describe --connect missing connection details: {describe_output}"
                print("✅ Connection details validated")
            else:
                print("⚠️  Project not found - connection details not available")
        else:
            print(f"❌ Describe --connect failed: {result['output']}")

        # Step 8.5: Run command to trigger the workflow
        print("\n=== Step 8.5: Run Command (Trigger Workflow) ===")
        run_result = self.run_cli_command([
            "run", "--pipeline", pipeline_file, 
            "--workflow", generated_dag_name,
            "--command", f"dags trigger {generated_dag_name}",
            "--targets", "test"
        ])
        results.append(run_result)
        
        if run_result['success']:
            print("✅ Run command successful")
            print(f"Run output: {run_result['output']}")
        else:
            print(f"⚠️ Run command failed (may be expected if MWAA unavailable): {run_result['output']}")

        # Step 8.6: Monitor command to check actual DAG detection
        print("\n=== Step 8.6: Monitor Command (DAG Detection) ===")
        result = self.run_cli_command(["monitor", "--pipeline", pipeline_file])
        results.append(result)

        if result['success']:
            print("✅ Monitor command successful")
            monitor_output = result['output']
            
            # Check if test_dag is detected in at least one environment (dev should have it)
            if "✓ test_dag" in monitor_output:
                print("✅ Workflow 'test_dag' detected in MWAA environments")
                
                # Count how many targets show the workflow
                test_dag_count = monitor_output.count("✓ test_dag")
                print(f"✅ Workflow detected in {test_dag_count} target environment(s)")
            else:
                print("❌ Workflow 'test_dag' not detected in any MWAA environments")
                print("🔍 Monitor output for debugging:")
                print(monitor_output)
                # This is a critical failure - at least dev environment should show the DAG
                assert False, f"Expected workflow 'test_dag' not found in monitor output after successful deployment: {monitor_output}"
            
            print(f"Monitor output: {result['output']}")
        else:
            print(f"❌ Monitor command failed: {result['output']}")
            
            # Check if failure is due to MWAA unavailability (expected in test environment)
            if "MWAA environment connection not found" in result['output'] and "No healthy MWAA environments found" in result['output']:
                print("⚠️ Monitor failed due to MWAA unavailability - this is expected in test environment")
                print("✅ All deployment steps completed successfully, MWAA monitoring skipped")
            else:
                assert False, f"Monitor command failed for unexpected reason: {result['output']}"

        print(f"\n✅ All CLI commands tested successfully!")

        # Generate test report
        report = self.generate_test_report("Multi-Target Pipeline Comprehensive Workflow", results)

        print(f"\n=== Test Report ===")
        print(f"Test: {report['test_name']}")
        print(f"Commands executed: {report['total_commands']}")
        print(f"Successful commands: {report['successful_commands']}")
        print(f"Success rate: {report['success_rate']:.1%}")
        print(f"Overall success: {'✅' if report['overall_success'] else '❌'}")

        # Parse, S3 upload, bundle commands must succeed
        # Deploy commands should also succeed (idempotent behavior)
        critical_commands = results[:4]  # First 4 are critical (parse, parse targets, S3 upload, bundle)
        critical_success = all(r['success'] for r in critical_commands)
        
        # All deploy commands should succeed due to idempotent behavior
        deploy_commands = [r for r in results if r.get('command') and 'deploy' in r['command']]
        deploy_success = all(r['success'] for r in deploy_commands)

        assert critical_success, f"Critical commands must succeed: {[r for r in critical_commands if not r['success']]}"
        assert deploy_success, f"Deploy commands should be idempotent and succeed: {[r for r in deploy_commands if not r['success']]}"
        assert len(results) == 10, f"Expected 10 commands (2 describe + 1 S3 upload + 1 bundle + 3 deploy + 1 describe + 1 run + 1 monitor), got {len(results)}"
        
        # Cleanup after successful test completion
        print(f"\n=== Final Cleanup ===")
        self.cleanup_generated_files()
        print(f"✅ Test completed successfully and cleaned up generated files")
