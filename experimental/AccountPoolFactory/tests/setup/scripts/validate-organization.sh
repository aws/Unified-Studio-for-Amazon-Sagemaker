#!/bin/bash
#
# Validate AWS Organization Structure
# This script verifies the organization structure was created correctly
#
# Prerequisites:
#   1. config.yaml exists with your configuration
#   2. Organization structure already deployed
#
# Usage: ./validate-organization.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_SETUP_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$(dirname "$TESTS_SETUP_DIR")")"
OU_IDS_FILE="${PROJECT_ROOT}/ou-ids.json"
CONFIG_FILE="${PROJECT_ROOT}/config.yaml"

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Read configuration
read_config() {
    local key="$1"
    if command -v yq &> /dev/null; then
        yq eval "$key" "$CONFIG_FILE" 2>/dev/null
    else
        grep -A 1 "^  ${key##*.}:" "$CONFIG_FILE" | tail -1 | sed 's/.*: //' | tr -d '"' | tr -d "'"
    fi
}

# Load configuration
REGION=$(read_config ".aws.region")
REGION="${REGION:-us-east-2}"

# Check if OU exists
check_ou() {
    local ou_name="$1"
    local ou_id="$2"
    
    if aws organizations describe-organizational-unit \
        --organizational-unit-id "$ou_id" \
        --region "$REGION" &> /dev/null; then
        log_success "OU exists: $ou_name ($ou_id)"
        return 0
    else
        log_error "OU missing: $ou_name ($ou_id)"
        return 1
    fi
}

# Main validation
main() {
    echo ""
    echo "=========================================="
    echo "  Organization Structure Validation"
    echo "=========================================="
    echo ""
    
    log_info "Using region: $REGION"
    
    # Check if ou-ids.json exists
    if [[ ! -f "$OU_IDS_FILE" ]]; then
        log_error "OU IDs file not found: $OU_IDS_FILE"
        log_info "Run ./deploy-organization.sh first"
        exit 1
    fi
    
    log_info "Reading OU IDs from: $OU_IDS_FILE"
    
    # Validate each OU
    FAILED=0
    
    # Extract and check each OU
    while IFS= read -r line; do
        if [[ "$line" =~ \"([^\"]+)\":\ \"(ou-[^\"]+)\" ]]; then
            ou_name="${BASH_REMATCH[1]}"
            ou_id="${BASH_REMATCH[2]}"
            
            if ! check_ou "$ou_name" "$ou_id"; then
                ((FAILED++))
            fi
        fi
    done < "$OU_IDS_FILE"
    
    echo ""
    if [[ $FAILED -eq 0 ]]; then
        log_success "All OUs validated successfully!"
        exit 0
    else
        log_error "$FAILED OU(s) failed validation"
        exit 1
    fi
}

main "$@"
