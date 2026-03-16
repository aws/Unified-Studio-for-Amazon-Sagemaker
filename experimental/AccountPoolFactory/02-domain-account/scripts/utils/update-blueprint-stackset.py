#!/usr/bin/env python3
"""Update the BlueprintEnablement StackSet with the correct IAM template."""
import boto3, os

REGION = 'us-east-2'
STACKSET_NAME = 'SMUS-AccountPoolFactory-BlueprintEnablement'

# Read the correct IAM template
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(script_dir, '..', '..')
template_path = os.path.join(project_root, 'templates', 'cloudformation',
                             '03-project-account', 'deploy', 'blueprint-enablement-iam.yaml')

with open(template_path) as f:
    template_body = f.read()

cf = boto3.client('cloudformation', region_name=REGION)

# Update the StackSet
print(f"Updating StackSet {STACKSET_NAME} with IAM template...")
resp = cf.update_stack_set(
    StackSetName=STACKSET_NAME,
    TemplateBody=template_body,
    AdministrationRoleARN='arn:aws:iam::495869084367:role/SMUS-AccountPoolFactory-StackSetAdmin',
    ExecutionRoleName='SMUS-AccountPoolFactory-StackSetExecution',
    Parameters=[
        {'ParameterKey': 'DomainId', 'ParameterValue': 'dzd-4h7jbz76qckoh5'},
        {'ParameterKey': 'ManageAccessRoleArn', 'ParameterValue': 'placeholder'},
        {'ParameterKey': 'ProvisioningRoleArn', 'ParameterValue': 'placeholder'},
        {'ParameterKey': 'VpcId', 'ParameterValue': 'placeholder'},
        {'ParameterKey': 'SubnetIds', 'ParameterValue': 'placeholder'},
        {'ParameterKey': 'S3BucketName', 'ParameterValue': 'placeholder'},
        {'ParameterKey': 'DomainUnitId', 'ParameterValue': 'bsmdc8e4dwye5l'},
    ],
    Capabilities=['CAPABILITY_NAMED_IAM'],
    OperationPreferences={
        'FailureToleranceCount': 0,
        'MaxConcurrentCount': 1,
    }
)
op_id = resp['OperationId']
print(f"Update operation: {op_id}")

# Wait for completion
import time
while True:
    status = cf.describe_stack_set_operation(
        StackSetName=STACKSET_NAME, OperationId=op_id
    )['StackSetOperation']['Status']
    print(f"  Status: {status}")
    if status in ('SUCCEEDED', 'FAILED', 'CANCELLED', 'STOPPED'):
        break
    time.sleep(10)

# Verify
resp = cf.describe_stack_set(StackSetName=STACKSET_NAME)
params = [p['ParameterKey'] for p in resp['StackSet'].get('Parameters', [])]
print(f"\nStackSet parameters after update: {params}")
