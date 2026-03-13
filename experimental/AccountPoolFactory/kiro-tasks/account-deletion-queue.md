# Account Deletion Queue — Quota-Aware Account Closure

## Status

| Field | Value |
|-------|-------|
| Status | 🔵 In Design |
| Last Updated | 2026-03-13 |
| Current Phase | — |
| Current Task | — |
| Blocked By | — |

### Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | New `PENDING_DELETE` state + Pool Manager rewrite | ⬜ Not started |
| 2 | Account Deleter Lambda (new) | ⬜ Not started |
| 3 | Reconciler + Recycler adjustments | ⬜ Not started |
| 4 | Pool Console UI — filter + dashboard + actions | ⬜ Not started |
| 5 | Infrastructure (EventBridge, IAM, Lambda deploy) | ⬜ Not started |
| 6 | Documentation updates | ⬜ Not started |
| 7 | Testing | ⬜ Not started |

> Status legend: ⬜ Not started · 🔄 In progress · ✅ Done · ❌ Blocked

---

## Problem

When a pool's `ReclaimStrategy` is `DELETE`, the current `reclaim_account_delete()` in
`pool-manager/lambda_function.py`:

1. Sets state to `DELETING`
2. Immediately deletes the DynamoDB record
3. Never calls `organizations:CloseAccount`

The AWS account is forgotten — it stays alive in Organizations, costs money, and is
invisible to the pool. There is no queue, no retry, no quota handling, and no UI
visibility.

### AWS Organizations CloseAccount Quota

- `CloseAccount` has a hard quota: **10% of accounts created in the org** (minimum 10)
  within a rolling 30-day window.
- Exceeding the quota returns `ConstraintViolationException` with reason
  `CLOSE_ACCOUNT_QUOTA_EXCEEDED`.
- Closed accounts enter a 90-day suspended period before permanent removal.

---

## Design

### New Account State: `PENDING_DELETE`

Add a new state to the account lifecycle:

```
ASSIGNED → (project deleted, strategy=DELETE) → PENDING_DELETE → (daily processor) → CLOSED
```

`PENDING_DELETE` means: "This account's project was deleted, it should be closed via
Organizations API, but we haven't done it yet (or the quota was exceeded)."

The DynamoDB record is preserved with all its metadata so the UI can display it,
filter on it, and the daily processor can pick it up.

### New DynamoDB Fields

| Field | Type | Description |
|-------|------|-------------|
| `deletionRequestedDate` | String (ISO) | When the account entered `PENDING_DELETE` |
| `deletionAttemptDate` | String (ISO) | Last time `CloseAccount` was attempted |
| `deletionAttemptCount` | Number | How many times closure was attempted |
| `deletionError` | String | Last error from `CloseAccount` (quota exceeded, etc.) |
| `closedDate` | String (ISO) | When `CloseAccount` succeeded |

### Component Changes

#### 1. Pool Manager — `reclaim_account_delete()` rewrite

Current behavior: sets `DELETING` then deletes the record.

New behavior:
- Set state to `PENDING_DELETE`
- Set `deletionRequestedDate` to now
- Set `deletionAttemptCount` to 0
- Do NOT delete the DynamoDB record
- Do NOT attempt `CloseAccount` (that's the daily processor's job)
- Publish `AccountPendingDelete` CloudWatch metric

Also update `handle_delete_failed_account()` to transition to `PENDING_DELETE`
instead of deleting the record, so failed accounts also enter the deletion queue.

#### 2. New Lambda: `AccountDeleter`

A new Lambda function that processes the deletion queue daily.

**Trigger**: EventBridge scheduled rule — `rate(1 day)` (configurable via SSM).

**Logic**:
1. Query DynamoDB `StateIndex` for all `PENDING_DELETE` accounts
2. Sort by `deletionRequestedDate` ascending (oldest first)
3. For each account (up to a configurable batch limit, default 5):
   a. Assume `SMUS-AccountPoolFactory-AccountCreation` role in Org Admin account
   b. Call `organizations:CloseAccount(AccountId=...)`
   c. On success:
      - Update state to `CLOSED`
      - Set `closedDate` to now
      - Publish `AccountClosed` metric
   d. On `ConstraintViolationException` (quota exceeded):
      - Update `deletionAttemptDate` and increment `deletionAttemptCount`
      - Set `deletionError` to the exception message
      - Stop processing remaining accounts (quota is org-wide)
      - Publish `AccountDeletionQuotaExceeded` metric
      - Send SNS notification
   e. On `AccountNotFoundException`:
      - Account already closed/removed — set state to `CLOSED`, set `closedDate`
   f. On other errors:
      - Update `deletionAttemptDate`, increment `deletionAttemptCount`
      - Set `deletionError`
      - Continue to next account
