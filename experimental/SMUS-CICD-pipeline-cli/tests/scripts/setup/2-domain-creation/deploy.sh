#!/bin/bash

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-$SCRIPT_DIR/config.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

# Parse config using yq (install with: brew install yq)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(yq '.regions.primary.name' "$CONFIG_FILE")
DOMAIN_STACK_NAME=$(yq '.stacks.domain' "$CONFIG_FILE")
DOMAIN_NAME=$(yq '.domain_name // "unified-studio-domain"' "$CONFIG_FILE")
DOMAIN_TAGS=$(yq '.domain_tags // {}' "$CONFIG_FILE" -o json)

# Convert domain_tags JSON to comma-separated key=value pairs
TAGS_PARAM=""
if [ "$DOMAIN_TAGS" != "{}" ] && [ "$DOMAIN_TAGS" != "null" ]; then
    TAGS_PARAM=$(echo "$DOMAIN_TAGS" | jq -r 'to_entries | map("\(.key)=\(.value)") | join(",")')
fi

# Check if stack exists and is in ROLLBACK_COMPLETE state
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$DOMAIN_STACK_NAME" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
    echo "Stack $DOMAIN_STACK_NAME is in ROLLBACK_COMPLETE state. Deleting..."
    aws cloudformation delete-stack --stack-name "$DOMAIN_STACK_NAME" --region "$REGION"
    echo "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$DOMAIN_STACK_NAME" --region "$REGION"
    echo "Stack deleted successfully."
fi

# Deploy DataZone Domain Stack
echo "Deploying DataZone Domain Stack..."
PARAM_OVERRIDES="DomainName=$DOMAIN_NAME"
if [ -n "$TAGS_PARAM" ]; then
    PARAM_OVERRIDES="$PARAM_OVERRIDES DomainTags=$TAGS_PARAM"
fi

if aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/sagemaker-domain.yaml" \
  --stack-name "$DOMAIN_STACK_NAME" \
  --parameter-overrides $PARAM_OVERRIDES \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"; then
  echo "✅ DataZone domain stack deployment complete!"
  
  # Tag the domain if tags are provided
  if [ -n "$TAGS_PARAM" ]; then
    echo "Tagging domain with: $TAGS_PARAM"
    DOMAIN_ID=$(aws cloudformation describe-stacks --stack-name "$DOMAIN_STACK_NAME" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`DomainId`].OutputValue' --output text)
    DOMAIN_ARN="arn:aws:datazone:${REGION}:${ACCOUNT_ID}:domain/${DOMAIN_ID}"
    
    # Convert comma-separated tags to JSON
    TAG_JSON=$(echo "$TAGS_PARAM" | awk -F',' '{for(i=1;i<=NF;i++){split($i,a,"="); printf "\"%s\":\"%s\"%s", a[1], a[2], (i<NF?",":"")}}' | sed 's/^/{/' | sed 's/$/}/')
    
    # Check if endpoint URL is set for non-prod
    ENDPOINT_ARG=""
    DATAZONE_ENDPOINT=$(yq '.service_endpoints.datazone // ""' "$CONFIG_FILE")
    if [ -n "$DATAZONE_ENDPOINT" ]; then
        ENDPOINT_ARG="--endpoint-url $DATAZONE_ENDPOINT"
    fi
    
    aws datazone tag-resource $ENDPOINT_ARG --resource-arn "$DOMAIN_ARN" --tags "$TAG_JSON" --region "$REGION"
    echo "✅ Domain tagged successfully"
  fi
else
  echo "❌ DataZone domain stack deployment failed!"
  exit 1
fi
