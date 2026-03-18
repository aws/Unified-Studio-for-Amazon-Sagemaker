#!/usr/bin/env python3
"""One-time: add domain Admin role as project contributor for connection access."""
import boto3, json

REGION = "us-east-2"
DOMAIN_ID = "dzd-4h7jbz76qckoh5"
PROJECT_ID = "5237hturzpp5ih"

dz = boto3.client('datazone', region_name=REGION)
sts = boto3.client('sts', region_name=REGION)

caller = sts.get_caller_identity()
parts = caller['Arn'].split(':')
role_name = parts[5].split('/')[1]
iam_arn = f"arn:aws:iam::{parts[4]}:role/{role_name}"
print(f"Adding {iam_arn} as PROJECT_CONTRIBUTOR to {PROJECT_ID}...")

try:
    dz.create_project_membership(
        domainIdentifier=DOMAIN_ID,
        projectIdentifier=PROJECT_ID,
        designation='PROJECT_CONTRIBUTOR',
        member={'userIdentifier': iam_arn})
    print("Done")
except Exception as e:
    print(f"Error: {e}")
