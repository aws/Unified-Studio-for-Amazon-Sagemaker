# Cross-Domain Data Product Sync — End-to-End Test Plan

Tests the freshly deployed stacks (Marketplace `cross-domain-data-product-sync`,
Producer `cross-domain-data-product-sync-producer`). Lineage schedule is set to
`rate(5 minutes)` for testing.

## Environment

| Thing | Value |
|---|---|
| Producer account | 981797970961 (profile `981-admin`) |
| Marketplace account | 900867815224 (profile `acc4-admin`) |
| Producer Glue DB | `rooter_glue_db_981` |
| Marketplace (target) Glue DB | `glue_db_40g5nf258n4ahz` |
| Producer domain | `dzd-ayhm9x5srysanb` |
| Marketplace domain | `dzd-bu6vgyigz33a07` |
| Producer SMUS portal | https://dzd-ayhm9x5srysanb.sagemaker.us-east-1.on.aws |
| Marketplace SMUS portal | https://dzd-bu6vgyigz33a07.sagemaker.us-east-1.on.aws |
| Marketplace data source | `aqxicovh69bn6v` (`...glue_db_40g5nf258n4ahz-default-datasource`) |
| Registered S3 (zero-copy) | `s3://amazon-sagemaker-981797970961-us-east-1-9a7095c5aed2/dzd-ayhm9x5srysanb/4woe9o68cmkh0n/dev/tables` |

---

## Test 0 — Pre-flight (confirm deployment is healthy)

```bash
# both stacks CREATE_COMPLETE
aws cloudformation describe-stacks --stack-name cross-domain-data-product-sync --profile acc4-admin --query 'Stacks[0].StackStatus' --output text
aws cloudformation describe-stacks --stack-name cross-domain-data-product-sync-producer --profile 981-admin --query 'Stacks[0].StackStatus' --output text

# 4 lambdas present
aws lambda list-functions --profile acc4-admin --query "Functions[?contains(FunctionName,'sync')].FunctionName" --output text

# lineage schedule is rate(5 minutes)
aws events describe-rule --name lineage-sync-schedule --profile acc4-admin --query 'ScheduleExpression' --output text
```
**PASS:** both `CREATE_COMPLETE`; 4 functions listed; schedule `rate(5 minutes)`.

---

## Test 1 — Glue table sync (schema mirror, ~30s)

**Goal:** a new producer table auto-mirrors into the marketplace catalog.

1. In the **producer** SMUS portal → open the project's query editor (or Athena in 981), run:
   ```sql
   CREATE TABLE rooter_glue_db_981.demo_orders
   WITH (format='PARQUET',
     external_location='s3://amazon-sagemaker-981797970961-us-east-1-9a7095c5aed2/dzd-ayhm9x5srysanb/4woe9o68cmkh0n/dev/tables/demo_orders/')
   AS SELECT * FROM (VALUES
     (1,'widget','hardware',19.99),
     (2,'license','software',99.00)) AS t(id,name,category,price);
   ```
2. Wait ~30–60s (CloudTrail → EventBridge → Lambda).
3. **Verify (marketplace):**
   ```bash
   aws glue get-table --database-name glue_db_40g5nf258n4ahz --name demo_orders --profile acc4-admin \
     --query 'Table.{Name:Name,Loc:StorageDescriptor.Location,Cols:StorageDescriptor.Columns[].Name}'
   ```
   Then confirm the Lambda ran:
   ```bash
   aws logs filter-log-events --log-group-name /aws/lambda/glue-table-sync --profile acc4-admin \
     --start-time $(($(date +%s)*1000 - 300000)) --query 'events[].message' --output text | tail -20
   ```

**PASS:** `demo_orders` exists in `glue_db_40g5nf258n4ahz`, columns match, location points at the producer S3; log shows `Created table demo_orders`.
**FAIL triage:** check `glue-sync-from-producer` rule metrics and the glue-table-sync DLQ.

---

## Test 2 — Managed asset creation (data source run)

**Goal:** the mirrored table becomes a subscribable asset.

