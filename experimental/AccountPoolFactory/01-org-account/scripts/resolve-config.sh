#!/bin/bash
# resolve-config.sh — Org admin config resolution.
#
# Source this script to get all resolved variables:
#   source "$SCRIPT_DIR/../resolve-config.sh"
#
# Reads 01-org-account/config.yaml from PROJECT_ROOT.
#
# Exports:
#   REGION, CURRENT_ACCOUNT, ORG_ID, STACKSET_PREFIX
#   APPROVED_STACKSETS     — space-separated list of template filenames
#   OU_COUNT               — number of OUs defined
#   For each OU (OU_<N>_* where N is 0-based index):
#     OU_<N>_NAME, OU_<N>_ID, OU_<N>_EMAIL_PREFIX,
#     OU_<N>_EMAIL_DOMAIN, OU_<N>_ACCOUNT_TAGS (JSON)

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

_resolve_ou_id() {
    local ou_name="$1"
    local root_id
    root_id=$(aws organizations list-roots \
        --query 'Roots[0].Id' --output text 2>/dev/null || echo "")
    local parent_id="$root_id"
    local ou_id=""
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

# ── Resolve ──────────────────────────────────────────────────────────────────

REGION=$(_yaml_get "$CONFIG_FILE" "region" "us-east-2")
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ORG_ID=$(aws organizations describe-organization \
    --query 'Organization.Id' --output text 2>/dev/null || echo "")
STACKSET_PREFIX=$(_yaml_get "$CONFIG_FILE" "stackset_prefix" "SMUS-AccountPoolFactory")

export REGION CURRENT_ACCOUNT ORG_ID STACKSET_PREFIX

# Approved stacksets — flat list of template filenames
APPROVED_STACKSETS=$(python3 -c "
import yaml
c = yaml.safe_load(open('$CONFIG_FILE'))
for t in c.get('approved_stacksets', []):
    print(t)
" 2>/dev/null || echo "")
export APPROVED_STACKSETS

# Per-OU config
OU_COUNT=0
while IFS= read -r ou_json; do
    [ -z "$ou_json" ] && continue
    eval "$(python3 -c "
import json
ou = json.loads('$ou_json')
idx = $OU_COUNT
print(f'export OU_{idx}_NAME=\"{ou[\"name\"]}\"')
print(f'export OU_{idx}_EMAIL_PREFIX=\"{ou.get(\"email_prefix\", \"accountpool\")}\"')
print(f'export OU_{idx}_EMAIL_DOMAIN=\"{ou.get(\"email_domain\", \"example.com\")}\"')
import json as j
print(f\"export OU_{idx}_ACCOUNT_TAGS='{j.dumps(ou.get(\"account_tags\", {}))}'\")" 2>/dev/null)"

    # Resolve OU name to ID
    eval "ou_name=\$OU_${OU_COUNT}_NAME"
    ou_id=$(_resolve_ou_id "$ou_name")
    [ -z "$ou_id" ] && ou_id="root"
    eval "export OU_${OU_COUNT}_ID=\"$ou_id\""

    OU_COUNT=$((OU_COUNT + 1))
done <<< "$(python3 -c "
import yaml, json
c = yaml.safe_load(open('$CONFIG_FILE'))
for ou in c.get('ous', []):
    print(json.dumps(ou))
" 2>/dev/null)"

export OU_COUNT
