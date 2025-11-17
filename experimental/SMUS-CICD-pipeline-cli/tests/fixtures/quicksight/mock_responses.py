"""Mock QuickSight API responses for testing."""


def get_start_dashboard_export_success():
    """Mock successful start_dashboard_snapshot_job response."""
    return {
        "Arn": "arn:aws:quicksight:us-east-1:123456789012:dashboard/test-dashboard",
        "SnapshotJobId": "test-job-id",
        "Status": 202,
    }


def get_describe_export_job_completed():
    """Mock completed describe_dashboard_snapshot_job response."""
    return {
        "SnapshotJobId": "test-job-id",
        "Status": "COMPLETED",
        "SnapshotConfiguration": {
            "FileGroups": [
                {
                    "Files": [
                        {
                            "S3Uri": "s3://bucket/export.zip",
                        }
                    ]
                }
            ]
        },
    }


def get_describe_export_job_running():
    """Mock running describe_dashboard_snapshot_job response."""
    return {
        "SnapshotJobId": "test-job-id",
        "Status": "RUNNING",
    }


def get_start_dashboard_import_success():
    """Mock successful start_dashboard_snapshot_job_creation response."""
    return {
        "Arn": "arn:aws:quicksight:us-east-1:123456789012:dashboard/test-dashboard",
        "SnapshotJobId": "test-import-job-id",
        "Status": 202,
    }


def get_describe_import_job_completed():
    """Mock completed describe_dashboard_snapshot_job_creation response."""
    return {
        "SnapshotJobId": "test-import-job-id",
        "Status": "COMPLETED",
    }


def get_update_dashboard_permissions_success():
    """Mock successful update_dashboard_permissions response."""
    return {
        "DashboardArn": "arn:aws:quicksight:us-east-1:123456789012:dashboard/test-dashboard",
        "Status": 200,
    }
