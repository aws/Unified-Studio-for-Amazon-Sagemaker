#!/usr/bin/env python3
"""
Setup script to import test dashboard before running integration tests.

This script:
1. Imports sample-dashboard.qs as "test-covid-dashboard" in dev region
2. This dashboard will be exported during bundle as "test-covid-dashboard"
3. Then imported during deploy as "deployed-test-covid-dashboard"
"""

import os
import sys
import boto3

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from src.smus_cicd.helpers.quicksight import (
    import_dashboard,
    poll_import_job,
    grant_asset_bundle_permissions,
)


def setup_test_dashboard():
    """Import test dashboard to dev environment."""
    
    # Get from environment or use defaults
    account_id = os.environ.get("AWS_ACCOUNT_ID")
    dev_region = os.environ.get("DEV_DOMAIN_REGION", "us-east-2")
    
    if not account_id:
        # Try to get from STS
        sts = boto3.client("sts")
        account_id = sts.get_caller_identity()["Account"]
    
    # Configuration
    dashboard_bundle = os.path.join(os.path.dirname(__file__), "sample-dashboard.qs")
    dashboard_id = "test-covid-dashboard"
    quicksight_user = os.environ.get("QUICKSIGHT_USER", "default-user")
    principal = f"arn:aws:quicksight:{dev_region}:{account_id}:user/default/{quicksight_user}"
    
    print(f"Setting up test dashboard: {dashboard_id}")
    print(f"  Bundle: {dashboard_bundle}")
    print(f"  Region: {dev_region}")
    print(f"  Account: {account_id}")
    
    # Import dashboard
    print("\nImporting dashboard...")
    job_id = import_dashboard(
        dashboard_bundle,
        account_id,
        dev_region,
        override_parameters={}
    )
    
    print(f"Import job started: {job_id}")
    print("Waiting for import to complete...")
    
    result = poll_import_job(job_id, account_id, dev_region)
    
    print(f"✓ Dashboard imported successfully: {dashboard_id}")
    
    # Grant permissions to all imported assets (dashboard, datasets, data sources)
    print("\nGranting permissions to all imported assets...")
    grant_asset_bundle_permissions(result, account_id, dev_region, principal)
    print("✓ Permissions granted to all assets")
    
    print(f"\n✅ Test dashboard setup complete!")
    print(f"\nNext steps:")
    print(f"  1. Run: smus-cli bundle --targets dev")
    print(f"     → Will export '{dashboard_id}' as 'bundled-test-covid-dashboard'")
    print(f"  2. Run: smus-cli deploy --targets test")
    print(f"     → Will import as 'deployed-test-covid-dashboard' in us-east-1")


if __name__ == "__main__":
    setup_test_dashboard()