1. In the **marketplace** SMUS portal → project `ay08mh5ij73lt3` → **Data → Data sources** → run
   `900867815224-AwsDataCatalog-glue_db_40g5nf258n4ahz-default-datasource`.
   (Portal action; the admin CLI can't start it — must be done as a project member.)
2. Wait for the run to finish (status SUCCESS).
3. **Verify (marketplace):**
   ```bash
   aws datazone list-data-source-runs --domain-identifier dzd-bu6vgyigz33a07 \
     --data-source-identifier aqxicovh69bn6v --profile acc4-admin \
     --query 'items[0].{Status:status,Counts:runStatisticsForAssets}' --output json
   ```

**PASS:** latest run `SUCCESS` with `added >= 1`; the `demo_orders` asset is visible in the portal catalog.

---

## Test 3 — Metadata overlay (asset publish → catalog-sync-mirror)

**Goal:** producer business metadata overlays onto the marketplace asset.

1. In the **producer** SMUS portal → open the `demo_orders` asset → add a **description / readme / column descriptions** → **Publish** (creates a new asset version).
2. Wait ~30–60s (asset event → `asset-sync-from-producer` → `catalog-sync-mirror`).
3. **Verify (marketplace):**
   ```bash
   aws logs filter-log-events --log-group-name /aws/lambda/catalog-sync-mirror --profile acc4-admin \
     --start-time $(($(date +%s)*1000 - 300000)) --query 'events[].message' --output text | tail -30
   ```
   And in the marketplace portal, open the `demo_orders` asset — the description/readme should now match the producer's.

**PASS:** log shows `Synced ... / Updated and published managed asset`; marketplace asset shows the producer's metadata.

---

## Test 4 — Data quality sync (event-driven, scoped)

**Goal:** a producer DQ run posts results onto the marketplace asset in real time.

1. In the **producer** (SMUS or Glue console) → create/run a **Data Quality ruleset** on `rooter_glue_db_981.demo_orders` (e.g. a `Completeness "id" > 0.9` rule). Wait for it to finish.
2. Wait ~1 min (native DQ event → scoped producer forwarder → `dq-sync-from-producer` → `dq-results-sync`).
3. **Verify (marketplace):**
   ```bash
   aws logs filter-log-events --log-group-name /aws/lambda/dq-results-sync --profile acc4-admin \
     --start-time $(($(date +%s)*1000 - 600000)) --query 'events[].message' --output text | tail -20
   ```
   Expect `DQ synced for demo_orders ...`. In the marketplace portal, open the asset → **Data quality** tab → the ruleset result should appear.

**PASS:** log shows DQ posted; marketplace asset shows the DQ result.
**Scope check (Comment 1):** run a DQ ruleset on a table in a *different* producer DB → confirm `dq-results-sync` does **not** fire (event filtered at the producer forwarder).

---

## Test 5 — Lineage sync (scheduled, scoped, idempotent) ⭐ new behavior

**Goal:** producer lineage for mirrored tables syncs on the 5-min schedule, engine-agnostic, no duplicates.

1. In the **producer**, run an ETL that produces lineage for a mirrored table — **Glue OR EMR** (test EMR to show engine-agnostic):
   - e.g. a Glue/EMR Spark job that reads `demo_orders` (and another table) and writes an output, with OpenLineage enabled; or any transform that emits lineage into the producer domain.
2. **Within 5 minutes**, the scheduled sweep runs on its own. Watch it:
   ```bash
   # list recent lineage-sync invocations (should fire every 5 min)
   aws logs describe-log-streams --log-group-name /aws/lambda/lineage-sync --profile acc4-admin \
     --order-by LastEventTime --descending --max-items 3 --query 'logStreams[].logStreamName' --output text

   aws logs filter-log-events --log-group-name /aws/lambda/lineage-sync --profile acc4-admin \
     --start-time $(($(date +%s)*1000 - 600000)) --query 'events[].message' --output text | tail -30
   ```
3. In the marketplace portal, open the `demo_orders` asset → **Lineage** tab → upstream lineage should appear.

**PASS:**
- `lineage-sync` fires on the schedule (an invocation every ~5 min, even with no new lineage, logging `Synced N lineage events`).
- Lineage for `demo_orders` shows in the marketplace asset.
- **Scope (Comment 2.1):** lineage for a *non-mirrored* producer table does NOT come across.
- **Idempotency (Comment 2.2):** let the sweep run 2–3 times; the marketplace lineage does NOT accumulate duplicates of the same events.
- **Engine-agnostic:** lineage from the EMR job appears even though there is no Glue job trigger.

---

## Test 6 — Zero-copy query (consumer, Lake Formation vending)

**Goal:** a consumer queries the subscribed product; data is read in place from the producer S3.

1. In the **marketplace** portal, as a consumer, **subscribe** to `demo_orders` and **approve** the subscription.
2. Query it (Athena in the marketplace project):
   ```sql
   SELECT * FROM glue_db_40g5nf258n4ahz.demo_orders LIMIT 10;
   ```
3. **PASS:** rows return (read from the producer S3 via `MirrorCatalogLFRole` credential vending — no data copied).
   **FAIL triage:** `VERIFICATION_FAILED` on the LF registration is informational for cross-account; a real failure shows as `AccessDenied` at query time → check the LF `/dev/tables` registration, the `DATA_LOCATION_ACCESS` grant, and the producer S3 bucket policy.

---

## DLQ / health check (any time)

```bash
for q in glue-table-sync catalog-sync-mirror dq-results-sync lineage-sync; do
  url=$(aws sqs get-queue-url --queue-name cross-domain-$q-dlq --profile acc4-admin --query QueueUrl --output text)
  echo -n "$q DLQ depth: "
  aws sqs get-queue-attributes --queue-url "$url" --attribute-names ApproximateNumberOfMessages --profile acc4-admin --query 'Attributes.ApproximateNumberOfMessages' --output text
done
```
**PASS:** all DLQs at 0 (no failed events).

---

## Summary checklist

- [ ] Test 0 — deployment healthy, schedule = 5 min
- [ ] Test 1 — table schema mirrors (~30s)
- [ ] Test 2 — data source run creates the asset
- [ ] Test 3 — metadata overlay on publish
- [ ] Test 4 — DQ syncs (+ scope check)
- [ ] Test 5 — lineage syncs on schedule (+ scope, dedupe, EMR)
- [ ] Test 6 — zero-copy consumer query
- [ ] DLQs empty
