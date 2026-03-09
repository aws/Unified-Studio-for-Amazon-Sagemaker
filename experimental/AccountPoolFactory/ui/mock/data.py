"""
Mock data for the Account Pool Factory UI.
Realistic sample data matching the actual DynamoDB schema and API shapes.
"""

import time
from datetime import datetime, timezone, timedelta

def ts(days_ago=0, hours_ago=0):
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)
    return dt.isoformat()

PROFILES = [
    {"id": "prof-analytics-001", "name": "All Capabilities - Account Pool",
     "description": "Full analytics stack with DataLake, Redshift, and ML tools", "hasPool": True,
     "allowedRegions": [
         {"value": "us-east-1", "label": "US East (N. Virginia) — us-east-1"},
         {"value": "us-east-2", "label": "US East (Ohio) — us-east-2"},
         {"value": "us-west-2", "label": "US West (Oregon) — us-west-2"},
     ]},
    {"id": "prof-ml-001", "name": "ML Capabilities - Account Pool",
     "description": "ML-focused profile with SageMaker and MLflow", "hasPool": True,
     "allowedRegions": [
         {"value": "us-east-2", "label": "US East (Ohio) — us-east-2"},
         {"value": "eu-central-1", "label": "Europe (Frankfurt) — eu-central-1"},
     ]},
    {"id": "prof-basic-001", "name": "Basic Analytics",
     "description": "Basic profile without account pool", "hasPool": False,
     "allowedRegions": []},
]

IDC_USERS = [
    {"id": "user-001", "name": "Alice Johnson", "email": "alice@example.com", "type": "USER"},
    {"id": "user-002", "name": "Bob Smith", "email": "bob@example.com", "type": "USER"},
    {"id": "user-003", "name": "Carol White", "email": "carol@example.com", "type": "USER"},
    {"id": "user-004", "name": "David Lee", "email": "david@example.com", "type": "USER"},
    {"id": "group-001", "name": "Analytics Team", "email": None, "type": "GROUP"},
    {"id": "group-002", "name": "ML Platform Team", "email": None, "type": "GROUP"},
    {"id": "group-003", "name": "Data Engineering", "email": None, "type": "GROUP"},
]

