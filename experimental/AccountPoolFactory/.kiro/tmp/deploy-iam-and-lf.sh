#!/bin/bash
# Deploy updated IAM policy and add Lambda role as LF admin
set -e
eval $(isengardcli credentials amirbo+3@amazon.com)
REGION="us-east-2"
ROOT="experimental/AccountPoolFactory"

echo "Step 1: Deploy CF stack to update IAM policy..."
aws cloudformation deploy \
    --template-file "$ROOT/templates/cloudformation/02-domain-account/deploy/01-infrastructure.yaml" \
    --stack-name AccountPoolFactory-DomainInfra \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
        DomainId=dzd-4h7jbz76qckoh5 \
        OrgAdminAccountId=495869084367 \
    --region "$REGION" \
    --no-fail-on-empty-changeset

echo ""
echo "Step 2: Add Lambda execution role as LF admin in domain account..."
python3 -c "
import boto3
lf = boto3.client('lakeformation', region_name='us-east-2')
settings = lf.get_data_lake_settings()
admins = settings['DataLakeSettings'].get('DataLakeAdmins', [])
role = 'arn:aws:iam::994753223772:role/SMUS-AccountPoolFactory-LambdaExecution-Role'
arns = [a['DataLakePrincipalIdentifier'] for a in admins]
if role not in arns:
    admins.append({'DataLakePrincipalIdentifier': role})
    settings['DataLakeSettings']['DataLakeAdmins'] = admins
    lf.put_data_lake_settings(DataLakeSettings=settings['DataLakeSettings'])
    print(f'Added {role} as LF admin')
else:
    print('Already an LF admin')
"
echo "Done"
