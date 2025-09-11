#!/bin/bash

# Master deployment script for DataZone CI/CD infrastructure
# This script deploys all stacks in the correct order

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-$SCRIPT_DIR/config.yaml}"

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    echo "Please create config.yaml with your account-specific settings"
    exit 1
fi

# Check if yq is installed
if ! command -v yq &> /dev/null; then
    echo "Error: yq is required but not installed"
    echo "Install with: brew install yq (macOS) or apt-get install yq (Ubuntu)"
    exit 1
fi

# Parse account and region configuration
ACCOUNT_ID=$(yq '.account_id' "$CONFIG_FILE")
PRIMARY_REGION=$(yq '.regions.primary.name' "$CONFIG_FILE")
PRIMARY_ENABLED=$(yq '.regions.primary.enabled' "$CONFIG_FILE")
SECONDARY_REGION=$(yq '.regions.secondary.name // ""' "$CONFIG_FILE")
SECONDARY_ENABLED=$(yq '.regions.secondary.enabled // false' "$CONFIG_FILE")
TERTIARY_REGION=$(yq '.regions.tertiary.name // ""' "$CONFIG_FILE")
TERTIARY_ENABLED=$(yq '.regions.tertiary.enabled // false' "$CONFIG_FILE")

echo "=== DataZone CI/CD Infrastructure Deployment ==="
echo "Using config: $CONFIG_FILE"
echo "Account ID: $ACCOUNT_ID"
echo "Primary Region: $PRIMARY_REGION (enabled: $PRIMARY_ENABLED)"
echo "Secondary Region: ${SECONDARY_REGION:-'Not configured'} (enabled: $SECONDARY_ENABLED)"
echo "Tertiary Region: ${TERTIARY_REGION:-'Not configured'} (enabled: $TERTIARY_ENABLED)"
echo

# Deploy in order
echo "1. Deploying GitHub OIDC Integration Stack..."
./deploy-github-integration.sh "$CONFIG_FILE"
echo

echo "2. Deploying VPC Stacks..."
./deploy-vpc.sh "$CONFIG_FILE"
echo

echo "3. Deploying Domain Stack..."
./deploy-domain.sh "$CONFIG_FILE"
echo

echo "4. Deploying Blueprints and Profiles Stack..."
./deploy-blueprints-profiles.sh "$CONFIG_FILE"
echo

echo "5. Deploying Dev Project Stack..."
./deploy-projects.sh "$CONFIG_FILE"
echo

echo "6. Deploying Project Memberships..."
./deploy-memberships.sh "$CONFIG_FILE"
echo

echo "=== Deployment Complete! ==="
echo "DataZone infrastructure and memberships have been successfully deployed."
echo ""
echo "Deployed regions:"
if [ "$PRIMARY_ENABLED" = "true" ]; then
    echo "  ✅ Primary: $PRIMARY_REGION"
fi
if [ "$SECONDARY_ENABLED" = "true" ] && [ -n "$SECONDARY_REGION" ]; then
    echo "  ✅ Secondary: $SECONDARY_REGION"
fi
if [ "$TERTIARY_ENABLED" = "true" ] && [ -n "$TERTIARY_REGION" ]; then
    echo "  ✅ Tertiary: $TERTIARY_REGION"
fi
echo ""
echo "Next steps:"
echo "- Dev project is ready for use with admin user as PROJECT_OWNER"
echo "- Test and Prod projects will be created by the CLI when needed:"
echo "  * Run 'smus-cli initialize test' to create test project"
echo "  * Run 'smus-cli initialize prod' to create prod project"
