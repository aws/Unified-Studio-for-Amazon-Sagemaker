#!/bin/bash
set -e

# Deploy the AccountPoolFactory Org Admin governance stack.
# Run AFTER the domain account deploy (which outputs ProvisionAccountRoleArn).
#
# Usage:
#   eval $(isengardcli credentials amirbo+1@amazon.com)
#   ./01-org-account/scripts/deploy/01-deploy.sh <domain-account-id> <domain-id> <provision-account-role-arn>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source "$SCRIPT_DIR/../resolve-config.sh"

STACK_NAME="AccountPoolFactory-OrgAdmin"
TEMPLATE="01-org-account/templates/cloudformation/SMUS-AccountPoolFactory-OrgAdmin.yaml"
STACKSET_TEMPLATE_DIR="approved-stacksets/cloudformation/idc"

# ── Arguments ────────────────────────────────────────────────────────────────

DOMAIN_ACCOUNT_ID="${1:-}"
DOMAIN_ID="${2:-}"
PROVISION_ACCOUNT_ROLE_ARN="${3:-}"

# Fall back to existing stack parameters if already deployed
if [ -z "$DOMAIN_ACCOUNT_ID" ] || [ -z "$DOMAIN_ID" ] || [ -z "$PROVISION_ACCOUNT_ROLE_ARN" ]; then
    EXISTING=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" --region "$REGION" \
        --query 'Stacks[0].Parameters' \
        --output json 2>/dev/null || echo "[]")

    [ -z "$DOMAIN_ACCOUNT_ID" ] && DOMAIN_ACCOUNT_ID=$(echo "$EXISTING" | \
        python3 -c "import json,sys; p=json.load(sys.stdin); print(next((x['ParameterValue'] for x in p if x['ParameterKey']=='DomainAccountId'),''))" 2>/dev/null || echo "")
    [ -z "$DOMAIN_ID" ] && DOMAIN_ID=$(echo "$EXISTING" | \
        python3 -c "import json,sys; p=json.load(sys.stdin); print(next((x['ParameterValue'] for x in p if x['ParameterKey']=='DomainId'),''))" 2>/dev/null || echo "")
    [ -z "$PROVISION_ACCOUNT_ROLE_ARN" ] && PROVISION_ACCOUNT_ROLE_ARN=$(echo "$EXISTING" | \
        python3 -c "import json,sys; p=json.load(sys.stdin); print(next((x['ParameterValue'] for x in p if x['ParameterKey']=='ProvisionAccountRoleArn'),''))" 2>/dev/null || echo "")
fi

if [ -z "$DOMAIN_ACCOUNT_ID" ] || [ "$DOMAIN_ACCOUNT_ID" = "None" ]; then
    echo "❌ Domain account ID required."
    echo "   Usage: $0 <domain-account-id> <domain-id> <provision-account-role-arn>"
    exit 1
fi
if [ -z "$DOMAIN_ID" ] || [ "$DOMAIN_ID" = "None" ]; then
    echo "❌ Domain ID required."
    exit 1
fi
if [ -z "$PROVISION_ACCOUNT_ROLE_ARN" ] || [ "$PROVISION_ACCOUNT_ROLE_ARN" = "None" ]; then
    echo "❌ ProvisionAccountRoleArn required (output from domain deploy step 1)."
    exit 1
fi

echo "🚀 Deploying Org Admin Stack"
echo "============================"
echo "Org Admin Account:        $CURRENT_ACCOUNT"
echo "Domain Account:           $DOMAIN_ACCOUNT_ID"
echo "Domain ID:                $DOMAIN_ID"
echo "ProvisionAccount Role:    $PROVISION_ACCOUNT_ROLE_ARN"
echo "Region:                   $REGION"
echo "StackSet Prefix:          $STACKSET_PREFIX"
echo "Approved StackSets:       $(echo "$APPROVED_STACKSETS" | wc -l | tr -d ' ') templates"
echo "OUs:                      $OU_COUNT"
echo ""

# ── Step 1: Deploy CF stack ───────────────────────────────────────────────────

echo "📦 Step 1: Deploying IAM + S3 stack..."
aws cloudformation deploy \
    --template-file "$TEMPLATE" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        DomainAccountId="$DOMAIN_ACCOUNT_ID" \
        DomainId="$DOMAIN_ID" \
        ProvisionAccountRoleArn="$PROVISION_ACCOUNT_ROLE_ARN" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --no-fail-on-empty-changeset
echo "✅ Stack deployed"

BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`TemplateBucketName`].OutputValue' \
    --output text)
echo "   Template bucket: $BUCKET_NAME"
echo ""

# ── Step 2: Upload ALL approved StackSet templates to S3 ──────────────────────

