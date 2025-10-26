#!/bin/bash

# Master deployment script for SMUS integration testing infrastructure
# Runs all setup stages in order

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-$SCRIPT_DIR/../config.yaml}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.yaml not found at $CONFIG_FILE"
    exit 1
fi

if ! command -v yq &> /dev/null; then
    echo "Error: yq is required but not installed"
    echo "Install with: brew install yq (macOS) or apt-get install yq (Ubuntu)"
    exit 1
fi

ACCOUNT_ID=$(yq '.account_id' "$CONFIG_FILE")
PRIMARY_REGION=$(yq '.regions.primary.name' "$CONFIG_FILE")

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  SMUS Integration Testing Infrastructure Deployment           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo
echo "Account: $ACCOUNT_ID"
echo "Primary Region: $PRIMARY_REGION"
echo "Config: $CONFIG_FILE"
echo
echo "This will deploy all 5 stages:"
echo "  1. Account Minimal Setup (OIDC, VPC)"
echo "  2. Domain Creation"
echo "  3. Domain Configuration (Blueprints, Profiles)"
echo "  4. Project Setup (Dev project, Memberships)"
echo "  5. Testing Infrastructure (MLflow, etc.)"
echo
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

echo
echo "════════════════════════════════════════════════════════════════"
echo "STAGE 1: Account Minimal Setup"
echo "════════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/1-account-setup/deploy.sh" "$CONFIG_FILE"

echo
echo "════════════════════════════════════════════════════════════════"
echo "STAGE 2: Domain Creation"
echo "════════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/2-domain-creation/deploy.sh" "$CONFIG_FILE"

echo
echo "════════════════════════════════════════════════════════════════"
echo "STAGE 3: Domain Configuration"
echo "════════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/3-domain-configuration/deploy.sh" "$CONFIG_FILE"

echo
echo "════════════════════════════════════════════════════════════════"
echo "STAGE 4: Project Setup"
echo "════════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/4-project-setup/deploy.sh" "$CONFIG_FILE"

echo
echo "════════════════════════════════════════════════════════════════"
echo "STAGE 5: Testing Infrastructure"
echo "════════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/5-testing-infrastructure/deploy.sh" "$CONFIG_FILE"

echo
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✅ ALL STAGES COMPLETE!                                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo
echo "Your SMUS integration testing environment is ready!"
echo
echo "Next steps:"
echo "  - Update test configurations with MLflow ARNs from /tmp/"
echo "  - Run integration tests"
echo "  - Configure GitHub workflows with OIDC role"
