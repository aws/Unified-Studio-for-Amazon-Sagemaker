#!/bin/bash

# Master deployment script for DataZone CI/CD infrastructure
# This script deploys all stacks in the correct order

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

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

echo "=== DataZone CI/CD Infrastructure Deployment ==="
echo "Using config: $CONFIG_FILE"
echo

# Deploy in order
echo "1. Deploying Domain Stack..."
./deploy-domain.sh
echo

echo "2. Deploying Blueprints and Profiles Stack..."
./deploy-blueprints-profiles.sh
echo

echo "3. Deploying Dev Project Stack..."
./deploy-projects.sh
echo

echo "4. Deploying Project Memberships..."
./deploy-memberships.sh
echo

echo "=== Deployment Complete! ==="
echo "DataZone infrastructure and memberships have been successfully deployed."
echo ""
echo "Next steps:"
echo "- Dev project is ready for use with admin user as PROJECT_OWNER"
echo "- Test and Prod projects will be created by the CLI when needed:"
echo "  * Run 'smus-cli initialize test' to create test project"
echo "  * Run 'smus-cli initialize prod' to create prod project"
