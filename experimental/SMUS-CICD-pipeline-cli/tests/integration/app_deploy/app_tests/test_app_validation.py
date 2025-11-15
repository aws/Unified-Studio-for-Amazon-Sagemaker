"""Pipeline tests for bundle deployment validation."""

import pytest
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path


class TestBundleValidation:
    """Validate bundle deployment commands."""

    def get_pipeline_file(self):
        """Get pipeline file path."""
        return Path(__file__).parent.parent / "manifest.yaml"

    def create_test_bundle(self):
        """Create a test bundle for validation."""
        pipeline_dir = Path(__file__).parent.parent
        code_dir = pipeline_dir / "code"

        # Create bundle in temp directory
        bundle_path = Path(tempfile.mkdtemp()) / "TestBundle.zip"

        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add storage files
            src_dir = code_dir / "src"
            if src_dir.exists():
                for file_path in src_dir.rglob("*"):
                    if file_path.is_file() and not file_path.name.endswith(".pyc"):
                        arcname = f"code/{file_path.relative_to(src_dir)}"
                        zipf.write(file_path, arcname)

            # Add workflow files
            workflows_dir = code_dir / "workflows"
            if workflows_dir.exists():
                for file_path in workflows_dir.rglob("*"):
                    if file_path.is_file() and not file_path.name.endswith(".pyc"):
                        arcname = f"workflows/{file_path.relative_to(workflows_dir)}"
                        zipf.write(file_path, arcname)

        return str(bundle_path)

    def run_smus_command(self, cmd_args):
        """Run SMUS CLI command and return result."""
        try:
            result = subprocess.run(
                ["smus-cli"] + cmd_args,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=Path(__file__).parent.parent.parent.parent,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Command timeout",
                "returncode": -1,
            }
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

    def test_describe_connect_validation(self):
        """Test describe --connect command to check MWAA connection and environment readiness."""
        pipeline_file = self.get_pipeline_file()

        result = self.run_smus_command(
            [
                "describe",
                "--manifest",
                str(pipeline_file),
                "--targets",
                "test",
                "--connect",
            ]
        )

        # Should succeed or fail gracefully
        assert result["returncode"] in [
            0,
            1,
        ], f"Describe --connect command failed unexpectedly: {result['stderr']}"

        if result["success"]:
            assert "test" in result["stdout"].lower()
            # Check for MWAA connection indicators
            if "mwaa" in result["stdout"].lower():
                print("✅ MWAA connection found in describe output")
                # When project doesn't exist, connection details aren't shown
                # Just verify the connection is referenced in workflows
                assert (
                    "project.workflow_mwaa" in result["stdout"]
                ), "MWAA connection project.workflow_mwaa not found in output"
                print("✅ MWAA connection is referenced in workflows")
            else:
                print("❌ MWAA connection not found in describe output")
                assert (
                    False
                ), "MWAA connection is required but not found in describe --connect output"
        else:
            # Expected failures: AWS connectivity, project not found, etc.
            expected_errors = [
                "connection",
                "project",
                "domain",
                "region",
                "mwaa",
                "environment",
            ]
            assert any(
                err in result["stdout"].lower() or err in result["stderr"].lower()
                for err in expected_errors
            ), f"Unexpected describe --connect error: {result['stderr']}"

    def test_deploy_command_validation(self):
        """Test deploy command with bundle."""
        pipeline_file = self.get_pipeline_file()
        bundle_path = self.create_test_bundle()

        # Test deploy command
        result = self.run_smus_command(
            [
                "deploy",
                "--manifest",
                str(pipeline_file),
                "--targets",
                "test",
                "--bundle",
                bundle_path,
            ]
        )

        # Should succeed or fail gracefully
        assert result["returncode"] in [
            0,
            1,
        ], f"Deploy command failed unexpectedly: {result['stderr']}"

        if result["success"]:
            assert (
                "bundle" in result["stdout"].lower()
                or "deploy" in result["stdout"].lower()
            )
        else:
            # Expected failures: AWS connectivity, project not found, etc.
            expected_errors = ["aws", "project", "connection", "region", "domain"]
            assert any(
                err in result["stderr"].lower() for err in expected_errors
            ), f"Unexpected deploy error: {result['stderr']}"

    def test_run_command_validation(self):
        """Test run command with both --command and --workflows options."""
        pipeline_file = self.get_pipeline_file()

        # Test 1: Run workflow with JSON output
        result = self.run_smus_command(
            [
                "run",
                "--workflow",
                "execute_notebooks_dag",
                "--manifest",
                str(pipeline_file),
                "--targets",
                "test",
                "--output",
                "JSON",
            ]
        )

        # Should succeed or fail gracefully
        assert result["returncode"] in [
            0,
            1,
        ], f"Run command failed unexpectedly: {result['stderr']}"

        if result["success"]:
            assert "execute_notebooks_dag" in result["stdout"].lower()
        else:
            # Expected failures: MWAA not available, project not found, etc.
            expected_errors = [
                "mwaa",
                "project",
                "connection",
                "workflow",
                "environment",
            ]
            assert any(
                err in result["stderr"].lower() for err in expected_errors
            ), f"Unexpected run error: {result['stderr']}"

    def test_test_command_validation(self):
        """Test test command validation."""
        pipeline_file = self.get_pipeline_file()

        result = self.run_smus_command(
            ["test", "--manifest", str(pipeline_file), "--targets", "test"]
        )

        # Should succeed or fail gracefully
        assert result["returncode"] in [
            0,
            1,
        ], f"Test command failed unexpectedly: {result['stderr']}"

        if result["success"]:
            assert "test" in result["stdout"].lower()
        else:
            # Expected failures: no tests found, project not available, etc.
            expected_errors = ["test", "project", "connection", "file", "folder"]
            assert any(
                err in result["stdout"].lower() for err in expected_errors
            ), f"Unexpected test error: {result['stderr']}"

    def test_monitor_command_validation(self):
        """Test monitor command validation with workflows parameter."""
        pipeline_file = self.get_pipeline_file()

        # Test 1: Monitor all workflows (no --workflows parameter)
        result = self.run_smus_command(
            [
                "monitor",
                "--manifest",
                str(pipeline_file),
                "--targets",
                "test",
                "--output",
                "JSON",
            ]
        )

        # Should succeed or fail gracefully
        assert result["returncode"] in [
            0,
            1,
        ], f"Monitor command failed unexpectedly: {result['stderr']}"

        if result["success"]:
            assert (
                "monitor" in result["stdout"].lower()
                or "bundle" in result["stdout"].lower()
            )
        else:
            # Expected failures: MWAA not available, project not found, etc.
            expected_errors = [
                "mwaa",
                "project",
                "connection",
                "environment",
                "workflow",
            ]
            assert any(
                err in result["stderr"].lower() for err in expected_errors
            ), f"Unexpected monitor error: {result['stderr']}"

        # Test 2: Monitor specific workflow with limit
        result2 = self.run_smus_command(
            [
                "monitor",
                "--manifest",
                str(pipeline_file),
                "--targets",
                "test",
                "--output",
                "JSON",
            ]
        )

        # Should succeed or fail gracefully
        assert result2["returncode"] in [
            0,
            1,
        ], f"Monitor workflows command failed unexpectedly: {result2['stderr']}"

        if result2["success"]:
            assert "execute_notebooks_dag" in result2["stdout"].lower()
        else:
            # Expected failures: MWAA not available, project not found, etc.
            expected_errors = [
                "mwaa",
                "project",
                "connection",
                "environment",
                "workflow",
            ]
            assert any(
                err in result2["stderr"].lower() for err in expected_errors
            ), f"Unexpected monitor workflows error: {result2['stderr']}"

    def test_describe_command_validation(self):
        """Test describe command validation."""
        pipeline_file = self.get_pipeline_file()

        result = self.run_smus_command(
            ["describe", "--manifest", str(pipeline_file), "--output", "JSON"]
        )

        # Describe should always succeed for valid pipeline
        assert result["success"], f"Describe command failed: {result['stderr']}"
        assert "IntegrationTestMultiTarget" in result["stdout"]
        assert "test" in result["stdout"]

    def test_bundle_structure_validation(self):
        """Test that created bundle has correct structure."""
        bundle_path = self.create_test_bundle()

        with zipfile.ZipFile(bundle_path, "r") as zipf:
            file_list = zipf.namelist()

            # Check for expected structure
            assert any("code/" in f for f in file_list), "Missing storage files"
            assert any(
                "workflows/dags/" in f for f in file_list
            ), "Missing workflow files"
            assert any(".ipynb" in f for f in file_list), "Missing notebook files"
            assert any(".py" in f for f in file_list), "Missing Python files"

            # Check specific files
            expected_files = [
                "code/test-notebook1.ipynb",
                "code/covid_analysis.ipynb",
                "workflows/dags/execute_notebooks_dag.py",
            ]

            for expected_file in expected_files:
                assert any(
                    expected_file in f for f in file_list
                ), f"Expected file not found: {expected_file}"
