"""Integration test for bundle zip deployment."""

import pytest
import os
import zipfile
import boto3
from pathlib import Path
from ..base import IntegrationTestBase


class TestBundleZipDeploy(IntegrationTestBase):
    """Test bundle zip creation and deployment workflow."""

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
        return os.path.join(os.path.dirname(__file__), "manifest.yaml")

    def create_bundle_zip(self, output_dir: str) -> str:
        """Create bundle zip matching deployment_configuration structure.
        
        Bundle structure must match deployment_configuration:
        - code/ -> maps to code/src in S3
        - data/ -> maps to code/data in S3
        - workflows/ -> maps to workflows in S3
        """
        pipeline_file = self.get_pipeline_file()
        code_dir = os.path.join(os.path.dirname(pipeline_file), "code")
        
        os.makedirs(output_dir, exist_ok=True)
        bundle_path = os.path.join(output_dir, "BundleZipDeployTest.zip")

        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add code section (from code/src/)
            src_dir = os.path.join(code_dir, "src")
            if os.path.exists(src_dir):
                for root, dirs, files in os.walk(src_dir):
                    for file in files:
                        if not file.endswith((".pyc", ".DS_Store")):
                            file_path = os.path.join(root, file)
                            arcname = os.path.join("code", os.path.relpath(file_path, src_dir))
                            zipf.write(file_path, arcname)

            # Add data section (from code/data/)
            data_dir = os.path.join(code_dir, "data")
            if os.path.exists(data_dir):
                for root, dirs, files in os.walk(data_dir):
                    for file in files:
                        if not file.endswith((".DS_Store",)):
                            file_path = os.path.join(root, file)
                            arcname = os.path.join("data", os.path.relpath(file_path, data_dir))
                            zipf.write(file_path, arcname)

            # Add workflows section (from code/workflows/)
            workflows_dir = os.path.join(code_dir, "workflows")
            if os.path.exists(workflows_dir):
                for root, dirs, files in os.walk(workflows_dir):
                    for file in files:
                        if not file.endswith((".pyc", ".DS_Store")):
                            file_path = os.path.join(root, file)
                            arcname = os.path.join("workflows", os.path.relpath(file_path, workflows_dir))
                            zipf.write(file_path, arcname)

        print(f"✅ Created bundle: {bundle_path}")
        return bundle_path

    def validate_bundle_structure(self, bundle_path: str):
        """Validate bundle has correct structure for deployment."""
        with zipfile.ZipFile(bundle_path, "r") as zipf:
            file_list = zipf.namelist()
            
            # Must have these top-level directories matching deployment_configuration names
            assert any(f.startswith("code/") for f in file_list), "Bundle missing 'code/' section"
            assert any(f.startswith("data/") for f in file_list), "Bundle missing 'data/' section"
            assert any(f.startswith("workflows/") for f in file_list), "Bundle missing 'workflows/' section"
            
            # Verify expected files
            assert any("test-notebook1.ipynb" in f for f in file_list), "Missing test-notebook1.ipynb"
            assert any("covid_analysis.ipynb" in f for f in file_list), "Missing covid_analysis.ipynb"
            assert any("foo.txt" in f for f in file_list), "Missing foo.txt"
            assert any("execute_notebooks_dag.py" in f for f in file_list), "Missing execute_notebooks_dag.py"
            
            print(f"✅ Bundle structure validated ({len(file_list)} files)")
            return file_list

    def validate_s3_deployment(self, pipeline_file: str):
        """Validate files were deployed to S3 correctly."""
        import yaml
        
        with open(pipeline_file, 'r') as f:
            manifest = yaml.safe_load(f)
        
        project_name = manifest['stages']['test']['project']['name']
        
        # Get project S3 bucket
        from smus_cicd.helpers.utils import get_datazone_project_info, build_domain_config
        from smus_cicd.application import ApplicationManifest
        app_manifest = ApplicationManifest.from_file(pipeline_file)
        test_config = app_manifest.stages['test']
        config = build_domain_config(test_config)
        project_info = get_datazone_project_info(project_name, config)
        
        s3_connection = project_info.get('connections', {}).get('default.s3_shared', {})
        s3_uri = s3_connection.get('s3Uri', '')
        
        if not s3_uri:
            pytest.fail("Could not get S3 URI from project")
        
        bucket = s3_uri.replace('s3://', '').split('/')[0]
        prefix = '/'.join(s3_uri.replace('s3://', '').split('/')[1:])
        
        s3 = boto3.client('s3')
        
        # Check expected files based on deployment_configuration
        expected_files = [
            f"{prefix}code/src/test-notebook1.ipynb",
            f"{prefix}code/src/covid_analysis.ipynb",
            f"{prefix}code/data/foo.txt",
            f"{prefix}workflows/dags/execute_notebooks_dag.py",
        ]
        
        found_files = []
        missing_files = []
        
        for expected_file in expected_files:
            try:
                s3.head_object(Bucket=bucket, Key=expected_file)
                found_files.append(expected_file)
                print(f"  ✅ Found: {expected_file}")
            except s3.exceptions.ClientError:
                missing_files.append(expected_file)
                print(f"  ❌ Missing: {expected_file}")
        
        assert len(missing_files) == 0, f"Missing files in S3: {missing_files}"
        print(f"\n✅ All {len(found_files)} files deployed correctly to S3")

    @pytest.mark.integration
    def test_bundle_zip_deploy(self):
        """Test bundle zip creation and deployment."""
        if not self.verify_aws_connectivity():
            pytest.skip("AWS connectivity not available")

        pipeline_file = self.get_pipeline_file()
        bundle_dir = "/tmp/bundle-zip-deploy-test"

        # Step 1: Create bundle zip
        print("\n=== Step 1: Create Bundle Zip ===")
        bundle_path = self.create_bundle_zip(bundle_dir)
        assert os.path.exists(bundle_path), f"Bundle not created: {bundle_path}"

        # Step 2: Validate bundle structure
        print("\n=== Step 2: Validate Bundle Structure ===")
        file_list = self.validate_bundle_structure(bundle_path)

        # Step 3: Deploy bundle
        print("\n=== Step 3: Deploy Bundle ===")
        result = self.run_cli_command(
            ["deploy", "--targets", "test", "--manifest", pipeline_file, "--bundle-archive-path", bundle_path]
        )
        
        assert result["success"], f"Deploy failed: {result['output']}"
        
        # Verify bootstrap print messages in output
        assert "Bundle Zip Deploy Test Started" in result["output"], "Missing bootstrap print message"
        assert "Deployment Complete" in result["output"], "Missing completion message"
        assert "Deployment completed successfully!" in result["output"], "Missing success message"
        print("✅ Deploy successful")

        print("\n✅ Bundle zip deploy test completed successfully!")
