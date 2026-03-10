#!/bin/bash
set -e

# Deploy the AccountPoolFactory Org Admin governance stack.
# Run AFTER the domain account deploy (which outputs ProvisionAccountRoleArn).
#
# Usage:
#   eval $(isengardcli credentials amirbo+1@amazon.com)
#   ./scripts/01-org-mgmt-account/deploy/01-deploy.sh <domain-account-id> <domain-id> <provision-account-role-arn>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

source scripts/utils/resolve-config.sh org

STACK_NAME="AccountPoolFactory-OrgAdmin"
TEMPLATE="templates/cloudformation/01-org-mgmt-account/deploy/SMUS-AccountPoolFactory-OrgAdmin.yaml"
STACKSET_TEMPLATE_DIR="templates/cloudformation/stacksets/idc"

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
    echo "   Usage: $0 <domain-account-id> <domain-id> <provision-account-role-arn>"
    exit 1
fi
if [ -z "$PROVISION_ACCOUNT_ROLE_ARN" ] || [ "$PROVISION_ACCOUNT_ROLE_ARN" = "None" ]; then
    echo "❌ ProvisionAccountRoleArn required (output from domain deploy step 1)."
    echo "   Usage: $0 <domain-account-id> <domain-id> <provision-account-role-arn>"
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
echo "Pools:                    $POOL_NAMES"
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

# Resolve bucket name from stack output
BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`TemplateBucketName`].OutputValue' \
    --output text)
echo "   Template bucket: $BUCKET_NAME"
echo ""

# ── Step 2: Upload StackSet templates to S3 ───────────────────────────────────

echo "📤 Step 2: Uploading StackSet templates to S3..."

