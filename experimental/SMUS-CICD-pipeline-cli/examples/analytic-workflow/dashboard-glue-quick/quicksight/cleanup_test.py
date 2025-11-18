#!/usr/bin/env python3
"""
Cleanup script to remove test artifacts from previous runs.
Run this BEFORE starting a new test to ensure clean state.
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError


def cleanup_dashboard(dashboard_id, account_id, region):
    """Delete a dashboard if it exists."""
    client = boto3.client("quicksight", region_name=region)
    
    try:
        # Check if dashboard exists
        client.describe_dashboard(
            AwsAccountId=account_id,
            DashboardId=dashboard_id
        )
        
        # Dashboard exists, delete it
        print(f"  Deleting dashboard: {dashboard_id}")
        client.delete_dashboard(
            AwsAccountId=account_id,
            DashboardId=dashboard_id
        )
        print(f"    ✓ Deleted")
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"  Dashboard {dashboard_id} not found (already clean)")
            return False
        else:
            print(f"  Error checking dashboard: {e}")
            return False


def main():
    """Clean up test artifacts from previous run."""
    # Get from environment or use defaults
    account_id = os.environ.get("AWS_ACCOUNT_ID")
    region = os.environ.get("DEV_DOMAIN_REGION", "us-east-2")
    
    if not account_id:
        # Try to get from STS
        sts = boto3.client("sts")
        account_id = sts.get_caller_identity()["Account"]
    
    print("Cleaning up test artifacts from previous run...")
    print(f"Region: {region}")
    print(f"Account: {account_id}\n")
    
    # Clean up deployed dashboard (from previous deploy)
    print("1. Checking deployed dashboard...")
    cleanup_dashboard("deployed-test-covid-dashboard", account_id, region)
    
    # Note: We keep test-covid-dashboard as it's the source for export
    print("\n2. Keeping source dashboard: test-covid-dashboard")
    print("   (This is the source for bundle export)\n")
    
    print("✅ Cleanup complete! Ready for new test run.")
    print("\nNext steps:")
    print("  1. Run: smus-cli bundle --targets dev")
    print("  2. Run: smus-cli deploy --targets test")


if __name__ == "__main__":
    main()
