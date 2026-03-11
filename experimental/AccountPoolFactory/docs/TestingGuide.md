# Account Pool Factory - Testing Guide

[← Back to README](../README.md) | [Org Admin Guide](OrgAdminGuide.md) | [Domain Admin Guide](DomainAdminGuide.md) | [Architecture](Architecture.md) | [Security Guide](SecurityGuide.md)

---

End-to-end testing guide. Covers fresh-account setup, deployment, pool seeding, project lifecycle testing, and common failure scenarios.

---

## Starting from Scratch

If you don't yet have an AWS Organization structure or a SMUS domain, set those up first.

### Create Organization Structure

Skip if your org and OUs already exist.

```bash
eval $(isengardcli credentials amirbo+1@amazon.com)
./tests/setup/scripts/deploy-organization.sh
```

Creates CloudFormation stack `AccountPoolFactory-Organization-Test` with OUs:
- `RetailBanking/CustomerAnalytics` — target for project accounts
- `RetailBanking/RiskAnalytics`
- `CommercialBanking`

### Create SMUS Domain

Skip if your domain already exists.

Navigate to the SageMaker Unified Studio console, create a domain, wait ~5-10 minutes, then copy the domain ID (`dzd-xxxxxxxxxxxxx`) and set it as `domain_name` in `domain-config.yaml`.

---

## Deployment

Fill in config files, then follow the admin guides in order:

```bash
cp org-config.yaml.template org-config.yaml       # set region, ou_name, email settings
cp domain-config.yaml.template domain-config.yaml  # set region, domain_name, email settings
```

1. **Domain admin deploys first** → [DomainAdminGuide.md](DomainAdminGuide.md) Steps 1–4
2. **Org admin deploys** → [OrgAdminGuide.md](OrgAdminGuide.md)
3. **Domain admin seeds the pool** → [DomainAdminGuide.md](DomainAdminGuide.md) Step 5

---

## End-to-End Lifecycle Test

Tests the full lifecycle: create project → account ASSIGNED → delete project → account AVAILABLE.

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
python3 tests/integration/test-e2e-pool-lifecycle.py
```

**What it tests:**
1. AccountProvider returns an AVAILABLE pool account
2. Project created with environment configs pointing to pool account
3. Account transitions to ASSIGNED within 10s
4. Deployment completes successfully
5. Data sources and environments deleted
6. Project deleted
7. Account transitions to CLEANING (reclaim triggered via SMUS event)
8. DeprovisionAccount runs, SetupOrchestrator re-provisions account
9. Account returns to AVAILABLE

**Expected output:**
```
✅ Account <pool-account-id> is ASSIGNED (10s)
✅ Project deleted
✅ Account <pool-account-id> is back to AVAILABLE (40s after deletion)
✅ End-to-end lifecycle test PASSED
```

---

## Verify Pool Health

```bash
eval $(isengardcli credentials amirbo+3@amazon.com)
./scripts/utils/verify-pool-health.sh           # full self-healing
./scripts/utils/verify-pool-health.sh --dry-run # preview only
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
aws lambda invoke --function-name AccountRecycler \
  --payload '{"recycleAll":true}' \
  --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/r.json
```

### Replenishment blocked by FAILED accounts

```bash
# See failed accounts
aws dynamodb query --table-name AccountPoolFactory-AccountState \
  --index-name StateIndex \
  --key-condition-expression '#s = :s' \
  --expression-attribute-names '{"#s":"state"}' \
  --expression-attribute-values '{":s":{"S":"FAILED"}}' \
  --region us-east-2

# Remove a specific failed account
aws lambda invoke --function-name PoolManager \
  --payload '{"action":"delete_failed_account","accountId":"ACCOUNT_ID"}' \
  --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/r.json
```

### Blueprint authorization error (403)

Pool account is missing PolicyGrant resources. Trigger a fleet-wide update:
```bash
aws lambda invoke --function-name AccountRecycler \
  --payload '{"updateBlueprints":true}' \
  --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/r.json
```

### Account not returning to AVAILABLE after project deletion

Check PoolManager logs for the `Environment Deletion Completed` event:
```bash
aws logs filter-log-events --log-group-name /aws/lambda/PoolManager \
  --region us-east-2 \
  --start-time $(($(date +%s) - 3600))000 \
  --query 'events[*].message' --output text | grep -E "Deletion|reclaim|CLEANING"
```

If the event didn't fire, manually trigger reclaim:
```bash
aws lambda invoke --function-name AccountRecycler \
  --payload '{"accountId":"ACCOUNT_ID","force":true}' \
  --cli-binary-format raw-in-base64-out --region us-east-2 /tmp/r.json
```

---

## Cleanup (Test Environment)

```bash
eval $(isengardcli credentials amirbo+1@amazon.com)
aws cloudformation delete-stack --stack-name AccountPoolFactory-Organization-Test --region us-east-2

eval $(isengardcli credentials amirbo+3@amazon.com)
aws datazone delete-domain --identifier YOUR_DOMAIN_ID --region us-east-2
```
