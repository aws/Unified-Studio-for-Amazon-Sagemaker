#!/bin/bash

# Helper script to display account switching instructions

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
        echo "🔄 Switch to Organization Management account (amirbo+1)"
        echo ""
        echo "  eval \$(isengardcli credentials amirbo+1@amazon.com)"
        ;;
    domain)
        echo "🔄 Switch to Domain account (amirbo+3)"
        echo ""
        echo "  eval \$(isengardcli credentials amirbo+3@amazon.com)"
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
