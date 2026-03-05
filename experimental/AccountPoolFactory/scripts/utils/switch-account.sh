#!/bin/bash

# Helper script to display account switching instructions

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Load configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

ORG_MGMT_ACCOUNT_ID=$(grep "org_admin_account_id:" config.yaml | awk '{print $2}' | tr -d '"')
DOMAIN_ACCOUNT_ID=$(grep "domain_account_id:" config.yaml | awk '{print $2}' | tr -d '"')

ACCOUNT_TYPE=$1

if [ -z "$ACCOUNT_TYPE" ]; then
    echo "Usage: $0 <org-mgmt|domain>"
    echo ""
    echo "Examples:"
    echo "   $0 org-mgmt    # Switch to Organization Management account"
    echo "   $0 domain      # Switch to Domain account"
    exit 1
fi

case "$ACCOUNT_TYPE" in
    org-mgmt)
        echo "🔄 Switch to Organization Management account"
        echo ""
        echo "Account ID: $ORG_MGMT_ACCOUNT_ID"
        echo ""
        echo "Use your organization's method to assume credentials for this account."
        echo "For example, using AWS CLI profiles:"
        echo "   export AWS_PROFILE=org-mgmt-account"
        ;;
    domain)
        echo "🔄 Switch to Domain account"
        echo ""
        echo "Account ID: $DOMAIN_ACCOUNT_ID"
        echo ""
        echo "Use your organization's method to assume credentials for this account."
        echo "For example, using AWS CLI profiles:"
        echo "   export AWS_PROFILE=domain-account"
        ;;
    *)
        echo "❌ Unknown account type: $ACCOUNT_TYPE"
        echo "   Valid options: org-mgmt, domain"
        exit 1
        ;;
esac

echo ""
echo "After switching, verify with:"
echo "   aws sts get-caller-identity"
