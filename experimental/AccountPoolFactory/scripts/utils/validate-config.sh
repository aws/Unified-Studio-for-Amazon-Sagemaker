#!/bin/bash
set -e

# Validate config.yaml exists and has required fields

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Validating config.yaml..."
echo ""

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    echo ""
    echo "Please create config.yaml from one of the examples:"
    echo "   cp examples/config-new-accounts.yaml config.yaml      # For testing"
    echo "   cp examples/config-existing-accounts.yaml config.yaml # For production"
    echo ""
    echo "Then update the values with your account information."
    exit 1
fi

echo "✅ config.yaml exists"

# Required fields
REQUIRED_FIELDS=(
    "region"
    "org_admin_account_id"
    "domain_account_id"
    "domain_id"
    "root_domain_unit_id"
)

MISSING_FIELDS=()

for field in "${REQUIRED_FIELDS[@]}"; do
    value=$(grep "$field:" config.yaml | awk '{print $2}' | tr -d '"' | head -1)
    
    if [ -z "$value" ] || [ "$value" == "REPLACE_WITH_"* ]; then
        MISSING_FIELDS+=("$field")
        echo "❌ Missing or placeholder value for: $field"
    else
        echo "✅ $field: $value"
    fi
done

echo ""

if [ ${#MISSING_FIELDS[@]} -gt 0 ]; then
    echo "❌ Validation failed: ${#MISSING_FIELDS[@]} required field(s) missing or have placeholder values"
    echo ""
    echo "Please update config.yaml with actual values for:"
    for field in "${MISSING_FIELDS[@]}"; do
        echo "   - $field"
    done
    exit 1
fi

echo "✅ All required fields present"
echo ""
echo "Configuration validated successfully!"
