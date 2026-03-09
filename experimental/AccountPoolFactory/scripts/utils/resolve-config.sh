#!/bin/bash
# resolve-config.sh — resolves IDs from human-readable names via AWS APIs.
#
# Source this script to get all resolved variables:
#   source scripts/utils/resolve-config.sh [org|domain]
#
# For org admin scripts:   source scripts/utils/resolve-config.sh org
# For domain scripts:      source scripts/utils/resolve-config.sh domain
#
# Exports:
#   REGION, CURRENT_ACCOUNT
#   (org)    TARGET_OU_ID, TARGET_OU_NAME, ORG_ID
#   (domain) DOMAIN_ID, DOMAIN_NAME, ROOT_DOMAIN_UNIT_ID, PORTAL_URL,
#            DOMAIN_ACCOUNT_ID, ORG_ADMIN_ACCOUNT_ID,
#            ACCOUNT_CREATION_ROLE_ARN, EXTERNAL_ID,
#            EMAIL_PREFIX, EMAIL_DOMAIN, PROJECT_PROFILE_NAME,
#            ORG_ID, TARGET_OU_ID

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODE="${1:-domain}"

# ── Helpers ──────────────────────────────────────────────────────────────────

_yaml_get() {
    local file="$1" key="$2" default="${3:-}"
    python3 -c "
import yaml, sys
try:
    c = yaml.safe_load(open('$file'))
    keys = '$key'.split('.')
    v = c
    for k in keys:
        v = v[k]
    print(v if v is not None else '$default')
except (KeyError, TypeError):
    print('$default')
" 2>/dev/null || echo "$default"
}

_yaml_list() {
    local file="$1" key="$2"
    python3 -c "
import yaml
c = yaml.safe_load(open('$file'))
keys = '$key'.split('.')
v = c
for k in keys:
    v = v[k]
print(','.join(str(x) for x in v))
" 2>/dev/null || echo ""
}

# ── Common ───────────────────────────────────────────────────────────────────

if [ "$MODE" = "org" ]; then
    CONFIG_FILE="$PROJECT_ROOT/org-config.yaml"
    [ -f "$CONFIG_FILE" ] || { echo "❌ org-config.yaml not found in $PROJECT_ROOT"; return 1 2>/dev/null || exit 1; }
    REGION=$(_yaml_get "$CONFIG_FILE" "region" "us-east-2")
else
    CONFIG_FILE="$PROJECT_ROOT/domain-config.yaml"
    [ -f "$CONFIG_FILE" ] || { echo "❌ domain-config.yaml not found in $PROJECT_ROOT"; return 1 2>/dev/null || exit 1; }
    REGION=$(_yaml_get "$CONFIG_FILE" "region" "us-east-2")
fi

CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export REGION CURRENT_ACCOUNT

# ── Org mode ─────────────────────────────────────────────────────────────────

if [ "$MODE" = "org" ]; then
    # Organization ID
    ORG_ID=$(aws organizations describe-organization \
        --query 'Organization.Id' --output text 2>/dev/null || echo "")
    export ORG_ID

    # Target OU — prefer explicit ID, fall back to name lookup
    TARGET_OU_ID=$(_yaml_get "$CONFIG_FILE" "target_ou_id" "")
    TARGET_OU_NAME=$(_yaml_get "$CONFIG_FILE" "target_ou_name" "")

    if [ -z "$TARGET_OU_ID" ] && [ -n "$TARGET_OU_NAME" ]; then
        # Walk the OU path to find the ID
        ROOT_ID=$(aws organizations list-roots \
            --query 'Roots[0].Id' --output text 2>/dev/null || echo "")
        PARENT_ID="$ROOT_ID"
        IFS='/' read -ra OU_PARTS <<< "$TARGET_OU_NAME"
        for OU_PART in "${OU_PARTS[@]}"; do
            TARGET_OU_ID=$(aws organizations list-organizational-units-for-parent \
                --parent-id "$PARENT_ID" \
                --query "OrganizationalUnits[?Name=='$OU_PART'].Id" \
                --output text 2>/dev/null || echo "")
            [ -n "$TARGET_OU_ID" ] && PARENT_ID="$TARGET_OU_ID" || break
        done
    fi

    [ -z "$TARGET_OU_ID" ] && TARGET_OU_ID="root"
    export TARGET_OU_ID TARGET_OU_NAME
    return 0 2>/dev/null || exit 0
fi

# ── Domain mode ──────────────────────────────────────────────────────────────

DOMAIN_ACCOUNT_ID="$CURRENT_ACCOUNT"
export DOMAIN_ACCOUNT_ID

# Domain ID — prefer explicit, fall back to name lookup
DOMAIN_ID=$(_yaml_get "$CONFIG_FILE" "domain_id" "")
DOMAIN_NAME=$(_yaml_get "$CONFIG_FILE" "domain_name" "")