4. Return summary: attempted, closed, quota_exceeded, errors

**SSM Parameters** (under `/AccountPoolFactory/PoolManager/`):
- `DeletionBatchSize`: max accounts to attempt per run (default: `5`)
- `DeletionSchedule`: EventBridge rate expression (default: `rate(1 day)`)

**Cross-account access**: Uses the existing `SMUS-AccountPoolFactory-AccountCreation`
role in the Org Admin account. This role needs `organizations:CloseAccount` added to
its IAM policy.

#### 3. Reconciler Adjustments

The reconciler (`account-reconciler/lambda_function.py`) currently validates
AVAILABLE accounts and marks unhealthy ones as FAILED. It needs to:

- Skip `PENDING_DELETE` and `CLOSED` accounts during health checks
- Not mark them as ORPHANED or FAILED
- Include `PENDING_DELETE` count in the reconciliation summary

#### 4. Recycler Adjustments

The recycler (`account-recycler/lambda_function.py`) currently marks non-recoverable
errors as `DELETING`. Change this to:

- Mark non-recoverable errors as `PENDING_DELETE` instead of `DELETING`
- Set `deletionRequestedDate` so the daily processor picks them up
- The `DELETING` state becomes unused (backward compat: reconciler treats any
  remaining `DELETING` records as `PENDING_DELETE`)

#### 5. Pool Console UI Changes

The UI (`ui/pool-console/app.js`) already renders any state dynamically via
`state-badge` CSS classes. Changes needed:

**Dashboard** (`renderPoolCard`):
- Add `PENDING_DELETE` to the state counts display
- Add `CLOSED` to the state counts display (dimmed/muted)

**Accounts table filter** (`filterState` dropdown):
- The dropdown is populated from the API — `PENDING_DELETE` will appear
  automatically once accounts exist in that state
- Add CSS class `state-pending_delete` with a distinct color (orange/amber)
- Add CSS class `state-closed` with a muted/gray color

**Account detail panel** (`renderPanel`):
- Show `deletionRequestedDate`, `deletionAttemptDate`, `deletionAttemptCount`,
  `deletionError`, `closedDate` fields when present
- For `PENDING_DELETE` accounts: show "Cancel Deletion" action button
  (transitions back to `AVAILABLE` after running setup)
- For `CLOSED` accounts: show "Remove Record" action button
  (deletes the DynamoDB record to clean up)

**Mock server** (`ui/mock/mock-server.py`):
- Add `PENDING_DELETE` and `CLOSED` sample accounts to mock data

#### 6. Infrastructure Changes

**Org Admin IAM** — `AccountCreationRole` policy:
- Add `organizations:CloseAccount` to the allowed actions
- This is in `templates/cloudformation/01-org-admin/01-governance.yaml`

**Domain Account** — new Lambda + EventBridge:
- Add `AccountDeleter` Lambda resource to `02-domain-account/01-infrastructure.yaml`
- Add EventBridge scheduled rule (`rate(1 day)`)
- Lambda execution role needs: DynamoDB read/write, STS AssumeRole (to Org Admin),
  CloudWatch PutMetricData, SNS Publish, SSM GetParameter
- Add deploy script for the new Lambda

**DynamoDB** — no schema changes needed (DynamoDB is schemaless). The new fields
are just new attributes on existing items. The `StateIndex` GSI already indexes
by `state`, so `PENDING_DELETE` queries work automatically.

---

## State Diagram

