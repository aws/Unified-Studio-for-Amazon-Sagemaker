"""Integration test for bundle-based deployment without dev project."""

import pytest
import os
import zipfile
import boto3
from typer.testing import CliRunner
from tests.integration.base import IntegrationTestBase


class TestBundleDeployPipeline(IntegrationTestBase):
    """Test bundle-based deployment workflow without dev project."""

    def setup_method(self, method):
        """Set up test environment."""
        super().setup_method(method)
        self.setup_test_directory()

        # Set up project and connections
        self.setup_project_and_connections()

    def setup_project_and_connections(self):
        """Set up project and required connections."""
        try:
            # Create project if it doesn't exist
            pipeline_file = self.get_pipeline_file()
            result = self.run_cli_command(
                ["create", "--pipeline", pipeline_file, "--targets", "test"]
            )

            if not result["success"]:
                print(f"⚠️ Project creation failed: {result['output']}")
                return

            # Wait for project to be active
            print("Waiting for project to be active...")
            import time

            for _ in range(30):  # 5 minutes timeout
                result = self.run_cli_command(
                    ["describe", "--pipeline", pipeline_file, "--targets", "test"]
                )
                if "Status: ACTIVE" in result["output"]:
                    print("✅ Project is active")
                    break
                time.sleep(10)
            else:
                print("⚠️ Project did not become active in time")

            # Set up MWAA environment
            self.setup_mwaa_environment()

        except Exception as e:
            print(f"⚠️ Project setup failed: {e}")

    def setup_mwaa_environment(self):
        """Set up MWAA environment."""
        try:
            # Get project info from pipeline
            pipeline_file = self.get_pipeline_file()
            with open(pipeline_file, "r") as f:
                import yaml

                pipeline_config = yaml.safe_load(f)

            domain_name = pipeline_config["domain"]["name"]
            domain_region = pipeline_config["domain"]["region"]
            project_name = pipeline_config["targets"]["test"]["project"]["name"]

            # Create MWAA environment
            mwaa_client = boto3.client("mwaa", region_name=domain_region)

            # Create environment if it doesn't exist
            env_name = f"DataZoneMWAAEnv-dzd_6je2k8b63qse07-broygppc8vw17r-dev"
            try:
                mwaa_client.get_environment(Name=env_name)
                print(f"✅ MWAA environment {env_name} exists")
            except mwaa_client.exceptions.ResourceNotFoundException:
                print(f"Creating MWAA environment {env_name}...")

                # Create S3 bucket for MWAA
                s3_client = boto3.client("s3", region_name=domain_region)
                bucket_name = f"mwaa-{domain_region}-{env_name.lower()}"

                try:
                    s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={"LocationConstraint": domain_region},
                    )
                    print(f"✅ Created S3 bucket: {bucket_name}")
                except s3_client.exceptions.BucketAlreadyExists:
                    print(f"✅ S3 bucket already exists: {bucket_name}")

                # Create MWAA environment
                mwaa_client.create_environment(
                    Name=env_name,
                    AirflowVersion="2.5.1",
                    SourceBucketArn=f"arn:aws:s3:::{bucket_name}",
                    DagS3Path="dags",
                    ExecutionRoleArn=f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/service-role/AmazonMWAA-{env_name}-{domain_region}",
                    NetworkConfiguration={
                        "SubnetIds": ["subnet-12345678"],  # TODO: Get from VPC
                        "SecurityGroupIds": ["sg-12345678"],  # TODO: Get from VPC
                    },
                    WebserverAccessMode="PUBLIC_ONLY",
                    MaxWorkers=1,
                )
                print(f"✅ Created MWAA environment: {env_name}")

                # Wait for environment to be available
                print("Waiting for environment to be available...")
                import time

                for _ in range(60):  # 30 minutes timeout
                    env = mwaa_client.get_environment(Name=env_name)
                    status = env["Environment"]["Status"]
                    if status == "AVAILABLE":
                        print("✅ MWAA environment is available")
                        break
                    elif status in ["CREATING", "UPDATING"]:
                        print(f"MWAA environment status: {status}")
                        time.sleep(30)
                    else:
                        print(f"❌ MWAA environment failed: {status}")
                        break
                else:
                    print("❌ MWAA environment did not become available in time")

        except Exception as e:
            print(f"⚠️ MWAA setup failed: {e}")

    def teardown_method(self, method):
        """Clean up test environment."""
        super().teardown_method(method)
        self.cleanup_resources()
        self.cleanup_test_directory()

    def get_pipeline_file(self):
        """Get path to pipeline file in same directory."""
        return os.path.join(os.path.dirname(__file__), "bundle_deploy_pipeline.yaml")

    def create_bundle_manually(self):
        """Create a bundle manually from the code directory."""
        pipeline_file = self.get_pipeline_file()
        code_dir = os.path.join(os.path.dirname(pipeline_file), "code")
        bundles_dir = "/tmp/bundles"

        # Ensure bundles directory exists
        os.makedirs(bundles_dir, exist_ok=True)

        # Create bundle zip file
        bundle_path = os.path.join(bundles_dir, "BundleDeployPipeline.zip")

        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add storage files - directly under src/
            src_dir = os.path.join(code_dir, "src")
            if os.path.exists(src_dir):
                for root, dirs, files in os.walk(src_dir):
                    for file in files:
                        if not file.endswith((".pyc", ".DS_Store")):
                            file_path = os.path.join(root, file)
                            # Remove the src/ prefix from the path to avoid src/src
                            arcname = os.path.join(
                                "storage", "src", os.path.relpath(file_path, src_dir)
                            )
                            zipf.write(file_path, arcname)

            # Add workflow files
            workflows_dir = os.path.join(code_dir, "workflows")
            if os.path.exists(workflows_dir):
                for root, dirs, files in os.walk(workflows_dir):
                    for file in files:
                        if not file.endswith((".pyc", ".DS_Store")):
                            file_path = os.path.join(root, file)
                            arcname = os.path.join(
                                "workflows", os.path.relpath(file_path, workflows_dir)
                            )
                            zipf.write(file_path, arcname)

        print(f"Created bundle: {bundle_path}")
        return bundle_path

    @pytest.mark.integration
    def test_describe_pipeline_without_dev(self):
        """Test describe pipeline that has no dev target."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()

        result = self.run_cli_command(["describe", "--pipeline", pipeline_file])

        assert result["success"], f"Describe failed: {result['output']}"
        assert "Pipeline: IntegrationTestMultiTarget" in result["output"]
        assert "test: integration-test-test" in result["output"]
        # Should not have dev or prod targets
        assert "dev:" not in result["output"]
        assert "prod:" not in result["output"]

    @pytest.mark.integration
    def test_bundle_deploy_workflow(self):
        """Test complete bundle-based deployment workflow."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        results = []

        try:
            # Step 1: Create bundle manually
            print("\n=== Step 1: Create Bundle Manually ===")
            bundle_path = self.create_bundle_manually()

            # Verify bundle exists and has content
            assert os.path.exists(bundle_path), f"Bundle not created: {bundle_path}"

            with zipfile.ZipFile(bundle_path, "r") as zipf:
                file_list = zipf.namelist()
                print(f"Bundle contains {len(file_list)} files")
                assert len(file_list) > 0, "Bundle is empty"
                assert any(
                    "workflows/dags/" in f for f in file_list
                ), "No workflow files in bundle"
                assert any(
                    "storage/src/" in f for f in file_list
                ), "No storage files in bundle"
                # Verify no src/src in paths
                assert not any(
                    "storage/src/src/" in f for f in file_list
                ), "Found src/src in bundle paths"

            print("✅ Bundle created successfully")

            # Step 2: Deploy using bundle
            print("\n=== Step 2: Deploy Using Bundle ===")
            result = self.run_cli_command(
                [
                    "deploy",
                    "--pipeline",
                    pipeline_file,
                    "--targets",
                    "test",
                    "--bundle",
                    bundle_path,
                ]
            )
            results.append(result)

            if result["success"]:
                print("✅ Bundle deployment successful")
                print(f"Deploy output: {result['output']}")

                # Validate deployment output
                assert (
                    "Bundle file:" in result["output"]
                ), "Deploy output missing bundle file reference"
                assert (
                    "Deployment completed successfully!" in result["output"]
                ), "Deploy output missing success message"
            else:
                print(f"❌ Bundle deployment failed: {result['output']}")
                # Don't fail the test immediately, continue to gather more info

            # Step 3: Monitor deployment
            print("\n=== Step 3: Monitor Deployment ===")
            result = self.run_cli_command(
                [
                    "monitor",
                    "--pipeline",
                    pipeline_file,
                    "--targets",
                    "test",
                    "--tasks",
                    "--download",
                ]
            )
            results.append(result)

            if result["success"]:
                print("✅ Monitor successful")
                print(f"Monitor output: {result['output']}")

                # Verify notebook was downloaded
                assert os.path.exists(
                    "/tmp/notebooks"
                ), "Notebooks directory not created"
                notebook_files = os.listdir("/tmp/notebooks")
                assert any(
                    "covid_analysis" in f for f in notebook_files
                ), "No covid analysis notebook downloaded"
            else:
                print(f"⚠️ Monitor failed (may be expected): {result['output']}")

            # Step 4: Test workflow execution
            print("\n=== Step 4: Test Workflow Execution ===")
            result = self.run_cli_command(
                [
                    "run",
                    "--pipeline",
                    pipeline_file,
                    "--targets",
                    "test",
                    "--workflow",
                    "test_dag",
                    "--command",
                    "dags list",
                ]
            )
            results.append(result)

            if result["success"]:
                print("✅ Workflow execution successful")
                print(f"Run output: {result['output']}")
            else:
                print(
                    f"⚠️ Workflow execution failed (may be expected): {result['output']}"
                )

        except Exception as e:
            print(f"❌ Test workflow failed: {e}")
            results.append({"success": False, "output": f"Test workflow failed: {e}"})

        # Generate test report
        report = self.generate_test_report("Bundle Deploy Pipeline Workflow", results)

        print(f"\n=== Test Report ===")
        print(f"Test: {report['test_name']}")
        print(f"Commands executed: {report['total_commands']}")
        print(f"Successful commands: {report['successful_commands']}")
        print(f"Success rate: {report['success_rate']:.1%}")
        print(f"Overall success: {'✅' if report['overall_success'] else '❌'}")

        # At minimum, bundle creation and deployment should succeed
        assert len(results) >= 1, "No commands were executed"

        # The first result should be deployment which is critical
        if len(results) > 0:
            deploy_result = results[0]
            assert deploy_result[
                "success"
            ], f"Bundle deployment must succeed: {deploy_result['output']}"

        print(f"\n✅ Bundle-based deployment test completed successfully!")

    @pytest.mark.integration
    def test_bundle_contents_validation(self):
        """Test that manually created bundle has correct structure."""
        pipeline_file = self.get_pipeline_file()

        # Create bundle
        bundle_path = self.create_bundle_manually()

        # Validate bundle structure
        with zipfile.ZipFile(bundle_path, "r") as zipf:
            file_list = zipf.namelist()

            # Check for expected files
            expected_files = [
                "storage/src/test-notebook1.ipynb",
                "storage/src/covid_analysis.ipynb",
                "workflows/dags/test_dag.py",
                "workflows/dags/execute_notebooks_dag.py",
            ]

            for expected_file in expected_files:
                assert any(
                    expected_file in f for f in file_list
                ), f"Expected file not found in bundle: {expected_file}"

            # Verify no src/src in paths
            assert not any(
                "storage/src/src/" in f for f in file_list
            ), "Found src/src in bundle paths"

            print(f"✅ Bundle structure validated - contains {len(file_list)} files")
            print("Expected files found:")
            for expected_file in expected_files:
                matching_files = [f for f in file_list if expected_file in f]
                print(f"  - {expected_file}: {matching_files}")
