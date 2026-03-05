#!/bin/bash

# Deploy All Approved StackSets in Parallel
# This script deploys VPC, IAM Roles, and Blueprint Enablement StackSets concurrently

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploy All StackSets in Parallel${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if individual scripts exist
if [ ! -f "$SCRIPT_DIR/deploy-vpc-stackset.sh" ]; then
    echo -e "${RED}Error: deploy-vpc-stackset.sh not found${NC}"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/deploy-iam-roles-stackset.sh" ]; then
    echo -e "${RED}Error: deploy-iam-roles-stackset.sh not found${NC}"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/deploy-blueprint-stackset.sh" ]; then
    echo -e "${RED}Error: deploy-blueprint-stackset.sh not found${NC}"
    exit 1
fi

echo -e "${BLUE}Starting parallel deployment of 3 StackSets...${NC}"
echo ""

# Create temporary directory for logs
LOG_DIR=$(mktemp -d)
echo "Logs will be saved to: $LOG_DIR"
echo ""

# Deploy VPC StackSet in background
echo -e "${YELLOW}[1/3] Starting VPC StackSet deployment...${NC}"
"$SCRIPT_DIR/deploy-vpc-stackset.sh" > "$LOG_DIR/vpc.log" 2>&1 &
VPC_PID=$!

# Deploy IAM Roles StackSet in background
echo -e "${YELLOW}[2/3] Starting IAM Roles StackSet deployment...${NC}"
"$SCRIPT_DIR/deploy-iam-roles-stackset.sh" > "$LOG_DIR/iam-roles.log" 2>&1 &
IAM_PID=$!

# Deploy Blueprint Enablement StackSet in background
echo -e "${YELLOW}[3/3] Starting Blueprint Enablement StackSet deployment...${NC}"
"$SCRIPT_DIR/deploy-blueprint-stackset.sh" > "$LOG_DIR/blueprint.log" 2>&1 &
BLUEPRINT_PID=$!

echo ""
echo -e "${BLUE}All deployments started. Waiting for completion...${NC}"
echo ""

# Wait for all background jobs and track results
VPC_STATUS=0
IAM_STATUS=0
BLUEPRINT_STATUS=0

wait $VPC_PID || VPC_STATUS=$?
wait $IAM_PID || IAM_STATUS=$?
wait $BLUEPRINT_PID || BLUEPRINT_STATUS=$?

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Results${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check VPC deployment
if [ $VPC_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ VPC StackSet: SUCCESS${NC}"
else
    echo -e "${RED}✗ VPC StackSet: FAILED (exit code: $VPC_STATUS)${NC}"
    echo "  Log: $LOG_DIR/vpc.log"
fi

# Check IAM Roles deployment
if [ $IAM_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ IAM Roles StackSet: SUCCESS${NC}"
else
    echo -e "${RED}✗ IAM Roles StackSet: FAILED (exit code: $IAM_STATUS)${NC}"
    echo "  Log: $LOG_DIR/iam-roles.log"
fi

# Check Blueprint deployment
if [ $BLUEPRINT_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ Blueprint Enablement StackSet: SUCCESS${NC}"
else
    echo -e "${RED}✗ Blueprint Enablement StackSet: FAILED (exit code: $BLUEPRINT_STATUS)${NC}"
    echo "  Log: $LOG_DIR/blueprint.log"
fi

echo ""

# Overall status
if [ $VPC_STATUS -eq 0 ] && [ $IAM_STATUS -eq 0 ] && [ $BLUEPRINT_STATUS -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}All StackSets Deployed Successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Deploy StackSet instances to target accounts"
    echo "2. Verify resources created in each account"
    echo ""
    exit 0
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}Some Deployments Failed${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "Check logs in: $LOG_DIR"
    echo ""
    exit 1
fi