```
                    ┌──────────────────────────────────────────────┐
                    │           Normal Pool Lifecycle               │
                    │                                              │
  PROVISIONED ──→ SETTING_UP ──→ AVAILABLE ──→ ASSIGNED           │
                    │                ↑                │             │
                    │                │    (project    │             │
                    │           (REUSE)    deleted)   │             │
                    │                │                ▼             │
                    │           CLEANING ←── strategy?             │
                    │                              │               │
                    │                         (DELETE)              │
                    │                              ▼               │
                    │                      PENDING_DELETE           │
                    │                              │               │
                    │                    (daily processor)          │
                    │                              ▼               │
                    │                           CLOSED             │
                    └──────────────────────────────────────────────┘

  FAILED ──→ (non-recoverable) ──→ PENDING_DELETE ──→ CLOSED
  ORPHANED ──→ (non-recoverable) ──→ PENDING_DELETE ──→ CLOSED
```

---

## Tasks

### Phase 1: `PENDING_DELETE` State + Pool Manager Rewrite

- [ ] 1.1 Rewrite `reclaim_account_delete()` in `src/pool-manager/lambda_function.py`
  - Change target state from `DELETING` to `PENDING_DELETE`
  - Set `deletionRequestedDate`, `deletionAttemptCount = 0`
  - Remove the `dynamodb.delete_item()` call — record must persist
  - Publish `AccountPendingDelete` metric instead of `AccountDeleted`
  - Update log messages

- [ ] 1.2 Update `handle_delete_failed_account()` in `src/pool-manager/lambda_function.py`
  - Instead of deleting the DynamoDB record, transition to `PENDING_DELETE`
  - Set `deletionRequestedDate` and `deletionAttemptCount = 0`
  - Keep the existing error info for debugging

- [ ] 1.3 Update `handle_datazone_deletion()` — no code change needed
  - It already calls `reclaim_account_delete()` which will now do the right thing
  - Verify the flow works end-to-end by reading the code path

### Phase 2: Account Deleter Lambda (New)

- [ ] 2.1 Create `src/account-deleter/lambda_function.py`
  - `lambda_handler`: load config, query `PENDING_DELETE` accounts, process batch
  - `process_deletion_queue()`: sort by `deletionRequestedDate` ASC, iterate up to batch limit
  - `close_account(account_id)`: assume Org Admin role, call `organizations:CloseAccount`
  - Handle `ConstraintViolationException` (quota) — stop batch, update record, notify
  - Handle `AccountNotFoundException` — mark as `CLOSED`
  - Handle other errors — update attempt count, continue
  - `load_config()`: read `DeletionBatchSize` from SSM
  - Publish CloudWatch metrics: `AccountClosed`, `AccountDeletionQuotaExceeded`, `DeletionQueueSize`
  - Send SNS notification on quota exceeded

- [ ] 2.2 Create deploy script `scripts/02-domain-account/deploy/05-deploy-account-deleter.sh`
  - Package and deploy the Lambda
  - Follow the pattern of existing deploy scripts (e.g., `03-deploy-recycler.sh`)

### Phase 3: Reconciler + Recycler Adjustments

- [ ] 3.1 Update `src/account-reconciler/lambda_function.py`
  - Skip `PENDING_DELETE` and `CLOSED` accounts in the validation pass
  - Add `PENDING_DELETE` and `CLOSED` counts to the reconciliation summary
  - Do not create ORPHANED records for accounts in these states

