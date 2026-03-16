# Investigation: Account stuck in ASSIGNED after project deletion

## Observation
After deleting project `azdsxdeusnm7u1` (e2e-lf-test-1773530247), account 108750422936 remained in ASSIGNED state for 12+ minutes without transitioning to CLEANING/AVAILABLE.

## Root Cause: Two bugs in the reclaim chain

### Bug 1: `projectId` not cleared on recycle (setup-orchestrator)
`mark_account_available()` in setup-orchestrator sets state=AVAILABLE but never clears `projectId`. When an account is recycled and reassigned, the stale `projectId` from the previous project remains in DynamoDB.

Location: `src/setup-orchestrator/lambda_function.py` → `mark_account_available()`

### Bug 2: `handle_datazone_assignment` doesn't update `projectId` when already set (pool-manager)
When a recycled account is reassigned to a new project, `handle_datazone_assignment()` checks if `projectId` is empty before updating it. Since the stale projectId from the previous project is still there, it skips the update and logs "already ASSIGNED".

Location: `src/pool-manager/lambda_function.py` → `handle_datazone_assignment()` lines 787-793

### Combined effect
1. Account assigned to project `cxmyi00n65vc89` → projectId set to `cxmyi00n65vc89`
2. Project `cxmyi00n65vc89` deleted → reclaim worked (DynamoDB ProjectIndex found the account)
3. Account recycled to AVAILABLE, but projectId still = `cxmyi00n65vc89` (Bug 1)
4. Account reassigned to project `azdsxdeusnm7u1` via AccountProvider
5. `handle_datazone_assignment` saw existing projectId, skipped update (Bug 2)
6. Project `azdsxdeusnm7u1` deleted → deletion events arrived
7. DataZone deletion event payload does NOT include `environmentAccount` field
8. DynamoDB ProjectIndex lookup for `azdsxdeusnm7u1` → 0 results (projectId was never updated)
9. GetEnvironment fallback → ResourceNotFoundException (environment already deleted)
10. PoolManager logs: `⏭️ DataZone event missing environmentAccount and could not look up, skipping`
11. Account stuck in ASSIGNED forever

### Evidence from CloudWatch logs

**Deletion events for project `azdsxdeusnm7u1` (the stuck one):**
```
1773530384938  ⚠️ Could not look up environment b295avdgi00gmh: ResourceNotFoundException
1773530384938  ⏭️ DataZone event missing environmentAccount and could not look up, skipping
1773530404797  ⚠️ Could not look up environment 3j9w58bmu6vbc9: ResourceNotFoundException  
1773530404797  ⏭️ DataZone event missing environmentAccount and could not look up, skipping
```

**Deletion events for project `cxmyi00n65vc89` (the previous one — worked):**
```
1773261808250  🗑️ DataZone environment deleted in account 108750422936 for project cxmyi00n65vc89
1773261808799  ⏳ 1 environment(s) still active in 108750422936, not reclaiming yet
1773261823240  🗑️ DataZone environment deleted in account 108750422936 for project cxmyi00n65vc89
1773261823679  ♻️ All environments deleted from 108750422936, reclaiming...
```

**DynamoDB state confirms stale projectId:**
```json
{
  "accountId": "108750422936",
  "state": "ASSIGNED",
  "projectId": "cxmyi00n65vc89"   // ← stale, should be azdsxdeusnm7u1
}
```

## Fixes Applied

### Fix 1: Clear projectId when recycling to AVAILABLE ✅
In `mark_account_available()` (setup-orchestrator), added `REMOVE projectId, projectStackName` to the UpdateExpression so stale project references are cleared when an account returns to the pool.

### Fix 2: Always update projectId on reassignment ✅
In `handle_datazone_assignment()` (pool-manager), changed the condition from "only update if empty" to "update if different from incoming project". This ensures the ProjectIndex GSI stays accurate after recycling.

### Fix 3: Reconciler detects ASSIGNED accounts with deleted projects ✅
Enhanced the reconciler's ASSIGNED handling to call `get_project()` and check if the project still exists. If deleted, the account is added to `recyclableAccountIds` for reclaim by AccountRecycler.

## Pre-existing Issue?
Yes — this is a pre-existing bug, not caused by the Glue/LF StackSet changes. It affects any account that gets recycled and reassigned. The first assignment always works; subsequent ones after recycling break the reclaim chain.

## Immediate Mitigation
The reconciler fix (Fix 3) will catch this on the next reconciliation run. For the currently stuck account (108750422936), the reconciler will detect the deleted project and queue it for reclaim.
