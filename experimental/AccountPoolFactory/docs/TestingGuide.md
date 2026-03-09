# Account Pool Factory - Testing Guide

End-to-end testing guide for the Account Pool Factory. Covers deployment, pool seeding, project lifecycle testing, and common failure scenarios.

---

## Prerequisites

- AWS CLI installed and configured
- Python 3.12+ with `boto3` and `pyyaml`
- `isengardcli` for credential switching
- Org Admin account: `495869084367` (amirbo+1)
- Domain account: `994753223772` (amirbo+3)

---

## Configuration

Two minimal config files — one per account. IDs are resolved automatically from names.

**`org-config.yaml`** (for the Org Admin account):
```yaml
region: us-east-2
target_ou_name: "RetailBanking/CustomerAnalytics"  # OU path, ID resolved automatically
```

**`domain-config.yaml`** (for the Domain account):
```yaml
region: us-east-2
domain_name: "your-domain-name"          # ID resolved automatically
default_project_owner: "analyst1-amirbo"
project_profile_name: "All Capabilities - Account Pool"
email_prefix: "accountpool"
email_domain: "example.com"
setup_stacks:
  - "DataZone-VPC-{account_id}"
  - "DataZone-IAM-{account_id}"
  - "DataZone-EventBridge-{account_id}"
  - "DataZone-ProjectRole-{account_id}"
  - "DataZone-Blueprints-{account_id}"
project_role:
  enabled: true
  role_name: AmazonSageMakerProjectRole
  managed_policy_arn: arn:aws:iam::aws:policy/AmazonSageMakerFullAccess
```

Copy the templates and fill in your values:
```bash
cp org-config.yaml.template org-config.yaml    # edit target_ou_name
cp domain-config.yaml.template domain-config.yaml  # edit domain_name, email settings
```

---

## Deployment Order

The org admin must deploy first (the domain account needs the role ARN output). In practice: the domain admin fills in `domain-config.yaml`, asks the org admin to run their script, then runs the domain account deployment.

**Phase 1 — Org Admin account:**

```bash
eval $(isengardcli credentials amirbo+1@amazon.com)
# Pass domain account ID and domain ID as arguments (one-time)
./scripts/01-org-mgmt-account/deploy/deploy-org-admin.sh 994753223772 dzd-4h7jbz76qckoh5
```

The script prints the outputs but the domain deploy script reads them automatically from the CF stack — no manual copy needed.

**Phase 2 — Domain account:**

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
./scripts/02-domain-account/deploy/01-deploy-infrastructure.sh
./scripts/02-domain-account/deploy/02-deploy-project-profile.sh
```

---

## Seed the Pool

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
aws lambda invoke \
  --function-name PoolManager \
  --payload '{"action":"force_replenishment"}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/seed.json

# Monitor — each account takes ~6-8 min
aws logs tail /aws/lambda/SetupOrchestrator --follow --region us-east-2
```

Wait until you see AVAILABLE accounts in DynamoDB:

```bash
aws dynamodb query \
  --table-name AccountPoolFactory-AccountState \
  --index-name StateIndex \
  --key-condition-expression '#s = :s' \
  --expression-attribute-names '{"#s":"state"}' \
  --expression-attribute-values '{":s":{"S":"AVAILABLE"}}' \
  --select COUNT --region us-east-2 \
  --query 'Count' --output text
```

---

## End-to-End Lifecycle Test