# Upload common templates (project-account deploy templates)
# Map filenames to logical names matching the stackset_prefix convention
# Upload all stackset templates from the stacksets/ folder, preserving filenames
for tmpl in "$STACKSET_TEMPLATE_DIR"/*.yaml; do
    fname=$(basename "$tmpl")
    aws s3 cp "$tmpl" "s3://${BUCKET_NAME}/stacksets/common/${fname}" --region "$REGION" > /dev/null
    echo "   ✓ stacksets/common/${fname}"
done

echo "✅ Common templates uploaded"
echo ""

# ── Step 3: Write per-pool SSM parameters ─────────────────────────────────────

echo "🔧 Step 3: Writing per-pool SSM parameters..."

STACKSET_ADMIN_ARN="arn:aws:iam::${CURRENT_ACCOUNT}:role/SMUS-AccountPoolFactory-StackSetAdmin"

for pool_name in $POOL_NAMES; do
    KEY=$(echo "$pool_name" | tr '[:lower:]-' '[:upper:]_')
    eval "ou_id=\$POOL_${KEY}_OU_ID"
    eval "email_prefix=\$POOL_${KEY}_EMAIL_PREFIX"
    eval "email_domain=\$POOL_${KEY}_EMAIL_DOMAIN"
    eval "account_tags=\$POOL_${KEY}_ACCOUNT_TAGS"
    eval "stacksets_json=\$POOL_${KEY}_STACKSETS"

    echo "   Pool: $pool_name (OU: $ou_id)"

    # Compute stackset names and full S3 URLs, store enriched JSON
    enriched_stacksets=$(python3 -c "
import json, re

prefix = '$STACKSET_PREFIX'
bucket = '$BUCKET_NAME'
region = '$REGION'
pool = '$pool_name'
raw = json.loads('''$stacksets_json''')

result = []
for entry in raw:
    tmpl = entry['template']
    # Resolve S3 key
    if tmpl.startswith('pools/'):
        s3_key = 'stacksets/' + tmpl
    else:
        s3_key = 'stacksets/common/' + tmpl
    s3_url = f'https://s3.{region}.amazonaws.com/{bucket}/{s3_key}'

    # Derive StackSet name: prefix + TitleCase stem (strip leading NN- numeric prefix)
    stem = re.sub(r'\.yaml$', '', tmpl.split('/')[-1])
    stem = re.sub(r'^\d+-', '', stem)  # strip leading numeric prefix e.g. "01-", "05-"
    # Convert kebab/snake to TitleCase
    title = ''.join(w.capitalize() for w in re.split(r'[-_]', stem))
    stackset_name = f'{prefix}-{title}'

    result.append({
        'template': tmpl,
        'stacksetName': stackset_name,
        'wave': entry['wave'],
        's3Url': s3_url
    })
print(json.dumps(result))
")

    # Write SSM params for this pool
    aws ssm put-parameter --name "/AccountPoolFactory/Pools/${pool_name}/OUId" \
        --value "$ou_id" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/Pools/${pool_name}/EmailPrefix" \
        --value "$email_prefix" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/Pools/${pool_name}/EmailDomain" \
        --value "$email_domain" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/Pools/${pool_name}/AccountTags" \
        --value "$account_tags" --type String --overwrite --region "$REGION"  > /dev/null
    aws ssm put-parameter --name "/AccountPoolFactory/Pools/${pool_name}/StackSets" \
        --value "$enriched_stacksets" --type String --overwrite --region "$REGION"  > /dev/null

    echo "   ✓ SSM params written for pool: $pool_name"

    # ── Step 4: Create/update StackSet definitions ────────────────────────────

    echo "   📦 Creating/updating StackSets for pool: $pool_name..."

    python3 -c "
import json, subprocess, sys, urllib.request, re

prefix = '$STACKSET_PREFIX'
region = '$REGION'
admin_arn = '$STACKSET_ADMIN_ARN'
domain_account_id = '$DOMAIN_ACCOUNT_ID'
domain_id = '$DOMAIN_ID'
bucket = '$BUCKET_NAME'
entries = json.loads('''$enriched_stacksets''')

def get_template_params(s3_key):
    '''Fetch template from S3 and return declared parameter names.'''
    r = subprocess.run(
        ['aws', 's3', 'cp', f's3://{bucket}/{s3_key}', '-', '--region', region],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        return set()
    import yaml
    try:
        t = yaml.safe_load(r.stdout)
        return set((t or {}).get('Parameters', {}).keys())
    except Exception:
        # Fallback: regex scan
        return set(re.findall(r'^  (\w+):\s*$', r.stdout, re.MULTILINE))

central_bus_arn = f'arn:aws:events:{region}:{domain_account_id}:event-bus/AccountPoolFactory-CentralBus'

ALL_PARAMS = {
    'DomainAccountId': domain_account_id,
    'DomainId': domain_id,
    'CentralEventBusArn': central_bus_arn,
}

for entry in entries:
    name = entry['stacksetName']
    url  = entry['s3Url']
    s3_key = url.split(bucket + '/')[-1]

    # Only pass parameters the template actually declares AND that we can resolve at definition time.
    # Parameters like ManageAccessRoleArn/ProvisioningRoleArn are per-account and passed at
    # instance creation time by SetupOrchestrator — skip them here.
    DEFINITION_TIME_PARAMS = {'DomainAccountId', 'DomainId', 'CentralEventBusArn'}
    declared = get_template_params(s3_key)
    params = [f'ParameterKey={k},ParameterValue={v}'
              for k, v in ALL_PARAMS.items() if k in declared and k in DEFINITION_TIME_PARAMS]

    base_args = ['--template-url', url, '--capabilities', 'CAPABILITY_NAMED_IAM', '--region', region]
    if params:
        base_args += ['--parameters'] + params

    check = subprocess.run(
        ['aws', 'cloudformation', 'describe-stack-set', '--stack-set-name', name, '--region', region],
        capture_output=True, text=True
    )

    if check.returncode == 0:
        cmd = ['aws', 'cloudformation', 'update-stack-set',
               '--stack-set-name', name,
               '--administration-role-arn', admin_arn,
               '--execution-role-name', 'SMUS-AccountPoolFactory-StackSetExecution'] + base_args
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            print(f'   ✓ Updated StackSet: {name}')
        elif 'No updates' in r.stderr or 'No updates' in r.stdout:
            print(f'   - No changes: {name}')
        else:
            print(f'   ⚠ Update failed for {name}: {r.stderr.strip()}', file=sys.stderr)
    else:
        cmd = ['aws', 'cloudformation', 'create-stack-set', '--stack-set-name', name,
               '--permission-model', 'SELF_MANAGED',
               '--administration-role-arn', admin_arn,
               '--execution-role-name', 'SMUS-AccountPoolFactory-StackSetExecution'] + base_args
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            print(f'   ✓ Created StackSet: {name}')
        else:
            print(f'   ⚠ Create failed for {name}: {r.stderr.strip()}', file=sys.stderr)
"
done

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
  ./scripts/02-domain-account/deploy/02-deploy-project-profile.sh
  ./scripts/02-domain-account/deploy/03-verify.sh

EOF
