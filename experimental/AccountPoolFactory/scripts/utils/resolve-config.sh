#!/bin/bash
# resolve-config.sh — resolves IDs from human-readable names via AWS APIs.
#
# Source this script to get all resolved variables:
#   source scripts/utils/resolve-config.sh [org|domain]
#
# For org admin scripts:   source scripts/utils/resolve-config.sh org
# For domain scripts:      source scripts/utils/resolve-config.sh domain
#
# Exports (org mode):
#   REGION, CURRENT_ACCOUNT, ORG_ID, STACKSET_PREFIX
#   POOL_NAMES          — space-separated list of pool names
#   For each pool (POOL_<NAME>_* with name uppercased, hyphens→underscores):
#     POOL_<N>_OU_NAME, POOL_<N>_OU_ID, POOL_<N>_EMAIL_PREFIX,
#     POOL_<N>_EMAIL_DOMAIN, POOL_<N>_ACCOUNT_TAGS (JSON),
#     POOL_<N>_STACKSETS (JSON array)
#   First pool also exported as TARGET_OU_ID, EMAIL_PREFIX, EMAIL_DOMAIN
#   (backward compat for scripts that only handle one pool)
#
# Exports (domain mode):
#   REGION, CURRENT_ACCOUNT, DOMAIN_ID, DOMAIN_NAME,
#   ROOT_DOMAIN_UNIT_ID, PORTAL_URL, DOMAIN_ACCOUNT_ID,
#   ORG_ADMIN_ACCOUNT_ID, ACCOUNT_CREATION_ROLE_ARN, EXTERNAL_ID, ORG_ID,
#   POOL_NAMES          — space-separated list of pool names
#   For each pool (POOL_<NAME>_* with name uppercased, hyphens→underscores):
#     POOL_<N>_MIN_SIZE, POOL_<N>_TARGET_SIZE, POOL_<N>_RECLAIM_STRATEGY,
#     POOL_<N>_DEFAULT_PROJECT_OWNER, POOL_<N>_PROJECT_PROFILE_NAME
#   First pool also exported as PROJECT_PROFILE_NAME, DEFAULT_PROJECT_OWNER
#   (backward compat)
#   PROJECT_ROLE_ENABLED, PROJECT_ROLE_NAME, PROJECT_ROLE_POLICY

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
    if v is None:
        print('$default')
    elif isinstance(v, bool):
        print('true' if v else 'false')
    else:
        print(v)
except (KeyError, TypeError):
    print('$default')
" 2>/dev/null || echo "$default"
}

# Get pool names as newline-separated list
_yaml_pool_names() {
    local file="$1"
    python3 -c "
import yaml
c = yaml.safe_load(open('$file'))
for p in c.get('pools', []):
    print(p['name'])
" 2>/dev/null || echo ""
}

# Get a field from a specific pool by name
_yaml_pool_get() {
    local file="$1" pool_name="$2" field="$3" default="${4:-}"
    python3 -c "
import yaml
c = yaml.safe_load(open('$file'))
for p in c.get('pools', []):
    if p['name'] == '$pool_name':
        v = p.get('$field', '$default')
        print(v if v is not None else '$default')
        break
else:
    print('$default')
" 2>/dev/null || echo "$default"
}

# Get account_tags for a pool as JSON object string
_yaml_pool_tags_json() {
    local file="$1" pool_name="$2"
    python3 -c "
import yaml, json
c = yaml.safe_load(open('$file'))
for p in c.get('pools', []):
    if p['name'] == '$pool_name':
        tags = p.get('account_tags', {})
        tags.setdefault('Pool', '$pool_name')
        print(json.dumps(tags))
        break
else:
    print('{}')
" 2>/dev/null || echo "{}"
}

# Get stacksets for a pool as JSON array string
_yaml_pool_stacksets_json() {
    local file="$1" pool_name="$2"
    python3 -c "
import yaml, json
c = yaml.safe_load(open('$file'))
for p in c.get('pools', []):
    if p['name'] == '$pool_name':
        print(json.dumps(p.get('stacksets', [])))
        break
else:
    print('[]')
" 2>/dev/null || echo "[]"
}

# Normalize pool name to env var safe key (uppercase, hyphens→underscores)
_pool_key() {
    echo "$1" | tr '[:lower:]-' '[:upper:]_'
}