- [ ] 3.2 Update `src/account-recycler/lambda_function.py`
  - In `handle_failed()`: change `DELETING` to `PENDING_DELETE` for non-recoverable errors
  - Set `deletionRequestedDate` when transitioning to `PENDING_DELETE`
  - In `get_recyclable_accounts()`: do NOT include `PENDING_DELETE` (it's not recyclable)
  - Backward compat: if any `DELETING` records exist, treat them as `PENDING_DELETE`

### Phase 4: Pool Console UI

- [ ] 4.1 Update `ui/pool-console/style.css`
  - Add `.state-pending_delete` style (amber/orange background)
  - Add `.state-closed` style (gray/muted background)

- [ ] 4.2 Update `ui/pool-console/app.js` — dashboard
  - Add `PENDING_DELETE` and `CLOSED` to `renderPoolCard()` state counts
  - `CLOSED` should be rendered dimmed/muted

- [ ] 4.3 Update `ui/pool-console/app.js` — account detail panel
  - Show deletion-related fields: `deletionRequestedDate`, `deletionAttemptDate`,
    `deletionAttemptCount`, `deletionError`, `closedDate`
  - For `PENDING_DELETE`: add "Cancel Deletion" button (sets state back to `FAILED`
    so recycler can re-evaluate)
  - For `CLOSED`: add "Remove Record" button (deletes DynamoDB record)

- [ ] 4.4 Update mock server `ui/mock/mock-server.py`
  - Add sample `PENDING_DELETE` and `CLOSED` accounts to mock data
  - Add `/pool/accounts/{id}/cancel-delete` mock endpoint

### Phase 5: Infrastructure

- [ ] 5.1 Update Org Admin IAM — `templates/cloudformation/01-org-admin/01-governance.yaml`
  - Add `organizations:CloseAccount` to `AccountCreationRole` policy

- [ ] 5.2 Update Domain infra — `templates/cloudformation/02-domain-account/01-infrastructure.yaml`
  - Add `AccountDeleter` Lambda function resource
  - Add Lambda execution role with: DynamoDB, STS AssumeRole, CloudWatch, SNS, SSM
  - Add EventBridge scheduled rule: `rate(1 day)` targeting AccountDeleter
  - Add SSM parameters: `DeletionBatchSize` (default 5)
  - Output: `AccountDeleterFunctionName`, `AccountDeleterFunctionArn`

- [ ] 5.3 Add `cancel_delete` and `remove_closed` actions to Pool Manager Lambda
  - `cancel_delete`: transition `PENDING_DELETE` → `FAILED` (recycler re-evaluates)
  - `remove_closed`: delete DynamoDB record for `CLOSED` accounts
  - Wire these to the UI action buttons

### Phase 6: Documentation Updates

- [ ] 6.1 Update `docs/Architecture.md`
  - Add `PENDING_DELETE` and `CLOSED` to the state diagram
  - Document the AccountDeleter Lambda and daily processing flow
  - Document the CloseAccount quota and retry behavior

- [ ] 6.2 Update `docs/DomainAdminGuide.md`
  - Add section on DELETE strategy behavior
  - Document how to monitor the deletion queue
  - Document how to cancel a pending deletion
  - Document the `DeletionBatchSize` SSM parameter

- [ ] 6.3 Update `kiro-tasks/web-ui.md`
  - Add `PENDING_DELETE` and `CLOSED` to the DynamoDB record shape
  - Note the new filter states in the Pool Console section

### Phase 7: Testing

- [ ] 7.1 Unit test: `reclaim_account_delete()` sets `PENDING_DELETE` and preserves record
  - Verify DynamoDB record is NOT deleted
  - Verify `deletionRequestedDate` is set
  - Verify state is `PENDING_DELETE`

- [ ] 7.2 Unit test: AccountDeleter Lambda
  - Mock `organizations:CloseAccount` success → verify state becomes `CLOSED`
  - Mock `ConstraintViolationException` → verify batch stops, error recorded
  - Mock `AccountNotFoundException` → verify state becomes `CLOSED`
  - Verify oldest accounts are processed first
  - Verify batch size limit is respected

- [ ] 7.3 Integration test: end-to-end DELETE strategy flow
  - Create a project on a DELETE-strategy pool
  - Delete the project
  - Verify account enters `PENDING_DELETE` (not deleted from DynamoDB)
  - Invoke AccountDeleter manually
  - Verify account transitions to `CLOSED`

- [ ] 7.4 UI test: verify `PENDING_DELETE` filter works in Pool Console
  - Open Pool Console with mock data
  - Filter by `PENDING_DELETE` state
  - Verify accounts appear with amber badge
  - Verify detail panel shows deletion fields
  - Verify "Cancel Deletion" button works

- [ ] 7.5 Reconciler test: verify `PENDING_DELETE` accounts are skipped
  - Run reconciler with `PENDING_DELETE` accounts in DynamoDB
  - Verify they are not marked FAILED or ORPHANED

---

## Open Questions

- **Q1**: Should `CLOSED` records be auto-cleaned after 90 days (matching AWS suspension
  period)? Could add a DynamoDB TTL on `closedDate + 90d`. Suggest: yes, add TTL.
- **Q2**: Should the daily processor also handle `DELETING` records from before this
  change (backward compat migration)? Suggest: yes, treat `DELETING` as `PENDING_DELETE`.
- **Q3**: Should there be a manual "Close Now" button in the UI for `PENDING_DELETE`
  accounts? Suggest: yes, invoke AccountDeleter for a single account.
