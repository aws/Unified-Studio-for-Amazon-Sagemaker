#!/usr/bin/env python3
"""
Fix LF registration: create a dedicated IAM role with S3 access,
deregister the bucket from LF, then re-register with the new role.
Run in domain account (994753223772).
"""
import boto3, json, time
from botocore.exceptions import ClientError

REGION = "us-east-2"
ROLE_NAME = "APF-LakeFormation-TestData"
BUCKET_NAME = "apf-test-data-994753223772"

sts = boto3.client("sts", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)
lf = boto3.client("lakeformation", region_name=REGION)

account_id = sts.get_caller_identity()["Account"]
print(f"Account: {account_id}")

# Step 1: Create IAM role with LF + S3 trust/permissions
print("\nStep 1: Creating IAM role...")
trust_policy = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lakeformation.amazonaws.com"},
        "Action": "sts:AssumeRole"
    }]
})

try:
    iam.create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=trust_policy,
        Description="Lake Formation role for APF test data S3 bucket"
    )
    print(f"  Created role: {ROLE_NAME}")
except ClientError as e:
    if e.response["Error"]["Code"] == "EntityAlreadyExists":
        print(f"  Role {ROLE_NAME} already exists")
    else:
        raise

# Inline policy for S3 access to the test data bucket
s3_policy = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Action": [
            "s3:GetObject",
            "s3:ListBucket",
            "s3:GetBucketLocation",
            "s3:ListBucketMultipartUploads",
            "s3:AbortMultipartUpload",
            "s3:ListMultipartUploadParts"
        ],
        "Resource": [
            f"arn:aws:s3:::{BUCKET_NAME}",
            f"arn:aws:s3:::{BUCKET_NAME}/*"
        ]
    }]
})

iam.put_role_policy(
    RoleName=ROLE_NAME,
    PolicyName="S3TestDataAccess",
    PolicyDocument=s3_policy
)
print(f"  Attached S3 policy for bucket {BUCKET_NAME}")

role_arn = f"arn:aws:iam::{account_id}:role/{ROLE_NAME}"
print(f"  Role ARN: {role_arn}")

# Wait for role to propagate
print("  Waiting 10s for IAM propagation...")
time.sleep(10)

# Step 2: Deregister existing S3 location from LF
print("\nStep 2: Deregistering existing S3 location...")
resource_arn = f"arn:aws:s3:::{BUCKET_NAME}"
try:
    lf.deregister_resource(ResourceArn=resource_arn)
    print(f"  Deregistered: {resource_arn}")
except ClientError as e:
    if "not registered" in str(e).lower() or "EntityNotFound" in str(e):
        print(f"  Not registered, skipping deregister")
    else:
        raise

# Step 3: Re-register with the new role
print("\nStep 3: Registering S3 location with new role...")
try:
    lf.register_resource(ResourceArn=resource_arn, RoleArn=role_arn)
    print(f"  Registered {resource_arn} with role {role_arn}")
except ClientError as e:
    if e.response["Error"]["Code"] == "AlreadyExistsException":
        print(f"  Already registered")
    else:
        raise

print("\nDone!")