ACCOUNTS = [
    {"accountId": "111122223333", "poolName": "analytics", "state": "AVAILABLE",
     "accountName": "smus-analytics-a3f8b2c1", "accountEmail": "analytics-pool+a3f8b2c1@example.com",
     "createdDate": ts(days_ago=5), "setupCompleteDate": ts(days_ago=5, hours_ago=1),
     "deployedStackSets": ["SMUS-AccountPoolFactory-DomainAccess", "SMUS-AccountPoolFactory-VPC",
                           "SMUS-AccountPoolFactory-IAMRoles", "SMUS-AccountPoolFactory-Blueprints"],
     "retryCount": 0, "errorMessage": "", "reconciliationNote": ""},
    {"accountId": "222233334444", "poolName": "analytics", "state": "AVAILABLE",
     "accountName": "smus-analytics-b4e9c3d2", "accountEmail": "analytics-pool+b4e9c3d2@example.com",
     "createdDate": ts(days_ago=4), "setupCompleteDate": ts(days_ago=4, hours_ago=1),
     "deployedStackSets": ["SMUS-AccountPoolFactory-DomainAccess", "SMUS-AccountPoolFactory-VPC",
                           "SMUS-AccountPoolFactory-IAMRoles", "SMUS-AccountPoolFactory-Blueprints"],
     "retryCount": 0, "errorMessage": "", "reconciliationNote": ""},
    {"accountId": "333344445555", "poolName": "analytics", "state": "ASSIGNED",
     "accountName": "smus-analytics-c5f0d4e3", "accountEmail": "analytics-pool+c5f0d4e3@example.com",
     "createdDate": ts(days_ago=10), "setupCompleteDate": ts(days_ago=10, hours_ago=1),
     "assignedDate": ts(hours_ago=2), "projectId": "proj-abc123",
     "deployedStackSets": ["SMUS-AccountPoolFactory-DomainAccess", "SMUS-AccountPoolFactory-VPC",
                           "SMUS-AccountPoolFactory-IAMRoles", "SMUS-AccountPoolFactory-Blueprints"],
     "retryCount": 0, "errorMessage": "", "reconciliationNote": ""},
    {"accountId": "444455556666", "poolName": "analytics", "state": "SETTING_UP",
     "accountName": "smus-analytics-d6g1e5f4", "accountEmail": "analytics-pool+d6g1e5f4@example.com",
     "createdDate": ts(hours_ago=1),
     "deployedStackSets": [],
     "retryCount": 0, "errorMessage": "", "reconciliationNote": ""},
    {"accountId": "555566667777", "poolName": "analytics", "state": "FAILED",
     "accountName": "smus-analytics-e7h2f6g5", "accountEmail": "analytics-pool+e7h2f6g5@example.com",
     "createdDate": ts(days_ago=2), "setupCompleteDate": None,
     "deployedStackSets": ["SMUS-AccountPoolFactory-DomainAccess"],
     "retryCount": 3, "errorMessage": "StackSet deployment timed out after 300s",
     "reconciliationNote": "NEEDS_SETUP: Missing DataZone-VPC, DataZone-IAM"},
    {"accountId": "666677778888", "poolName": "ml-training", "state": "AVAILABLE",
     "accountName": "smus-ml-f8i3g7h6", "accountEmail": "ml-pool+f8i3g7h6@example.com",
     "createdDate": ts(days_ago=3), "setupCompleteDate": ts(days_ago=3, hours_ago=1),
     "deployedStackSets": ["SMUS-AccountPoolFactory-DomainAccess",
                           "SMUS-AccountPoolFactory-IAMRoles", "SMUS-AccountPoolFactory-Blueprints"],
     "retryCount": 0, "errorMessage": "", "reconciliationNote": ""},
    {"accountId": "777788889999", "poolName": "ml-training", "state": "AVAILABLE",
     "accountName": "smus-ml-g9j4h8i7", "accountEmail": "ml-pool+g9j4h8i7@example.com",
     "createdDate": ts(days_ago=3), "setupCompleteDate": ts(days_ago=3, hours_ago=2),
     "deployedStackSets": ["SMUS-AccountPoolFactory-DomainAccess",
                           "SMUS-AccountPoolFactory-IAMRoles", "SMUS-AccountPoolFactory-Blueprints"],
     "retryCount": 0, "errorMessage": "", "reconciliationNote": ""},
    {"accountId": "888899990000", "poolName": "ml-training", "state": "CLEANING",
     "accountName": "smus-ml-h0k5i9j8", "accountEmail": "ml-pool+h0k5i9j8@example.com",
     "createdDate": ts(days_ago=15), "setupCompleteDate": ts(days_ago=15, hours_ago=1),
     "assignedDate": ts(days_ago=5), "projectId": "proj-def456",
     "deployedStackSets": ["SMUS-AccountPoolFactory-DomainAccess",
                           "SMUS-AccountPoolFactory-IAMRoles", "SMUS-AccountPoolFactory-Blueprints"],
     "retryCount": 0, "errorMessage": "", "reconciliationNote": ""},
]

PORTAL_URL = "https://dzd-4h7jbz76qckoh5.datazone.us-east-2.on.aws"

# Simulated project creation state (in-memory for mock)
_projects = {}

def create_project(name, region, owner_id, profile_id):
    import uuid
    project_id = "proj-" + uuid.uuid4().hex[:8]
    _projects[project_id] = {
        "id": project_id,
        "name": name,
        "region": region,
        "ownerId": owner_id,
        "profileId": profile_id,
        "resolvedAccountId": "111122223333",
        "projectStatus": "ACTIVE",
        "overallDeploymentStatus": "IN_PROGRESS",
        "environments": [
            {"name": "Tooling", "status": "DEPLOYING"},
            {"name": "Lakehouse Database", "status": "PENDING"},
        ],
        "createdAt": ts(),
        "_tick": 0,
    }
    return project_id

def get_project_status(project_id):
    p = _projects.get(project_id)
    if not p:
        return None
    p["_tick"] += 1
    tick = p["_tick"]
    # Simulate progression
    if tick < 3:
        p["overallDeploymentStatus"] = "IN_PROGRESS"
        p["environments"][0]["status"] = "DEPLOYING"
        p["environments"][1]["status"] = "PENDING"
    elif tick < 6:
        p["overallDeploymentStatus"] = "IN_PROGRESS"
        p["environments"][0]["status"] = "ACTIVE"
        p["environments"][1]["status"] = "DEPLOYING"
    else:
        p["overallDeploymentStatus"] = "COMPLETED"
        p["environments"][0]["status"] = "ACTIVE"
        p["environments"][1]["status"] = "ACTIVE"
    return p