if [ -z "$DOMAIN_ID" ] && [ -n "$DOMAIN_NAME" ]; then
    DOMAIN_ID=$(aws datazone list-domains \
        --region "$REGION" \
        --query "items[?name=='$DOMAIN_NAME'].id" \
        --output text 2>/dev/null | awk '{print $1}')
fi

if [ -z "$DOMAIN_ID" ]; then
    echo "❌ Could not resolve domain ID. Set domain_name in domain-config.yaml."
    return 1 2>/dev/null || exit 1
fi

# Resolve domain details
DOMAIN_INFO=$(aws datazone get-domain \
    --identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --output json 2>/dev/null || echo "{}")

ROOT_DOMAIN_UNIT_ID=$(echo "$DOMAIN_INFO" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(d.get('rootDomainUnitId',''))" 2>/dev/null || echo "")
PORTAL_URL=$(echo "$DOMAIN_INFO" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(d.get('portalUrl',''))" 2>/dev/null || echo "")

export DOMAIN_ID DOMAIN_NAME ROOT_DOMAIN_UNIT_ID PORTAL_URL

# Org Admin account ID — from AccountPoolFactory-OrgAdmin stack or AccountCreation role
ACCOUNT_CREATION_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-OrgAdmin \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`AccountCreationRoleArn`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -n "$ACCOUNT_CREATION_ROLE_ARN" ] && [ "$ACCOUNT_CREATION_ROLE_ARN" != "None" ]; then
    ORG_ADMIN_ACCOUNT_ID=$(echo "$ACCOUNT_CREATION_ROLE_ARN" | sed 's|arn:aws:iam::\([0-9]*\):.*|\1|')
    EXTERNAL_ID="AccountPoolFactory-${DOMAIN_ACCOUNT_ID}"
else
    echo "⚠️  AccountPoolFactory-OrgAdmin stack not found — deploy org admin first"
    ACCOUNT_CREATION_ROLE_ARN=""
    ORG_ADMIN_ACCOUNT_ID=""
    EXTERNAL_ID=""
fi

export ACCOUNT_CREATION_ROLE_ARN EXTERNAL_ID ORG_ADMIN_ACCOUNT_ID

# Organization ID
ORG_ID=""
if [ -n "$ORG_ADMIN_ACCOUNT_ID" ]; then
    # Assume AccountCreation role to get org ID
    ORG_ID=$(aws cloudformation describe-stacks \
        --stack-name AccountPoolFactory-OrgAdmin \
        --region "$REGION" \
        --query 'Stacks[0].Tags[?Key==`OrganizationId`].Value' \
        --output text 2>/dev/null || echo "")
    # Fall back: try organizations API directly (works if domain account is in same org)
    [ -z "$ORG_ID" ] && ORG_ID=$(aws organizations describe-organization \
        --query 'Organization.Id' --output text 2>/dev/null || echo "")
fi
export ORG_ID

# Target OU ID — from org admin stack output or organizations API
TARGET_OU_ID=$(aws cloudformation describe-stacks \
    --stack-name AccountPoolFactory-OrgAdmin \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`TargetOUId`].OutputValue' \
    --output text 2>/dev/null || echo "")
# If not in stack outputs, try SSM (set by deploy-infrastructure)
[ -z "$TARGET_OU_ID" ] || [ "$TARGET_OU_ID" = "None" ] && \
    TARGET_OU_ID=$(aws ssm get-parameter \
        --name /AccountPoolFactory/PoolManager/TargetOUId \
        --region "$REGION" \
        --query 'Parameter.Value' --output text 2>/dev/null || echo "root")
export TARGET_OU_ID

# Config values
EMAIL_PREFIX=$(_yaml_get "$CONFIG_FILE" "email_prefix" "accountpool")
EMAIL_DOMAIN=$(_yaml_get "$CONFIG_FILE" "email_domain" "example.com")
PROJECT_PROFILE_NAME=$(_yaml_get "$CONFIG_FILE" "project_profile_name" "")
DEFAULT_PROJECT_OWNER=$(_yaml_get "$CONFIG_FILE" "default_project_owner" "")
EXPECTED_STACK_PATTERNS=$(_yaml_list "$CONFIG_FILE" "setup_stacks")
PROJECT_ROLE_ENABLED=$(_yaml_get "$CONFIG_FILE" "project_role.enabled" "true")
PROJECT_ROLE_NAME=$(_yaml_get "$CONFIG_FILE" "project_role.role_name" "AmazonSageMakerProjectRole")
PROJECT_ROLE_POLICY=$(_yaml_get "$CONFIG_FILE" "project_role.managed_policy_arn" "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess")

export EMAIL_PREFIX EMAIL_DOMAIN PROJECT_PROFILE_NAME DEFAULT_PROJECT_OWNER
export EXPECTED_STACK_PATTERNS PROJECT_ROLE_ENABLED PROJECT_ROLE_NAME PROJECT_ROLE_POLICY