echo "📤 Step 2: Uploading approved StackSet templates to S3..."
for tmpl in "$STACKSET_TEMPLATE_DIR"/*.yaml; do
    fname=$(basename "$tmpl")
    aws s3 cp "$tmpl" "s3://${BUCKET_NAME}/stacksets/common/${fname}" --region "$REGION" > /dev/null
    echo "   ✓ stacksets/common/${fname}"
done
echo "✅ Templates uploaded"
echo ""

# ── Step 3: Write per-OU SSM parameters ───────────────────────────────────────

echo "🔧 Step 3: Writing per-OU SSM parameters..."
i=0
while [ $i -lt $OU_COUNT ]; do
    eval "ou_name=\$OU_${i}_NAME"
    eval "ou_id=\$OU_${i}_ID"
    eval "email_prefix=\$OU_${i}_EMAIL_PREFIX"
    eval "email_domain=\$OU_${i}_EMAIL_DOMAIN"
    eval "account_tags=\$OU_${i}_ACCOUNT_TAGS"

    echo "   OU: $ou_name (ID: $ou_id)"

    aws ssm put-parameter --name "/AccountPoolFactory/OUs/${ou_id}/EmailPrefix" \
        --value "$email_prefix" --type String --overwrite --region "$REGION" > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/OUs/${ou_id}/EmailDomain" \
        --value "$email_domain" --type String --overwrite --region "$REGION" > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/OUs/${ou_id}/AccountTags" \
        --value "$account_tags" --type String --overwrite --region "$REGION" > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/OUs/${ou_id}/OUName" \
        --value "$ou_name" --type String --overwrite --region "$REGION" > /dev/null

    echo "   ✓ SSM params written for OU: $ou_name"
    i=$((i + 1))
done

# Global params
aws ssm put-parameter --name "/AccountPoolFactory/TemplateBucketName" \
    --value "$BUCKET_NAME" --type String --overwrite --region "$REGION" > /dev/null
aws ssm put-parameter --name "/AccountPoolFactory/StackSetPrefix" \
    --value "$STACKSET_PREFIX" --type String --overwrite --region "$REGION" > /dev/null
echo "   ✓ Global SSM params written"
echo ""

# ── Step 4: Create/update StackSet definitions for all approved templates ─────

echo "📦 Step 4: Creating/updating StackSet definitions..."
STACKSET_ADMIN_ARN="arn:aws:iam::${CURRENT_ACCOUNT}:role/SMUS-AccountPoolFactory-StackSetAdmin"

python3 -c "
import json, subprocess, sys, re

prefix = '$STACKSET_PREFIX'
region = '$REGION'
admin_arn = '$STACKSET_ADMIN_ARN'
domain_account_id = '$DOMAIN_ACCOUNT_ID'
domain_id = '$DOMAIN_ID'
bucket = '$BUCKET_NAME'
templates = '''$APPROVED_STACKSETS'''.strip().split('\n')

def get_template_params(s3_key):
    r = subprocess.run(
        ['aws', 's3', 'cp', f's3://{bucket}/{s3_key}', '-', '--region', region],
        capture_output=True, text=True)
    if r.returncode != 0: return set()
    import yaml
    class CFLoader(yaml.SafeLoader): pass
    CFLoader.add_multi_constructor('!', lambda loader, suffix, node: None)
    try:
        t = yaml.load(r.stdout, Loader=CFLoader)
        return set((t or {}).get('Parameters', {}).keys())
    except: return set()

central_bus_arn = f'arn:aws:events:{region}:{domain_account_id}:event-bus/AccountPoolFactory-CentralBus'
ALL_PARAMS = {
    'DomainAccountId': domain_account_id,
    'DomainId': domain_id,
    'CentralEventBusArn': central_bus_arn,
}
DEFINITION_TIME_PARAMS = {'DomainAccountId', 'DomainId', 'CentralEventBusArn'}

for tmpl in templates:
    tmpl = tmpl.strip()
    if not tmpl: continue
    s3_key = f'stacksets/common/{tmpl}'
    s3_url = f'https://s3.{region}.amazonaws.com/{bucket}/{s3_key}'

    stem = re.sub(r'\.yaml$', '', tmpl)
    stem = re.sub(r'^\d+-', '', stem)
    title = ''.join(w.capitalize() for w in re.split(r'[-_]', stem))
    stackset_name = f'{prefix}-{title}'

    declared = get_template_params(s3_key)
    params = [f'ParameterKey={k},ParameterValue={v}'
              for k, v in ALL_PARAMS.items() if k in declared and k in DEFINITION_TIME_PARAMS]

    base_args = ['--template-url', s3_url, '--capabilities', 'CAPABILITY_NAMED_IAM', '--region', region]
    if params: base_args += ['--parameters'] + params

    check = subprocess.run(
        ['aws', 'cloudformation', 'describe-stack-set', '--stack-set-name', stackset_name, '--region', region],
        capture_output=True, text=True)

    if check.returncode == 0:
        cmd = ['aws', 'cloudformation', 'update-stack-set', '--stack-set-name', stackset_name,
               '--administration-role-arn', admin_arn,
               '--execution-role-name', 'SMUS-AccountPoolFactory-StackSetExecution'] + base_args
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0: print(f'   ✓ Updated StackSet: {stackset_name}')
        elif 'No updates' in r.stderr or 'No updates' in r.stdout: print(f'   - No changes: {stackset_name}')
        else: print(f'   ⚠ Update failed for {stackset_name}: {r.stderr.strip()}', file=sys.stderr)
    else:
        cmd = ['aws', 'cloudformation', 'create-stack-set', '--stack-set-name', stackset_name,
               '--permission-model', 'SELF_MANAGED',
               '--administration-role-arn', admin_arn,
               '--execution-role-name', 'SMUS-AccountPoolFactory-StackSetExecution'] + base_args
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0: print(f'   ✓ Created StackSet: {stackset_name}')
        else: print(f'   ⚠ Create failed for {stackset_name}: {r.stderr.strip()}', file=sys.stderr)
"
echo ""

# ── Summary ───────────────────────────────────────────────────────────────────

ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`AccountCreationRoleArn`].OutputValue' \
    --output text)

cat <<EOF
✅ Org Admin deploy complete.

  AccountCreationRoleArn : $ROLE_ARN
  TemplateBucket         : $BUCKET_NAME
  ExternalId             : AccountPoolFactory-${DOMAIN_ACCOUNT_ID}

Domain admin next steps:
  eval \$(isengardcli credentials amirbo+3@amazon.com)
  ./02-domain-account/scripts/deploy/02-deploy-project-profile.sh
  ./02-domain-account/scripts/deploy/03-verify.sh

EOF