# Walk OU path to find ID
_resolve_ou_id() {
    local ou_name="$1"
    local root_id
    root_id=$(aws organizations list-roots \
        --query 'Roots[0].Id' --output text 2>/dev/null || echo "")
    local parent_id="$root_id"
    local ou_id=""
    # Use python to split on / to avoid IFS issues
    local parts
    parts=$(python3 -c "print('\n'.join('$ou_name'.split('/')))" 2>/dev/null)
    while IFS= read -r part; do
        [ -z "$part" ] && continue
        ou_id=$(aws organizations list-organizational-units-for-parent \
            --parent-id "$parent_id" \
            --query "OrganizationalUnits[?Name=='$part'].Id" \
            --output text 2>/dev/null || echo "")
        [ -n "$ou_id" ] && parent_id="$ou_id" || break
    done <<< "$parts"
    echo "$ou_id"
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
    ORG_ID=$(aws organizations describe-organization \
        --query 'Organization.Id' --output text 2>/dev/null || echo "")
    export ORG_ID

    STACKSET_PREFIX=$(_yaml_get "$CONFIG_FILE" "stackset_prefix" "SMUS-AccountPoolFactory")
    export STACKSET_PREFIX

    # Iterate pools
    POOL_NAMES_LIST=$(_yaml_pool_names "$CONFIG_FILE")
    POOL_NAMES=""
    FIRST_POOL=1

    while IFS= read -r pool_name; do
        [ -z "$pool_name" ] && continue
        POOL_NAMES="$POOL_NAMES $pool_name"
        KEY=$(_pool_key "$pool_name")

        # OU ID — prefer explicit, fall back to name lookup
        ou_id=$(_yaml_pool_get "$CONFIG_FILE" "$pool_name" "ou_id" "")
        ou_name=$(_yaml_pool_get "$CONFIG_FILE" "$pool_name" "ou_name" "")
        if [ -z "$ou_id" ] && [ -n "$ou_name" ]; then
            ou_id=$(_resolve_ou_id "$ou_name")
        fi
        [ -z "$ou_id" ] && ou_id="root"

        email_prefix=$(_yaml_pool_get "$CONFIG_FILE" "$pool_name" "email_prefix" "accountpool")
        email_domain=$(_yaml_pool_get "$CONFIG_FILE" "$pool_name" "email_domain" "example.com")
        account_tags=$(_yaml_pool_tags_json "$CONFIG_FILE" "$pool_name")
        stacksets=$(_yaml_pool_stacksets_json "$CONFIG_FILE" "$pool_name")

        eval "export POOL_${KEY}_OU_NAME=\"$ou_name\""
        eval "export POOL_${KEY}_OU_ID=\"$ou_id\""
        eval "export POOL_${KEY}_EMAIL_PREFIX=\"$email_prefix\""
        eval "export POOL_${KEY}_EMAIL_DOMAIN=\"$email_domain\""
        eval "export POOL_${KEY}_ACCOUNT_TAGS='$account_tags'"
        eval "export POOL_${KEY}_STACKSETS='$stacksets'"

        # Backward compat: first pool sets the legacy single-pool vars
        if [ "$FIRST_POOL" = "1" ]; then
            TARGET_OU_ID="$ou_id"
            TARGET_OU_NAME="$ou_name"
            EMAIL_PREFIX="$email_prefix"
            EMAIL_DOMAIN="$email_domain"
            export TARGET_OU_ID TARGET_OU_NAME EMAIL_PREFIX EMAIL_DOMAIN
            FIRST_POOL=0
        fi
    done <<< "$POOL_NAMES_LIST"

    POOL_NAMES="${POOL_NAMES# }"  # trim leading space
    export POOL_NAMES
    return 0 2>/dev/null || exit 0
fi

# ── Domain mode ──────────────────────────────────────────────────────────────

DOMAIN_ACCOUNT_ID="$CURRENT_ACCOUNT"
export DOMAIN_ACCOUNT_ID

# Domain ID
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

DOMAIN_INFO=$(aws datazone get-domain \
    --identifier "$DOMAIN_ID" \
    --region "$REGION" \
    --output json 2>/dev/null || echo "{}")

ROOT_DOMAIN_UNIT_ID=$(echo "$DOMAIN_INFO" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(d.get('rootDomainUnitId',''))" 2>/dev/null || echo "")
PORTAL_URL=$(echo "$DOMAIN_INFO" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(d.get('portalUrl',''))" 2>/dev/null || echo "")

export DOMAIN_ID DOMAIN_NAME ROOT_DOMAIN_UNIT_ID PORTAL_URL

# Org admin account — from AccountPoolFactory-OrgAdmin stack output
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

ORG_ID=$(aws organizations describe-organization \
    --query 'Organization.Id' --output text 2>/dev/null || echo "")
export ORG_ID

# Project role config
PROJECT_ROLE_ENABLED=$(_yaml_get "$CONFIG_FILE" "project_role.enabled" "true")
PROJECT_ROLE_NAME=$(_yaml_get "$CONFIG_FILE" "project_role.role_name" "AmazonSageMakerProjectRole")
PROJECT_ROLE_POLICY=$(_yaml_get "$CONFIG_FILE" "project_role.managed_policy_arn" "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess")
export PROJECT_ROLE_ENABLED PROJECT_ROLE_NAME PROJECT_ROLE_POLICY

# Iterate pools
POOL_NAMES_LIST=$(_yaml_pool_names "$CONFIG_FILE")
POOL_NAMES=""
FIRST_POOL=1

while IFS= read -r pool_name; do
    [ -z "$pool_name" ] && continue
    POOL_NAMES="$POOL_NAMES $pool_name"
    KEY=$(_pool_key "$pool_name")

    min_size=$(_yaml_pool_get "$CONFIG_FILE" "$pool_name" "min_size" "2")
    target_size=$(_yaml_pool_get "$CONFIG_FILE" "$pool_name" "target_size" "5")
    reclaim=$(_yaml_pool_get "$CONFIG_FILE" "$pool_name" "reclaim_strategy" "REUSE")
    owner=$(_yaml_pool_get "$CONFIG_FILE" "$pool_name" "default_project_owner" "")
    profile=$(_yaml_pool_get "$CONFIG_FILE" "$pool_name" "project_profile_name" "")

    eval "export POOL_${KEY}_MIN_SIZE=\"$min_size\""
    eval "export POOL_${KEY}_TARGET_SIZE=\"$target_size\""
    eval "export POOL_${KEY}_RECLAIM_STRATEGY=\"$reclaim\""
    eval "export POOL_${KEY}_DEFAULT_PROJECT_OWNER=\"$owner\""
    eval "export POOL_${KEY}_PROJECT_PROFILE_NAME=\"$profile\""

    # Backward compat: first pool sets legacy single-pool vars
    if [ "$FIRST_POOL" = "1" ]; then
        PROJECT_PROFILE_NAME="$profile"
        DEFAULT_PROJECT_OWNER="$owner"
        export PROJECT_PROFILE_NAME DEFAULT_PROJECT_OWNER
        FIRST_POOL=0
    fi
done <<< "$POOL_NAMES_LIST"

POOL_NAMES="${POOL_NAMES# }"
export POOL_NAMES
