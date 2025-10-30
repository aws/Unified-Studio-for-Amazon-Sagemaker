# Step 6: Fix Project IAM Roles

This script fixes IAM role trust policies for all DataZone projects in a domain.

## What It Does

Updates IAM role trust policies to include required service principals:
- `airflow-serverless.amazonaws.com` - For Airflow Serverless workflows
- `airflow-serverless-gamma.amazonaws.com` - For Airflow Serverless gamma stage
- `athena.aws.internal` - For Athena queries
- `athena.amazonaws.com` - For Athena queries

## Prerequisites

- AWS credentials configured
- Permissions to:
  - List DataZone projects
  - Get DataZone project details
  - Update IAM role trust policies

## Usage

```bash
# Dry run (see what would be changed)
python fix_project_roles.py --domain-id dzd-xxxxx --region us-east-1 --dry-run

# Apply changes
python fix_project_roles.py --domain-id dzd-xxxxx --region us-east-1
```

## Parameters

- `--domain-id` (required): DataZone domain ID
- `--region` (default: us-east-1): AWS region
- `--dry-run`: Show what would be done without making changes

## Example Output

```
🔧 Fixing project roles in domain dzd-5b6m4h6c1yfch3
   Region: us-east-1

✅ Found 3 projects in domain dzd-5b6m4h6c1yfch3

📋 Project: dev-marketing (abc123)
  Role: arn:aws:iam::123456789012:role/DataZoneProjectRole-abc123
  ✅ Updated trust policy for DataZoneProjectRole-abc123

📋 Project: test-marketing (def456)
  Role: arn:aws:iam::123456789012:role/DataZoneProjectRole-def456
  ✓ Role DataZoneProjectRole-def456 already has all required principals

============================================================
Summary:
  Total projects: 3
  ✅ Successfully updated: 2
  ⚠️  Skipped: 1
  ❌ Failed: 0
============================================================
```

## When to Run

Run this script:
1. After creating a new DataZone domain
2. After creating new projects
3. When adding Airflow Serverless or Athena support
4. Once per account during initial setup

## Notes

- Safe to run multiple times (idempotent)
- Only updates roles that need changes
- Preserves existing trust policy statements
- Adds new service principals to existing statements