The master test script covers the full lifecycle: create project → account ASSIGNED → delete project → account AVAILABLE.

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
python3 tests/integration/test-e2e-pool-lifecycle.py
```

**What it tests:**
1. AccountProvider returns an AVAILABLE pool account
2. Project created with all 17 environment configs pointing to pool account
3. Account transitions to ASSIGNED within 10s (via `AccountProvider.validateAccountAuthorization`)
4. Deployment completes successfully
5. Data sources and environments deleted
6. Project deleted
7. Account transitions to CLEANING (reclaim triggered via DataZone `Environment Deletion Completed` event)
8. DeprovisionAccount runs, SetupOrchestrator re-provisions account
9. Account returns to AVAILABLE

**Expected output:**
```
✅ Account 071378140110 is ASSIGNED (10s)
✅ Project deleted after 0s
✅ Account 071378140110 is back to AVAILABLE (40s after deletion)
✅ End-to-end lifecycle test PASSED
```

---

## Individual Test Scripts

### Check Account Assignment

After creating a project, verify the account moved to ASSIGNED:

```bash
python3 tests/integration/check-assignment.py <account_id> [--timeout 120]
```

### Delete a Project

```bash
python3 tests/integration/delete-project.py <project_id> [--timeout 300]
```

### Check Account Reclaim

After deleting a project, verify the account returns to AVAILABLE:

```bash
python3 tests/integration/check-reclaim.py <account_id> [--timeout 600]
```

### Create Project (IDC domain)

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
python3 .test-create-from-pool-IDC.py
```

---

## Credential Switching

```bash
# Org Admin account
eval $(isengardcli credentials amirbo+1@amazon.com)

# Domain account
eval $(isengardcli credentials amirbo+3@amazon.com)
```

---

## Verify Pool Health

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)

# Run reconciler
aws lambda invoke \
  --function-name AccountReconciler \
  --payload '{"source":"manual","dryRun":false,"autoRecycle":true,"autoReplenish":true}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/reconciler.json

cat /tmp/reconciler.json | python3 -m json.tool
```

---

## Common Failure Modes

### Account stuck in SETTING_UP

SetupOrchestrator timed out or failed. Check logs:

```bash
aws logs tail /aws/lambda/SetupOrchestrator --region us-east-2 | grep -E "FAILED|Error|❌"
```

Trigger recycler to fix:

```bash
aws lambda invoke \
  --function-name AccountRecycler \
  --payload '{"recycleAll":true}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/recycler.json
```

### Replenishment blocked by FAILED accounts

```bash
# See failed accounts
aws dynamodb query \
  --table-name AccountPoolFactory-AccountState \
  --index-name StateIndex \
  --key-condition-expression '#s = :s' \
  --expression-attribute-names '{"#s":"state"}' \
  --expression-attribute-values '{":s":{"S":"FAILED"}}' \
  --region us-east-2

# Remove a specific failed account
aws lambda invoke \
  --function-name PoolManager \
  --payload '{"action":"delete_failed_account","accountId":"ACCOUNT_ID"}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json
```

### Blueprint authorization error (403)

Pool account is missing PolicyGrant resources in its blueprint stack. Trigger a fleet-wide update:

```bash
aws lambda invoke \
  --function-name AccountRecycler \
  --payload '{"updateBlueprints":true}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json
```

### Account not returning to AVAILABLE after project deletion

Check PoolManager logs for the `Environment Deletion Completed` event:

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/PoolManager \
  --region us-east-2 \
  --start-time $(($(date +%s) - 3600))000 \
  --query 'events[*].message' --output text | grep -E "Deletion|reclaim|CLEANING"
```

If the event didn't fire, manually trigger reclaim:

```bash
aws lambda invoke \
  --function-name AccountRecycler \
  --payload '{"accountId":"ACCOUNT_ID","force":true}' \
  --cli-binary-format raw-in-base64-out \
  --region us-east-2 /tmp/response.json
```

---

## Key Resource IDs

| Resource | Value |
|----------|-------|
| Org Admin account | `495869084367` |
| Domain account | `994753223772` |
| DataZone Domain ID | `dzd-4h7jbz76qckoh5` |
| Root Domain Unit ID | `bsmdc8e4dwye5l` |
| Account Pool ID | `c5r1rtjwi2qhbd` |
| Project Profile (All Capabilities) | `5riu03k7l71zc9` |
| Region | `us-east-2` |
| DynamoDB table | `AccountPoolFactory-AccountState` |
