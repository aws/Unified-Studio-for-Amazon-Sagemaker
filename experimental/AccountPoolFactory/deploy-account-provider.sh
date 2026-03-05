#!/bin/bash
set -e

# Deploy Account Provider Lambda
# This Lambda handles DataZone account pool requests

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load configuration
REGION=$(grep "region:" config.yaml | awk '{print $2}')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')

echo "🚀 Deploying Account Provider Lambda"
echo "====================================="
echo "Region: $REGION"
echo "Domain Account: $DOMAIN_ACCOUNT_ID"
echo ""

# Get SNS Topic ARN from infrastructure stack
SNS_TOPIC_ARN=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-Infrastructure \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`SNSTopicArn`].OutputValue' \
    --output text)

echo "SNS Topic ARN: $SNS_TOPIC_ARN"
echo ""

# Create deployment package
echo "📦 Creating deployment package..."
cd src/account-provider
cp lambda_function_prod.py lambda_function.py
zip -r ../../account-provider.zip lambda_function.py
rm lambda_function.py
cd ../..

echo "✅ Package created"
echo ""

# Check if Lambda function exists
if aws lambda get-function --function-name AccountProvider --region "$REGION" 2>/dev/null; then
    echo "🔄 Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name AccountProvider \
        --zip-file fileb://account-provider.zip \
        --region "$REGION" \
        > /dev/null
    
    # Update environment variables
    aws lambda update-function-configuration \
        --function-name AccountProvider \
        --environment "Variables={TABLE_NAME=AccountPoolFactory-AccountState,SNS_TOPIC_ARN=$SNS_TOPIC_ARN}" \
        --region "$REGION" \
        > /dev/null
    
    echo "✅ Lambda function updated"
else
    echo "📦 Creating new Lambda function..."
    
    # Create IAM role for Lambda
    ROLE_NAME="AccountProviderLambdaRole"
    
    # Check if role exists
    if ! aws iam get-role --role-name "$ROLE_NAME" 2>/dev/null; then
        echo "Creating IAM role..."
        
        # Create trust policy
        cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
        
        aws iam create-role \
            --role-name "$ROLE_NAME" \
            --assume-role-policy-document file:///tmp/trust-policy.json \
            > /dev/null
        
        # Attach basic execution policy
        aws iam attach-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        
        # Create and attach DynamoDB policy
        cat > /tmp/dynamodb-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Query",
        "dynamodb:GetItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:$REGION:$DOMAIN_ACCOUNT_ID:table/AccountPoolFactory-AccountState",
        "arn:aws:dynamodb:$REGION:$DOMAIN_ACCOUNT_ID:table/AccountPoolFactory-AccountState/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "$SNS_TOPIC_ARN"
    }
  ]
}
EOF
        
        aws iam put-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-name "AccountProviderPolicy" \
            --policy-document file:///tmp/dynamodb-policy.json
        
        echo "✅ IAM role created"
        echo "⏳ Waiting 10 seconds for role to propagate..."
        sleep 10
    fi
    
    ROLE_ARN="arn:aws:iam::$DOMAIN_ACCOUNT_ID:role/$ROLE_NAME"
    
    # Create Lambda function
    aws lambda create-function \
        --function-name AccountProvider \
        --runtime python3.12 \
        --role "$ROLE_ARN" \
        --handler lambda_function.lambda_handler \
        --zip-file fileb://account-provider.zip \
        --timeout 60 \
        --memory-size 256 \
        --environment "Variables={TABLE_NAME=AccountPoolFactory-AccountState,SNS_TOPIC_ARN=$SNS_TOPIC_ARN}" \
        --region "$REGION" \
        > /dev/null
    
    echo "✅ Lambda function created"
fi

# Clean up
rm -f account-provider.zip
rm -f /tmp/trust-policy.json /tmp/dynamodb-policy.json

# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function \
    --function-name AccountProvider \
    --region "$REGION" \
    --query 'Configuration.FunctionArn' \
    --output text)

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Lambda ARN: $LAMBDA_ARN"
echo ""
echo "Next steps:"
echo "1. Create Account Pool in DataZone"
echo "2. Register this Lambda ARN with the account pool"
echo ""
