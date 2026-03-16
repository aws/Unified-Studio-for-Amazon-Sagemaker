#!/bin/bash
set -e

# Validate 01-org-account/config.yaml and 02-domain-account/config.yaml exist and have required fields

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Validating configuration files..."
echo ""

ERRORS=0

# ── 01-org-account/config.yaml ──────────────────────────────────────────────────────────
echo "── 01-org-account/config.yaml ──"

if [ ! -f "01-org-account/config.yaml" ]; then
    echo "❌ 01-org-account/config.yaml not found"
    echo "   Create it with at minimum: region, target_ou_name (or target_ou_id)"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ 01-org-account/config.yaml exists"

    ORG_REQUIRED_FIELDS=("region")
    for field in "${ORG_REQUIRED_FIELDS[@]}"; do
        value=$(python3 -c "import yaml; c=yaml.safe_load(open('01-org-account/config.yaml')); print(c.get('$field',''))" 2>/dev/null || echo "")
        if [ -z "$value" ]; then
            echo "❌ Missing required field: $field"
            ERRORS=$((ERRORS + 1))
        else
            echo "✅ $field: $value"
        fi
    done

    # At least one of target_ou_id or target_ou_name must be set
    OU_ID=$(python3 -c "import yaml; c=yaml.safe_load(open('01-org-account/config.yaml')); print(c.get('target_ou_id',''))" 2>/dev/null || echo "")
    OU_NAME=$(python3 -c "import yaml; c=yaml.safe_load(open('01-org-account/config.yaml')); print(c.get('target_ou_name',''))" 2>/dev/null || echo "")
    if [ -z "$OU_ID" ] && [ -z "$OU_NAME" ]; then
        echo "❌ Must set target_ou_id or target_ou_name"
        ERRORS=$((ERRORS + 1))
    else
        [ -n "$OU_ID" ]   && echo "✅ target_ou_id: $OU_ID"
        [ -n "$OU_NAME" ] && echo "✅ target_ou_name: $OU_NAME"
    fi
fi

echo ""

# ── 02-domain-account/config.yaml ───────────────────────────────────────────────────────
echo "── 02-domain-account/config.yaml ──"

if [ ! -f "02-domain-account/config.yaml" ]; then
    echo "❌ 02-domain-account/config.yaml not found"
    echo "   Create it with at minimum: region, domain_name (or domain_id), email_prefix, email_domain"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ 02-domain-account/config.yaml exists"

    DOMAIN_REQUIRED_FIELDS=("region" "email_prefix" "email_domain")
    for field in "${DOMAIN_REQUIRED_FIELDS[@]}"; do
        value=$(python3 -c "import yaml; c=yaml.safe_load(open('02-domain-account/config.yaml')); print(c.get('$field',''))" 2>/dev/null || echo "")
        if [ -z "$value" ]; then
            echo "❌ Missing required field: $field"
            ERRORS=$((ERRORS + 1))
        else
            echo "✅ $field: $value"
        fi
    done

    # At least one of domain_id or domain_name must be set
    DOMAIN_ID=$(python3 -c "import yaml; c=yaml.safe_load(open('02-domain-account/config.yaml')); print(c.get('domain_id',''))" 2>/dev/null || echo "")
    DOMAIN_NAME=$(python3 -c "import yaml; c=yaml.safe_load(open('02-domain-account/config.yaml')); print(c.get('domain_name',''))" 2>/dev/null || echo "")
    if [ -z "$DOMAIN_ID" ] && [ -z "$DOMAIN_NAME" ]; then
        echo "❌ Must set domain_id or domain_name"
        ERRORS=$((ERRORS + 1))
    else
        [ -n "$DOMAIN_ID" ]   && echo "✅ domain_id: $DOMAIN_ID"
        [ -n "$DOMAIN_NAME" ] && echo "✅ domain_name: $DOMAIN_NAME"
    fi

    # Optional but recommended fields
    for field in "project_profile_name" "default_project_owner"; do
        value=$(python3 -c "import yaml; c=yaml.safe_load(open('02-domain-account/config.yaml')); print(c.get('$field',''))" 2>/dev/null || echo "")
        if [ -z "$value" ]; then
            echo "⚠️  Optional field not set: $field"
        else
            echo "✅ $field: $value"
        fi
    done
fi

echo ""

# ── Summary ──────────────────────────────────────────────────────────────────
if [ "$ERRORS" -eq 0 ]; then
    echo "✅ Configuration validated successfully!"
else
    echo "❌ Validation failed: $ERRORS error(s)"
    echo ""
    echo "See examples/ for reference configurations."
    exit 1
fi
