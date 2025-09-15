#!/usr/bin/env python3
"""Comprehensive test runner for SMUS CLI with coverage analysis."""

import argparse
import os
import shutil
import subprocess
import sys
import yaml
from pathlib import Path


def load_test_config():
    """Load integration test configuration."""
    config_path = Path("tests/integration/config.local.yaml")
    if not config_path.exists():
        config_path = Path("tests/integration/config.yaml")

    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return {}


def check_aws_setup():
    """Check if AWS credentials are configured."""
    if os.getenv("AWS_PROFILE") or (
        os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    ):
        return True

    # Check config file
    config = load_test_config()
    aws_config = config.get("aws", {})

    if aws_config.get("profile") or (
        aws_config.get("access_key_id") and aws_config.get("secret_access_key")
    ):
        return True

    return False


def clean_reports_directory():
    """Clean the reports directory before running tests."""
    reports_dir = Path("tests/reports")
    if reports_dir.exists():
        shutil.rmtree(reports_dir)
        print("🧹 Cleaned reports directory")
    reports_dir.mkdir(parents=True, exist_ok=True)


def run_unit_tests(coverage=True, html_report=False):
    """Run unit tests with coverage."""
    cmd = ["python", "-m", "pytest", "tests/unit/", "-v"]

    if coverage:
        cmd.extend(["--cov=src/smus_cicd", "--cov-report=term-missing"])
        if html_report:
            cmd.extend(["--cov-report=html:tests/reports/coverage"])

    if html_report:
        cmd.extend(
            ["--html=tests/reports/unit-test-results.html", "--self-contained-html"]
        )

    print("🧪 Running unit tests...")
    return subprocess.run(cmd).returncode


def run_integration_tests(coverage=True, html_report=False, skip_slow=False):
    """Run integration tests with coverage."""
    cmd = ["python", "-m", "pytest", "tests/integration/", "-v"]

    if coverage:
        cmd.extend(["--cov=src/smus_cicd", "--cov-append", "--cov-report=term-missing"])
        if html_report:
            cmd.extend(["--cov-report=html:tests/reports/coverage"])

    if skip_slow:
        cmd.extend(["-m", "not slow"])

    if html_report:
        cmd.extend(
            [
                "--html=tests/reports/integration-test-results.html",
                "--self-contained-html",
            ]
        )

    print("🔗 Running integration tests...")
    if not check_aws_setup():
        print("⚠️  Warning: AWS credentials not configured. Some tests may fail.")

    return subprocess.run(cmd).returncode


def run_all_tests(coverage=True, html_report=False, skip_slow=False):
    """Run all tests with coverage."""
    cmd = ["python", "-m", "pytest", "tests/", "-v"]

    if coverage:
        cmd.extend(["--cov=src/smus_cicd", "--cov-report=term-missing"])
        if html_report:
            cmd.extend(["--cov-report=html:tests/reports/coverage"])

    if skip_slow:
        cmd.extend(["-m", "not slow"])

    if html_report:
        cmd.extend(
            ["--html=tests/reports/all-test-results.html", "--self-contained-html"]
        )

    print("🚀 Running all tests...")
    if not check_aws_setup():
        print(
            "⚠️  Warning: AWS credentials not configured. Some integration tests may fail."
        )

    return subprocess.run(cmd).returncode


def generate_coverage_report():
    """Generate detailed coverage report."""
    print("📊 Generating coverage report...")

    # Ensure reports directory exists
    Path("tests/reports").mkdir(parents=True, exist_ok=True)

    # Generate HTML report
    subprocess.run(["python", "-m", "coverage", "html", "-d", "tests/reports/coverage"])

    # Generate XML report for CI
    subprocess.run(
        ["python", "-m", "coverage", "xml", "-o", "tests/reports/coverage.xml"]
    )

    # Show coverage summary
    result = subprocess.run(
        ["python", "-m", "coverage", "report"], capture_output=True, text=True
    )
    print(result.stdout)

    print("📁 HTML coverage report generated in: tests/reports/coverage/index.html")
    print("📄 XML coverage report generated in: tests/reports/coverage.xml")


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="SMUS CLI Test Runner with Coverage")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "all"],
        default="all",
        help="Type of tests to run",
    )
    parser.add_argument(
        "--no-coverage", action="store_true", help="Skip coverage analysis"
    )
    parser.add_argument(
        "--no-html-report",
        action="store_true",
        help="Skip HTML test results and coverage reports generation",
    )
    parser.add_argument(
        "--skip-slow",
        action="store_true",
        help="Skip slow tests (marked with @pytest.mark.slow)",
    )
    parser.add_argument(
        "--coverage-only",
        action="store_true",
        help="Only generate coverage report from existing data",
    )

    args = parser.parse_args()

    # Ensure reports directory exists
    Path("tests/reports").mkdir(parents=True, exist_ok=True)

    if args.coverage_only:
        generate_coverage_report()
        return 0

    coverage = not args.no_coverage
    html_report = (
        not args.no_html_report
    )  # Default to True unless --no-html-report is specified

    # Clean reports directory before running tests
    if html_report:
        clean_reports_directory()

    # Run tests based on type
    if args.type == "unit":
        exit_code = run_unit_tests(coverage=coverage, html_report=html_report)
    elif args.type == "integration":
        exit_code = run_integration_tests(
            coverage=coverage, html_report=html_report, skip_slow=args.skip_slow
        )
    else:  # all
        exit_code = run_all_tests(
            coverage=coverage, html_report=html_report, skip_slow=args.skip_slow
        )

    # Generate coverage report if requested
    if coverage and html_report:
        generate_coverage_report()

    if exit_code == 0:
        print("✅ All tests passed!")
        if html_report:
            print(f"📁 Test results available in: tests/reports/")
            if args.type == "unit":
                print(f"📊 Unit test results: tests/reports/unit-test-results.html")
            elif args.type == "integration":
                print(
                    f"📊 Integration test results: tests/reports/integration-test-results.html"
                )
            else:
                print(f"📊 All test results: tests/reports/all-test-results.html")
            print(f"📈 Coverage report: tests/reports/coverage/index.html")
    else:
        print("❌ Some tests failed!")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
