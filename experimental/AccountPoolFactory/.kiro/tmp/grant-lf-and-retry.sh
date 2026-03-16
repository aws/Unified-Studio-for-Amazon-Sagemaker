#!/bin/bash
# Step 1: Grant cross-account LF permissions from domain account
eval $(isengardcli credentials amirbo+3@amazon.com)
ACCOUNT_ID="108750422936"
REGION="us-east-2"

echo "Granting cross-account LF permissions to $ACCOUNT_ID..."
python3 -c "
import boto3
lf = boto3.client('lakeformation', region_name='us-east-2')
acct = '$ACCOUNT_ID'
for db in ['apf_test_customers', 'apf_test_transactions']:
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': acct},
            Resource={'Database': {'Name': db}},
            Permissions=['DESCRIBE'],
            PermissionsWithGrantOption=['DESCRIBE']
        )
        print(f'  Granted DESCRIBE on {db} to {acct}')
    except Exception as e:
        print(f'  DB {db}: {e}')
    try:
        lf.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': acct},
            Resource={'Table': {'DatabaseName': db, 'TableWildcard': {}}},
            Permissions=['SELECT', 'DESCRIBE'],
            PermissionsWithGrantOption=['SELECT', 'DESCRIBE']
        )
        print(f'  Granted SELECT+DESCRIBE on tables in {db} to {acct}')
    except Exception as e:
        print(f'  Tables {db}: {e}')
print('Done granting LF permissions')
"

# Step 2: Delete failed instance and retry from org admin
eval $(isengardcli credentials amirbo+1@amazon.com)
STACKSET="SMUS-AccountPoolFactory-GlueLfTestData"

echo ""
echo "Deleting failed instance..."
OP_ID=$(aws cloudformation delete-stack-instances \
    --stack-set-name "$STACKSET" \
    --accounts "$ACCOUNT_ID" \
    --regions "$REGION" \
    --no-retain-stacks \
    --region "$REGION" \
    --query 'OperationId' --output text 2>&1)
echo "Delete OP: $OP_ID"

for i in $(seq 1 10); do
    sleep 15
    STATUS=$(aws cloudformation describe-stack-set-operation \
        --stack-set-name "$STACKSET" --operation-id "$OP_ID" \
        --region "$REGION" --query 'StackSetOperation.Status' --output text 2>&1)
    echo "[$((i*15))s] Delete: $STATUS"
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ]; then break; fi
done

echo ""
echo "Updating StackSet template..."
ADMIN_ROLE="arn:aws:iam::495869084367:role/SMUS-AccountPoolFactory-StackSetAdmin"
EXEC_ROLE="SMUS-AccountPoolFactory-StackSetExecution"
BUCKET="accountpoolfactory-templates-495869084367"
TEMPLATE_URL="https://${BUCKET}.s3.${REGION}.amazonaws.com/stacksets/common/07-glue-lf-test-data.yaml"

OP_ID=$(aws cloudformation update-stack-set \
    --stack-set-name "$STACKSET" \
    --template-url "$TEMPLATE_URL" \
    --administration-role-arn "$ADMIN_ROLE" \
    --execution-role-name "$EXEC_ROLE" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters ParameterKey=DomainAccountId,ParameterValue=994753223772 ParameterKey=DomainId,ParameterValue=dzd-4h7jbz76qckoh5 \
    --region "$REGION" \
    --query 'OperationId' --output text 2>&1)
echo "Update OP: $OP_ID"

for i in $(seq 1 10); do
    sleep 10
    STATUS=$(aws cloudformation describe-stack-set-operation \
        --stack-set-name "$STACKSET" --operation-id "$OP_ID" \
        --region "$REGION" --query 'StackSetOperation.Status' --output text 2>&1)
    echo "[$((i*10))s] Update: $STATUS"
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ]; then break; fi
done

echo ""
echo "Creating fresh instance for $ACCOUNT_ID..."
OP_ID=$(aws cloudformation create-stack-instances \
    --stack-set-name "$STACKSET" \
    --accounts "$ACCOUNT_ID" \
    --regions "$REGION" \
    --operation-preferences MaxConcurrentCount=1 \
    --region "$REGION" \
    --query 'OperationId' --output text 2>&1)
echo "Create OP: $OP_ID"

for i in $(seq 1 20); do
    sleep 15
    STATUS=$(aws cloudformation describe-stack-set-operation \
        --stack-set-name "$STACKSET" --operation-id "$OP_ID" \
        --region "$REGION" --query 'StackSetOperation.Status' --output text 2>&1)
    echo "[$((i*15))s] Instance: $STATUS"
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ]; then break; fi
done
echo "Done: $STATUS"
