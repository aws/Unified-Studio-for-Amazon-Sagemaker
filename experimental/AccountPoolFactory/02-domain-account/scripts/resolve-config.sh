#!/bin/bash
# resolve-config.sh — Domain admin config resolution.
#
# Source this script to get all resolved variables:
#   source "$SCRIPT_DIR/../resolve-config.sh"
#
# Reads 02-domain-account/config.yaml.
#
# Exports:
#   REGION, CURRENT_ACCOUNT, DOMAIN_ID, DOMAIN_NAME,
#   ROOT_DOMAIN_UNIT_ID, PORTAL_URL, DOMAIN_ACCOUNT_ID,
#   ORG_ADMIN_ACCOUNT_ID, ACCOUNT_CREATION_ROLE_ARN, EXTERNAL_ID, ORG_ID,
#   PROJECT_ROLE_ENABLED, PROJECT_ROLE_NAME, PROJECT_ROLE_POLICY
#   POOL_NAMES — space-separated list of pool names
#   For each pool (POOL_<NAME>_* with name uppercased, hyphens→underscores):
#     POOL_<N>_MIN_SIZE, POOL_<N>_TARGET_SIZE, POOL_<N>_RECLAIM_STRATEGY,
#     POOL_<N>_DEFAULT_PROJECT_OWNER, POOL_<N>_PROJECT_PROFILE_NAME,
#     POOL_<N>_OU_NAME, POOL_<N>_STACKSETS (JSON array)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CONFIG_FILE="$SCRIPT_DIR/../config.yaml"
[ -f "$CONFIG_FILE" ] || { echo "❌ config.yaml not found at $CONFIG_FILE"; return 1 2>/dev/null || exit 1; }

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
    if v is None: print('$default')
    elif isinstance(v, bool): print('true' if v else 'false')
    else: print(v)
except (KeyError, TypeError): print('$default')
" 2>/dev/null || echo "$default"
}

_pool_key() { echo "$1" | tr '[:lower:]-' '[:upper:]_'; }

# ── Resolve ──────────────────────────────────────────────────────────────────

REGION=$(_yaml_get "$CONFIG_FILE" "region" "us-east-2")
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
DOMAIN_ACCOUNT_ID="$CURRENT_ACCOUNT"

export REGION CURRENT_ACCOUNT DOMAIN_ACCOUNT_ID

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
    echo "❌ Could not resolve domain ID. Set domain_name in config.yaml."
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

# Org admin account
ORG_ADMIN_ACCOUNT_ID=$(_yaml_get "$CONFIG_FILE" "org_admin_account_id" "")
if [ -n "$ORG_ADMIN_ACCOUNT_ID" ] && [ "$ORG_ADMIN_ACCOUNT_ID" != "your-org-admin-account-id" ]; then
    ACCOUNT_CREATION_ROLE_ARN="arn:aws:iam::${ORG_ADMIN_ACCOUNT_ID}:role/SMUS-AccountPoolFactory-AccountCreation"
    EXTERNAL_ID="AccountPoolFactory-${DOMAIN_ACCOUNT_ID}"
else
    echo "⚠️  org_admin_account_id not set in config.yaml"
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
PROJECT_ROLE_POLICY=$(_yaml_get "$CONFIG_FILE" "project_role.managed_policy_arn" \
    "arn:aws:iam::aws:policy/SageMakerStudioAdminIAMPermissiveExecutionPolicy")
export PROJECT_ROLE_ENABLED PROJECT_ROLE_NAME PROJECT_ROLE_POLICY

# ── Pools ────────────────────────────────────────────────────────────────────

POOL_NAMES=""
FIRST_POOL=1

while IFS= read -r pool_json; do
    [ -z "$pool_json" ] && continue
    pool_name=$(echo "$pool_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['name'])" 2>/dev/null)
    [ -z "$pool_name" ] && continue
    POOL_NAMES="$POOL_NAMES $pool_name"
    KEY=$(_pool_key "$pool_name")

    eval "$(python3 -c "
import json
p = json.loads('''$pool_json''')
key = '$KEY'
print(f'export POOL_{key}_MIN_SIZE=\"{p.get(\"min_size\", 2)}\"')
print(f'export POOL_{key}_TARGET_SIZE=\"{p.get(\"target_size\", 5)}\"')
print(f'export POOL_{key}_RECLAIM_STRATEGY=\"{p.get(\"reclaim_strategy\", \"REUSE\")}\"')
print(f'export POOL_{key}_DEFAULT_PROJECT_OWNER=\"{p.get(\"default_project_owner\", \"\")}\"')
print(f'export POOL_{key}_PROJECT_PROFILE_NAME=\"{p.get(\"project_profile_name\", \"\")}\"')
print(f'export POOL_{key}_OU_NAME=\"{p.get(\"ou_name\", \"\")}\"')
print(f'export POOL_{key}_OU_ID=\"{p.get(\"ou_id\", \"\")}\"')
ss = json.dumps(p.get('stacksets', []))
print(f\"export POOL_{key}_STACKSETS='{ss}'\")
" 2>/dev/null)"

    # Backward compat: first pool sets legacy single-pool vars
    if [ "$FIRST_POOL" = "1" ]; then
        eval "PROJECT_PROFILE_NAME=\$POOL_${KEY}_PROJECT_PROFILE_NAME"
        eval "DEFAULT_PROJECT_OWNER=\$POOL_${KEY}_DEFAULT_PROJECT_OWNER"
        export PROJECT_PROFILE_NAME DEFAULT_PROJECT_OWNER
        FIRST_POOL=0
    fi
done <<< "$(python3 -c "
import yaml, json
c = yaml.safe_load(open('$CONFIG_FILE'))
for p in c.get('pools', []):
    print(json.dumps(p))
" 2>/dev/null)"

POOL_NAMES="${POOL_NAMES# }"
export POOL_NAMES
