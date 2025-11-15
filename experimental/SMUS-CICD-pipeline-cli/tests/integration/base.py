"""Base class for integration tests."""

import os
import re
import yaml
import boto3
import tempfile
import shutil
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
from typer.testing import CliRunner
from smus_cicd.cli import app


class IntegrationTestBase:
    """Base class for integration tests with AWS setup and cleanup."""

    # Class-level test results tracking
    _test_results = []
    _test_start_time = None

    def setup_debug_logging(self):
        """Set up debug logging to file and console."""
        if not hasattr(self, "debug_log_file"):
            # Use pytest's configured log directory instead of /tmp/
            log_dir = "tests/test-outputs"
            os.makedirs(log_dir, exist_ok=True)
            
            # Use current_test_name if available, otherwise use timestamp
            if hasattr(self, 'current_test_name'):
                test_name = self.current_test_name
            else:
                test_name = f"integration_test_{int(time.time())}"
            
            self.debug_log_file = os.path.join(log_dir, f"{test_name}.log")

        self.logger = logging.getLogger("integration_test_debug")
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        self.logger.handlers.clear()

        # File handler (mode='w' to overwrite, not append)
        file_handler = logging.FileHandler(self.debug_log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Console handler for real-time output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("🔍 %(message)s")
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        self.logger.info(f"=== Integration Test Debug Log Started ===")
        self.logger.info(f"Debug log file: {self.debug_log_file}")
        
        return self.logger

    def setup_method(self, method):
        """Setup for each test method."""
        if IntegrationTestBase._test_start_time is None:
            IntegrationTestBase._test_start_time = time.time()

        # Set test name first for log file naming
        test_name = f"{self.__class__.__name__}__{method.__name__}"
        self.current_test_name = test_name
        
        self.setup_debug_logging()
        self.config = self._load_config()
        self.runner = CliRunner()
        self.test_dir = None
        self.created_resources = []
        self.setup_aws_session()

        self.test_commands = []
        self.logger.info(f"=== Starting test: {method.__name__} ===")
        
        # Pre-register test result so pytest hooks can update it
        self.test_result = {
            "name": self.current_test_name,
            "commands": 0,
            "success": True,  # Will be updated by pytest hook if test fails
            "duration": 0,
        }
        IntegrationTestBase._test_results.append(self.test_result)

    def teardown_method(self, method):
        """Teardown for each test method."""
        # Update test result with final command counts and duration
        self.test_result["commands"] = len(self.test_commands)
        self.test_result["duration"] = sum(cmd.get("duration", 0) for cmd in self.test_commands)

        if hasattr(self, "test_dir"):
            self.cleanup_test_directory()

    @classmethod
    def print_test_summary(cls):
        """Print a comprehensive test summary."""
        if not cls._test_results:
            return

        total_time = time.time() - cls._test_start_time if cls._test_start_time else 0
        total_tests = len(cls._test_results)
        passed_tests = sum(1 for r in cls._test_results if r.get("success") is True)
        total_commands = sum(r["commands"] for r in cls._test_results)

        print("\n" + "=" * 80)
        print("🧪 INTEGRATION TEST SUMMARY")
        print("=" * 80)
        print(
            f"📊 Tests: {passed_tests}/{total_tests} passed ({passed_tests/total_tests*100:.1f}%)"
        )
        print(f"⚡ Commands: {total_commands} total executed")
        print(f"⏱️  Total time: {total_time:.1f}s")
        print()

        # Group by test class
        by_class = {}
        for result in cls._test_results:
            class_name = result["name"].split("::")[0] if "::" in result["name"] else result["name"].split("__")[0]
            if class_name not in by_class:
                by_class[class_name] = []
            by_class[class_name].append(result)

        for class_name, tests in by_class.items():
            class_passed = sum(1 for t in tests if t.get("success") is True)
            class_total = len(tests)
            status = "✅" if class_passed == class_total else "❌"
            print(f"{status} {class_name}: {class_passed}/{class_total}")

            for test in tests:
                test_status = "✅" if test.get("success") is True else "❌"
                # Handle both :: and __ separators
                if "::" in test["name"]:
                    method_name = test["name"].split("::")[1]
                elif "__" in test["name"]:
                    method_name = test["name"].split("__")[1]
                else:
                    method_name = test["name"]
                print(
                    f"   {test_status} {method_name} ({test['commands']} cmds, {test['duration']:.1f}s)"
                )

        print("=" * 80)

    def _load_config(self) -> Dict[str, Any]:
        """Load integration test configuration."""
        config_path = Path(__file__).parent / "config.local.yaml"
        if not config_path.exists():
            config_path = Path(__file__).parent / "config.yaml"

        with open(config_path, "r") as f:
            content = f.read()
            # Expand environment variables in the format ${VAR:default}
            import re

            def replace_env_var(match):
                var_expr = match.group(1)
                if ":" in var_expr:
                    var_name, default_value = var_expr.split(":", 1)
                    return os.environ.get(var_name, default_value)
                else:
                    return os.environ.get(var_expr, "")

            content = re.sub(r"\$\{([^}]+)\}", replace_env_var, content)
            return yaml.safe_load(content)

    def setup_aws_session(self):
        """Set up AWS session with current credentials."""
        # Use current session credentials instead of profile
        aws_config = self.config.get("aws", {})

        if aws_config.get("region"):
            os.environ["AWS_DEFAULT_REGION"] = aws_config["region"]

        # Verify AWS credentials are available before proceeding
        self._verify_aws_credentials()

        # Ensure current role is Lake Formation admin
        self.setup_lake_formation_admin()

    def _verify_aws_credentials(self):
        """Verify AWS credentials are available and fail fast if not."""
        try:
            import boto3

            sts_client = boto3.client(
                "sts", region_name=self.config.get("aws", {}).get("region", "us-east-1")
            )
            identity = sts_client.get_caller_identity()
            print(f"✅ AWS credentials verified: {identity['Arn']}")
        except Exception as e:
            error_msg = f"❌ AWS credentials not available: {str(e)}"
            print(error_msg)
            raise RuntimeError(
                f"Integration tests require valid AWS credentials. {error_msg}"
            ) from e

    def setup_lake_formation_admin(self):
        """Ensure current role is a Lake Formation admin (idempotent)."""
        try:
            import boto3

            lf_client = boto3.client(
                "lakeformation",
                region_name=self.config.get("aws", {}).get("region", "us-east-1"),
            )
            sts_client = boto3.client(
                "sts", region_name=self.config.get("aws", {}).get("region", "us-east-1")
            )

            # Get current identity
            identity = sts_client.get_caller_identity()
            assumed_role_arn = identity["Arn"]

            # Extract the role ARN from assumed role ARN
            # Format: arn:aws:sts::account:assumed-role/RoleName/SessionName
            # We want: arn:aws:iam::account:role/RoleName
            if "assumed-role" in assumed_role_arn:
                parts = assumed_role_arn.split("/")
                if len(parts) >= 3:
                    account_and_service = (
                        parts[0]
                        .replace(":sts:", ":iam:")
                        .replace(":assumed-role", ":role")
                    )
                    role_name = parts[1]
                    role_arn = f"{account_and_service}/{role_name}"
                else:
                    role_arn = assumed_role_arn
            else:
                role_arn = assumed_role_arn

            # Get current Lake Formation settings
            try:
                current_settings = lf_client.get_data_lake_settings()
                current_admins = current_settings.get("DataLakeSettings", {}).get(
                    "DataLakeAdmins", []
                )

                # Check if role ARN is already an admin
                admin_arns = [
                    admin.get("DataLakePrincipalIdentifier") for admin in current_admins
                ]

                if role_arn not in admin_arns:
                    # Add role ARN to existing admins
                    current_admins.append({"DataLakePrincipalIdentifier": role_arn})

                    lf_client.put_data_lake_settings(
                        DataLakeSettings={"DataLakeAdmins": current_admins}
                    )
                    print(f"✅ Added {role_arn} as Lake Formation admin")
                else:
                    print(f"✅ {role_arn} is already a Lake Formation admin")

            except Exception as e:
                print(f"⚠️ Lake Formation admin setup: {e}")

        except Exception as e:
            print(f"⚠️ Lake Formation setup failed: {e}")

    def setup_test_directory(self):
        """Create temporary test directory."""
        self.test_dir = tempfile.mkdtemp(prefix="smus_integration_test_")
        return self.test_dir

    def cleanup_test_directory(self):
        """Clean up temporary test directory."""
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def get_pipeline_path(self, pipeline_file: str) -> str:
        """Get full path to pipeline file."""
        return str(Path(__file__).parent / pipeline_file)

    def upload_code_to_dev_project(
        self,
        pipeline_file: str,
        source_dir: str,
        target_prefix: str,
        exclude_patterns: list = None
    ) -> bool:
        """Upload code to dev project S3 bucket.
        
        Args:
            pipeline_file: Path to pipeline manifest file
            source_dir: Local directory to upload (relative to test file)
            target_prefix: S3 prefix to upload to (e.g., "ml/", "genai/")
            exclude_patterns: Optional list of patterns to exclude
            
        Returns:
            True if upload succeeded, False otherwise
        """
        # Get S3 URI from dev project
        result = self.run_cli_command(["describe", "--manifest", pipeline_file, "--connect"])
        if not result["success"]:
            print(f"❌ Failed to describe pipeline: {result['output']}")
            return False
        
        s3_uri_match = re.search(
            r"dev: dev-marketing.*?default\.s3_shared:.*?s3Uri: (s3://[^\s]+)",
            result["output"],
            re.DOTALL
        )
        
        if not s3_uri_match:
            print("❌ Could not extract S3 URI from describe output")
            return False
        
        s3_uri = s3_uri_match.group(1)
        print(f"📍 Dev S3 URI: {s3_uri}")
        
        # Resolve source directory
        if not os.path.isabs(source_dir):
            print(f"❌ Source directory must be absolute path: {source_dir}")
            return False
        
        if not os.path.exists(source_dir):
            print(f"❌ Source directory not found: {source_dir}")
            return False
        
        # Default exclude patterns
        if exclude_patterns is None:
            exclude_patterns = ["*.pyc", "__pycache__/*", ".ipynb_checkpoints/*"]
        
        # Sync to S3
        target_uri = s3_uri + target_prefix
        print(f"🔄 Uploading {source_dir} to {target_uri}")
        
        try:
            self.sync_to_s3(source_dir, target_uri, exclude_patterns=exclude_patterns)
            print("✅ Upload completed")
            return True
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return False

    def sync_to_s3(
        self,
        source_dir: str,
        s3_uri: str,
        exclude_patterns: list = None
    ) -> None:
        """Sync local directory to S3 with proper error handling.
        
        Args:
            source_dir: Local directory to sync
            s3_uri: S3 URI destination (e.g., s3://bucket/prefix/)
            exclude_patterns: List of patterns to exclude (optional)
        
        Raises:
            AssertionError: If sync fails
        """
        import subprocess
        
        if exclude_patterns is None:
            exclude_patterns = [
                "*.pyc",
                "__pycache__/*",
                ".ipynb_checkpoints/*",
                "*_bundle.yaml",
                "*.md"
            ]
        
        cmd = ["aws", "s3", "sync", source_dir, s3_uri]
        for pattern in exclude_patterns:
            cmd.extend(["--exclude", pattern])
        
        print(f"🔄 Syncing {source_dir} to {s3_uri}")
        print(f"   Exclude patterns: {exclude_patterns}")
        self.logger.info(f"Syncing {source_dir} to {s3_uri}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.stdout:
            print(f"   Output: {result.stdout[:200]}")
            self.logger.info(f"S3 sync output: {result.stdout}")
        if result.stderr:
            print(f"   Stderr: {result.stderr[:200]}")
            self.logger.warning(f"S3 sync stderr: {result.stderr}")
        
        if result.returncode != 0:
            print(f"❌ S3 sync failed with code {result.returncode}")
            self.logger.error(f"S3 sync failed with code {result.returncode}")
            assert False, f"S3 sync failed: {result.stderr}"
        
        print(f"✅ Successfully synced to {s3_uri}")
        self.logger.info(f"✅ Successfully synced to {s3_uri}")

    def run_cli_command(
        self, command: list, expected_exit_code: int = 0
    ) -> Dict[str, Any]:
        """Run CLI command and return result with validation."""
        cmd_str = " ".join(command)
        self.logger.info(f"EXECUTING CLI COMMAND: {cmd_str}")

        start_time = time.time()
        result = self.runner.invoke(app, command)
        end_time = time.time()

        duration = end_time - start_time
        
        # Log the full output to both console and file
        if result.output:
            # Split output into lines and log each
            for line in result.output.splitlines():
                self.logger.info(f"  {line}")
        
        self.logger.info(
            f"COMMAND COMPLETED in {duration:.2f}s - Exit code: {result.exit_code}"
        )

        command_result = {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "output": result.output,
            "success": result.exit_code == expected_exit_code,
            "command": cmd_str,
            "duration": duration,
        }

        # Track command for test summary
        self.test_commands.append(command_result)

        if result.exit_code != expected_exit_code:
            self.logger.error(
                f"COMMAND FAILED - Expected exit code {expected_exit_code}, got {result.exit_code}"
            )

        return command_result

    def run_cli_command_streaming(self, command: list) -> Dict[str, Any]:
        """Run CLI command with live streaming output."""
        import subprocess
        import sys
        
        cmd_str = " ".join(command)
        self.logger.info(f"EXECUTING CLI COMMAND (STREAMING): {cmd_str}")
        
        # Build full command
        full_cmd = [sys.executable, "-m", "smus_cicd.cli"] + command
        
        start_time = time.time()
        output_lines = []
        
        try:
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Stream output line by line
            for line in iter(process.stdout.readline, ''):
                if line:
                    line = line.rstrip()
                    print(line, flush=True)  # Print to console immediately
                    self.logger.info(f"  {line}")
                    output_lines.append(line)
            
            process.wait()
            exit_code = process.returncode
            
        except Exception as e:
            self.logger.error(f"COMMAND FAILED: {e}")
            exit_code = 1
            output_lines.append(f"Error: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        self.logger.info(f"COMMAND COMPLETED in {duration:.2f}s - Exit code: {exit_code}")
        
        output = "\n".join(output_lines)
        command_result = {
            "exit_code": exit_code,
            "stdout": output,
            "output": output,
            "success": exit_code == 0,
            "command": cmd_str,
            "duration": duration,
        }
        
        self.test_commands.append(command_result)
        return command_result

    def verify_aws_connectivity(self) -> bool:
        """Verify AWS connectivity and permissions."""
        self.logger.info("CHECKING AWS connectivity...")
        try:
            # Use current session credentials, not profile-based
            sts = boto3.client("sts")
            identity = sts.get_caller_identity()
            self.logger.info(f"AWS identity verified: {identity.get('Arn')}")

            # Basic STS access is sufficient for most tests
            # DataZone access is optional and may not be available in all environments
            try:
                endpoint_url = os.environ.get("AWS_ENDPOINT_URL_DATAZONE")
                region = os.environ.get("DEV_DOMAIN_REGION", self.config["aws"]["region"])
                datazone = boto3.client(
                    "datazone", region_name=region, endpoint_url=endpoint_url
                )
                domains = datazone.list_domains(maxResults=1)
                self.logger.info("DataZone access verified")
            except Exception as datazone_error:
                # DataZone access not available, but STS works, so continue
                self.logger.warning(
                    f"DataZone access not available (this is OK): {datazone_error}"
                )

            return True
        except Exception as e:
            self.logger.error(f"AWS connectivity check failed: {e}")
            return False

    def check_domain_exists(self, domain_name: str) -> bool:
        """Check if DataZone domain exists."""
        try:
            datazone = boto3.client(
                "datazone", region_name=self.config["aws"]["region"]
            )
            domains = datazone.list_domains()

            for domain in domains.get("items", []):
                if domain.get("name") == domain_name:
                    return True
            return False
        except Exception:
            return False

    def check_project_exists(self, domain_name: str, project_name: str) -> bool:
        """Check if DataZone project exists."""
        try:
            from smus_cicd import datazone as dz_utils

            domain_id = dz_utils.get_domain_id_by_name(
                domain_name, self.config["aws"]["region"]
            )
            if not domain_id:
                return False

            project_id = dz_utils.get_project_id_by_name(
                project_name, domain_id, self.config["aws"]["region"]
            )
            return project_id is not None
        except Exception:
            return False

    def cleanup_resources(self):
        """Clean up created AWS resources if configured."""
        if not self.config.get("test_environment", {}).get("cleanup_after_tests", True):
            return

        # Cleanup logic would go here
        # For now, just log what would be cleaned up
        if self.created_resources:
            print(f"Would clean up resources: {self.created_resources}")

    def get_airflow_client(self):
        """Get boto3 client for Airflow Serverless."""
        import boto3
        region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-2')
        endpoint = os.environ.get('AIRFLOW_SERVERLESS_ENDPOINT', f'https://airflow-serverless.{region}.api.aws/')
        return boto3.client('mwaaserverless-internal', region_name=region, endpoint_url=endpoint)

    def get_workflow_arn(self, expected_workflow_name: str) -> str:
        """Get workflow ARN by name.
        
        Args:
            expected_workflow_name: Expected workflow name
            
        Returns:
            Workflow ARN
        """
        client = self.get_airflow_client()
        response = client.list_workflows()
        for wf in response.get('Workflows', []):
            if wf.get('Name') == expected_workflow_name:
                return wf.get('WorkflowArn')
        raise AssertionError(f"Could not find workflow: {expected_workflow_name}")

    def check_active_workflow_runs(self, workflow_arn: str) -> list:
        """Check for active workflow runs.
        
        Args:
            workflow_arn: Workflow ARN
            
        Returns:
            List of active run IDs
        """
        client = self.get_airflow_client()
        runs_response = client.list_workflow_runs(WorkflowArn=workflow_arn, MaxResults=5)
        active_runs = [r for r in runs_response.get('WorkflowRuns', []) 
                       if r.get('Status') in ['RUNNING', 'QUEUED']]
        return [r.get('RunId') for r in active_runs]

    def verify_workflow_status(self, workflow_arn: str, run_id: str, expected_status: str = 'SUCCESS') -> None:
        """Verify workflow run completed with expected status.
        
        Args:
            workflow_arn: Workflow ARN
            run_id: Run ID to check
            expected_status: Expected status (default: SUCCESS)
            
        Raises:
            AssertionError if status doesn't match
        """
        client = self.get_airflow_client()
        run_response = client.get_workflow_run(WorkflowArn=workflow_arn, RunId=run_id)
        actual_status = run_response.get('RunDetail', {}).get('RunState')
        print(f"📊 Workflow Run ID: {run_id}")
        print(f"📊 Final Status: {actual_status}")
        assert actual_status == expected_status, f"Workflow did not complete successfully. Status: {actual_status}"
        print(f"✅ Workflow completed with {expected_status} status")

    def download_and_validate_notebooks(self, workflow_arn: str, run_id: str) -> bool:
        """Download workflow notebook outputs using GetTaskInstance API and validate for errors.
        
        Args:
            workflow_arn: Workflow ARN to query task instances
            run_id: Workflow run ID
            
        Returns:
            True if notebooks downloaded and contain no errors, False otherwise
        """
        import subprocess
        import tarfile
        import json
        import boto3
        import os
        
        # Extract workflow name from ARN (format: arn:aws:airflow-serverless:region:account:workflow/workflow-name)
        workflow_name = workflow_arn.split('/')[-1] if '/' in workflow_arn else run_id
        
        output_dir = Path("tests/test-outputs/notebooks") / workflow_name
        
        # Clean up old notebooks for this workflow (replace with latest run)
        if output_dir.exists():
            import shutil
            print(f"🧹 Cleaning up old notebooks from {output_dir}")
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n=== Downloading Workflow Notebooks ===")
        print(f"Workflow ARN: {workflow_arn}")
        print(f"Run ID: {run_id}")
        
        # Get task instances from workflow run
        region = os.environ.get('DEV_DOMAIN_REGION', 'us-east-2')
        endpoint = os.environ.get('AIRFLOW_SERVERLESS_ENDPOINT', f'https://airflow-serverless.{region}.api.aws/')
        client = boto3.client('mwaaserverless-internal', region_name=region, endpoint_url=endpoint)
        
        # List task instances for this run
        try:
            response = client.list_task_instances(WorkflowArn=workflow_arn, RunId=run_id)
        except Exception as e:
            print(f"❌ Error listing task instances: {e}")
            return False
        
        task_instances = response.get('TaskInstances', [])
        if not task_instances:
            print("❌ No task instances found")
            return False
        
        print(f"Found {len(task_instances)} task instances")
        
        downloaded_notebooks = []
        
        for task in task_instances:
            task_id = task.get('TaskInstanceId')
            task_name = task.get('TaskId') or task_id or 'unknown'
            
            print(f"\n🔍 Checking task: {task_name} (ID: {task_id})")
            
            # Get task instance details including Xcom
            try:
                task_detail = client.get_task_instance(
                    WorkflowArn=workflow_arn,
                    RunId=run_id,
                    TaskInstanceId=task_id
                )
            except Exception as e:
                print(f"⚠️ Error getting task details: {e}")
                continue
            
            # Check if task has notebook output in Xcom
            xcom = task_detail.get('Xcom', {})
            print(f"   XCom keys: {list(xcom.keys())}")
            
            # Try different XCom keys
            notebook_output = (
                xcom.get('notebook_output') or 
                xcom.get('return_value') or 
                xcom.get('sagemaker_unified_studio') or
                xcom.get('s3_path')
            )
            
            # Remove quotes if present (some XCom values are JSON-encoded strings)
            if notebook_output and isinstance(notebook_output, str):
                notebook_output = notebook_output.strip('"')
                # Fix path if it points to model.tar.gz instead of output.tar.gz
                if notebook_output.endswith('/output/model.tar.gz'):
                    notebook_output = notebook_output.replace('/output/model.tar.gz', '/output/output.tar.gz')
                    print(f"   🔧 Corrected path to output.tar.gz")
            
            if not notebook_output:
                print(f"   ⚠️ No notebook output found in XCom")
                continue
            
            print(f"\n📓 Task: {task_name}")
            print(f"   Output: {notebook_output}")
            
            # Download notebook from S3
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
                tmp_path = tmp.name
            
            result = subprocess.run(
                ["aws", "s3", "cp", notebook_output, tmp_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"  ❌ Error downloading: {result.stderr}")
                Path(tmp_path).unlink(missing_ok=True)
                continue
            
            # Extract notebooks
            task_dir = output_dir / task_name
            task_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                with tarfile.open(tmp_path, "r:gz") as tar:
                    for member in tar.getmembers():
                        if member.name.startswith("_") and member.name.endswith(".ipynb"):
                            tar.extract(member, task_dir)
                            notebook_path = task_dir / member.name
                            downloaded_notebooks.append(notebook_path)
                            print(f"  ✅ {notebook_path}")
            except Exception as e:
                print(f"  ❌ Error extracting: {e}")
                return False
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        
        if not downloaded_notebooks:
            print("❌ No notebooks downloaded from task instances")
            return False
        
        print(f"\n✅ Downloaded {len(downloaded_notebooks)} notebooks")
        
        # Validate notebooks for errors
        print("\n=== Validating Notebooks ===")
        has_errors = False
        
        for notebook_path in downloaded_notebooks:
            try:
                with open(notebook_path) as f:
                    notebook = json.load(f)
                
                error_count = 0
                for cell in notebook.get("cells", []):
                    for output in cell.get("outputs", []):
                        if output.get("output_type") == "error":
                            error_count += 1
                            if not has_errors:
                                print(f"❌ Errors found in {notebook_path.name}:")
                            has_errors = True
                            print(f"  - {output.get('ename', 'Error')}: {output.get('evalue', '')}")
                
                if error_count == 0:
                    print(f"✅ {notebook_path.name}: No errors")
            except Exception as e:
                print(f"❌ Error reading {notebook_path.name}: {e}")
                has_errors = True
        
        return not has_errors

    def generate_test_report(self, test_name: str, results: list) -> Dict[str, Any]:
        """Generate test report."""
        total_commands = len(results)
        successful_commands = sum(1 for r in results if r["success"])

        return {
            "test_name": test_name,
            "total_commands": total_commands,
            "successful_commands": successful_commands,
            "success_rate": (
                successful_commands / total_commands if total_commands > 0 else 0
            ),
            "overall_success": successful_commands == total_commands,
            "results": results,
        }
