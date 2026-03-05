# Wave-Based Deployment Optimization Analysis

## Current Wave Structure

The Setup Orchestrator currently deploys resources in 6 waves:

### Wave 1: VPC Deployment (~2.5 min)
- **Stack**: `DataZone-VPC-{accountId}`
- **Resources**: VPC with 3 private subnets across 3 AZs
- **Dependencies**: None (foundation layer)
- **Reason for Wave 1**: Must exist before IAM roles and EventBridge rules

### Wave 2: IAM Roles + EventBridge Rules (parallel, ~2 min)
- **Stacks**: 
  - `DataZone-IAM-{accountId}` (IAM roles)
  - `DataZone-EventBridge-{accountId}` (EventBridge rules)
- **Resources**:
  - ManageAccessRole, ProvisioningRole
  - EventBridge rules forwarding to Domain account central bus
- **Dependencies**: 
  - IAM roles need VPC ID (passed as parameter)
  - EventBridge rules need VPC ID (passed as parameter)
- **Reason for Wave 2**: Both need VPC ID from Wave 1, but are independent of each other

### Wave 3: S3 Bucket + RAM Share (parallel, ~1 min)
- **Operations**:
  - S3 bucket creation (API call, not CloudFormation)
  - RAM share creation (API call, not CloudFormation)
- **Resources**:
  - S3 bucket: `datazone-blueprints-{accountId}-{region}`
  - RAM share: `DataZone-Domain-Share-{accountId}`
- **Dependencies**:
  - S3 bucket: Needs IAM roles (passed as parameter)
  - RAM share: NO dependencies (only needs Domain ID from config)
- **Reason for Wave 3**: 
  - S3 bucket needs IAM roles from Wave 2
  - RAM share could potentially move earlier

### Wave 4: Blueprint Enablement (~3 min)
- **Stack**: `DataZone-Blueprints-{accountId}`
- **Resources**: 17 DataZone EnvironmentBlueprintConfiguration resources + PolicyGrants
- **Dependencies**:
  - VPC ID and subnet IDs (from Wave 1)
  - ManageAccessRole and ProvisioningRole ARNs (from Wave 2)
  - S3 bucket name (from Wave 3)
- **Reason for Wave 4**: Needs outputs from Waves 1, 2, and 3

### Wave 5: Policy Grants (SKIPPED)
- **Status**: Now included in blueprint template (Wave 4)
- **Reason**: Consolidated to reduce waves

### Wave 6: Domain Visibility Verification (~1 min)
- **Operation**: Polling DataZone API to verify domain is accessible
- **Dependencies**: RAM share must be active and propagated (from Wave 3)
- **Reason for Wave 6**: Must wait for RAM share propagation before DataZone can see the domain

---

## Dependency Analysis

### Actual Dependencies (Must Respect)

```
Wave 1: VPC
  ↓
Wave 2: IAM Roles, EventBridge Rules (parallel)
  ↓
Wave 3: S3 Bucket (needs IAM roles)
  ↓
Wave 4: Blueprint Enablement (needs VPC, IAM roles, S3 bucket)
  ↓
Wave 6: Domain Visibility (needs RAM share propagation)
```

### RAM Share Dependencies

**Current placement**: Wave 3 (parallel with S3 bucket)

**Actual dependencies**:
- Domain ID (from config) ✅
- Domain account ID (from config) ✅
- Project account ID (from event) ✅

**Does NOT depend on**:
- VPC ❌
- IAM roles ❌
- EventBridge rules ❌
- S3 bucket ❌

**What depends on RAM share**:
- Wave 6: Domain Visibility Verification (must wait for RAM share to propagate)

---

## Why Current Wave Structure Exists

### Wave 1: VPC (Must be first)
✅ **Correct placement**
- VPC is the foundation - many resources reference VPC ID and subnet IDs
- CloudFormation parameters require VPC outputs
- Cannot parallelize with anything

### Wave 2: IAM Roles + EventBridge (Parallel after VPC)
✅ **Correct placement**
- Both stacks take VPC ID as a parameter (even though they don't strictly need it)
- Independent of each other, so correctly parallelized
- Must wait for VPC to complete

### Wave 3: S3 Bucket + RAM Share (Parallel)
⚠️ **RAM Share could move earlier**

**S3 Bucket**: Correctly placed
- Needs IAM roles from Wave 2 (passed as parameter to enable_blueprints)
- Cannot move earlier

**RAM Share**: Could potentially move to Wave 1 or Wave 2
- Has NO dependencies on VPC, IAM roles, or S3 bucket
- Only needs Domain ID and account IDs (from config/event)
- Currently in Wave 3 because it's parallelized with S3 bucket
- **However**: Moving it earlier wouldn't save time because:
  - RAM share creation is fast (~10 seconds)
  - The bottleneck is RAM share propagation (15+ seconds wait)
  - Blueprint enablement (Wave 4) doesn't need RAM share
  - Only Domain Visibility (Wave 6) needs RAM share

**Conclusion**: RAM share placement is optimal for current architecture

### Wave 4: Blueprint Enablement (After VPC, IAM, S3)
✅ **Correct placement**
- Needs VPC ID and subnet IDs (Wave 1)
- Needs ManageAccessRole and ProvisioningRole ARNs (Wave 2)
- Needs S3 bucket name (Wave 3)
- This is the longest operation (~3 minutes)
- Cannot parallelize because it depends on all previous waves

### Wave 6: Domain Visibility Verification (After RAM Share)
✅ **Correct placement**
- Must wait for RAM share to propagate to DataZone
- Polls DataZone API until domain is accessible
- Cannot move earlier because RAM share needs time to propagate

---

## Optimization Opportunities

### 1. ✅ MAJOR: Move IAM Roles + EventBridge Rules + RAM Share to Wave 1
**Proposal**: Deploy IAM roles, EventBridge rules, and RAM share in parallel with VPC

**Analysis**:
- **IAM roles template**: Only uses `DomainAccountId` and `DomainId` (from config) - NO VPC dependency!
- **EventBridge rules template**: Only uses `CentralEventBusArn` (from config) - NO VPC dependency!
- **RAM share**: Only uses Domain ID and account IDs (from config) - NO VPC dependency!
- The code passes `vpc_result` to these functions but **never uses it**
- All three can run in parallel with VPC deployment

**Current misconception**: 
- Code structure suggests Wave 2 depends on Wave 1
- Reality: `vpc_result` parameter is passed but unused
- This is a **false dependency**

**Net benefit**: 
- Save entire Wave 2 duration (~120 seconds)
- Total time: 8.4 min → 6.4 min (24% improvement!)

**Recommendation**: ✅ **IMPLEMENT THIS - MAJOR OPTIMIZATION**
- Remove `vpc_result` parameter from `deploy_iam_roles()` and `deploy_eventbridge_rules()`
- Move all three operations to Wave 1 (parallel with VPC)
- This is the biggest optimization opportunity

### 2. ❌ Parallelize Blueprint Enablement with S3/RAM
**Proposal**: Start blueprint enablement before S3 bucket is ready

**Analysis**:
- Blueprint enablement needs S3 bucket name as parameter
- Cannot start until S3 bucket exists
- **Blocker**: Hard dependency

**Recommendation**: ❌ Not possible
- Hard dependency on S3 bucket

### 3. ❌ Overlap RAM Share Propagation with Blueprint Enablement
**Proposal**: Start RAM share creation earlier so propagation happens during blueprint enablement

**Current flow**:
```
Wave 3: Create RAM share (10s) + Wait for propagation (15s) = 25s
Wave 4: Blueprint enablement (180s)
Wave 6: Verify domain visibility (polling)
Total: 25s + 180s + polling = ~205s + polling
```

**Optimized flow**:
```
Wave 2: Create RAM share (10s) - parallel with IAM roles
Wave 3: S3 bucket (10s)
Wave 4: Blueprint enablement (180s) - RAM share propagates during this time
Wave 6: Verify domain visibility (minimal polling needed)
Total: 10s + 10s + 180s + minimal polling = ~200s
```

**Analysis**:
- RAM share creation (10s) overlaps with IAM roles (120s)
- RAM share propagation (15s) overlaps with blueprint enablement (180s)
- By the time Wave 6 starts, RAM share is already propagated
- **Net benefit**: ~20 seconds saved (RAM share creation + propagation time)

**Implementation**:
- Move RAM share creation to Wave 2 (parallel with IAM roles)
- RAM share has no dependencies, so this is safe
- Domain Visibility (Wave 6) will have minimal wait time

**Recommendation**: ❌ Not needed with optimization #1
- If IAM roles, EventBridge, and RAM share all move to Wave 1, this optimization is redundant
- The major time savings come from eliminating Wave 2 entirely

---

## Recommended Wave Structure (Optimized)

### Wave 1: VPC + IAM + EventBridge + RAM + Domain Visibility + S3 Bucket (parallel, ~2.5 min)
- **VPC**: VPC with 3 private subnets (~150s)
- **IAM roles**: ManageAccessRole, ProvisioningRole (~120s)
- **EventBridge rules**: Forward CloudFormation events (~30s)
- **S3 bucket**: Blueprint artifacts bucket (~10s)
- **RAM share + Domain Visibility**: 
  - Create RAM share (~10s)
  - Wait for RAM share to become ACTIVE (~10s)
  - Wait for domain resource to be added to share (~15s)
  - Verify domain is accessible via DataZone API (~10s polling)
  - **Total**: ~45s
- **All run in parallel**: Total wave time = max(150s, 120s, 30s, 10s, 45s) = 150s
- **CRITICAL**: Wave does NOT complete until domain is visible in project account
- **Benefit**: Eliminates Wave 2 and Wave 3 entirely!

### Wave 2: Blueprint Enablement (~3 min)
- 17 DataZone EnvironmentBlueprintConfiguration resources
- Policy grants
- **Dependencies**: Needs VPC, IAM roles, S3 bucket from Wave 1
- **CRITICAL**: Domain MUST be visible before this wave (guaranteed by Wave 1)
- **Note**: All DataZone API calls will succeed because domain visibility was verified in Wave 1

---

## Time Savings Calculation

### Current Structure
```
Wave 1: VPC                    = 150s
Wave 2: IAM + EventBridge      = 120s (parallel)
Wave 3: S3 + RAM Share         = 25s (parallel, includes RAM propagation wait)
Wave 4: Blueprint Enablement   = 180s
Wave 6: Domain Visibility      = 30s (polling)
Total: 150 + 120 + 25 + 180 + 30 = 505 seconds (~8.4 minutes)
```

### Optimized Structure
```
Wave 1: VPC + IAM + EventBridge + S3 + RAM + Domain Visibility = 150s (all parallel, VPC is longest)
        - VPC: 150s
        - IAM roles: 120s
        - EventBridge: 30s
        - S3 bucket: 10s
        - RAM share creation: 10s
        - RAM share ACTIVE wait: 10s
        - Domain resource added: 15s
        - Domain visibility polling: 10s
        - Total RAM+Visibility: 45s (overlaps with VPC 150s)
Wave 2: Blueprint Enablement   = 180s
Total: 150 + 180 = 330 seconds (~5.5 minutes)
```

**Time saved**: 175 seconds (~35% improvement!)
**Wave count reduced**: 6 waves → 2 waves
**Critical fix**: Domain visibility verified BEFORE any DataZone API calls

---

## Why We Can't Reduce Wave Count Further

### ✅ Can Merge Wave 2 into Wave 1 (Current Wave 2)
- **Discovery**: IAM roles and EventBridge rules DON'T actually use VPC ID
- The code passes `vpc_result` but never uses it - **false dependency**
- All can run in parallel with VPC
- **Result**: Eliminate Wave 2 entirely

### ✅ Can Merge Wave 3 into Wave 1 (Current Wave 3 - S3 Bucket)
- **Discovery**: S3 bucket creation DON'T actually use IAM roles
- The code passes `iam_result` but never uses it - **false dependency**
- Only needs account ID and region (from config)
- Can run in parallel with VPC
- **Result**: Eliminate Wave 3 entirely

### ✅ Domain Visibility MUST be in Wave 1 (with RAM Share)
- **Critical**: Blueprint enablement calls DataZone APIs
- DataZone APIs will fail if domain is not visible in project account
- Domain visibility is a **prerequisite**, not a post-check
- Wave 1 does NOT complete until domain is verified accessible
- **Result**: Prevents DataZone API failures in Wave 2

### Can't Merge Wave 1 and Wave 2 (Blueprint Enablement)
- Blueprint enablement needs VPC ID, IAM role ARNs, and S3 bucket name
- These are **real dependencies** - the CloudFormation template uses them as parameters
- **Blocker**: Hard dependency on outputs from Wave 1

---

## Conclusion

The current wave structure has **three false dependencies** that can be eliminated:

1. ✅ **FALSE DEPENDENCY: IAM roles and EventBridge rules don't need VPC**
   - Code passes `vpc_result` but never uses it
   - Can run in parallel with VPC deployment
   - **Saves 120 seconds**

2. ✅ **FALSE DEPENDENCY: S3 bucket doesn't need IAM roles**
   - Code passes `iam_result` but never uses it
   - Only needs account ID and region from config
   - Can run in parallel with VPC deployment
   - **Saves additional 10 seconds**

3. ✅ **CRITICAL FIX: Domain visibility must be in Wave 1 (with RAM Share)**
   - Domain visibility is a **prerequisite** for blueprint enablement, not a post-check
   - Blueprint enablement calls DataZone APIs which fail if domain not visible
   - Wave 1 must NOT complete until domain is verified accessible
   - **Prevents DataZone API failures**
   - **Saves additional 45 seconds** (no separate wave needed)

4. ✅ **Only real dependency: Blueprint enablement needs Wave 1 outputs**
   - Blueprint template uses VPC ID, IAM role ARNs, and S3 bucket name as parameters
   - This is a **real dependency** that cannot be eliminated

The architecture currently achieves **17% time savings** compared to sequential deployment (10-12 minutes → 8.4 minutes). With these optimizations, it would achieve **45% time savings** (10-12 minutes → 5.5 minutes).

**Final structure**: 2 waves instead of 6 waves, reducing setup time from 8.4 minutes to 5.5 minutes.

---

## Implementation Notes

To implement these optimizations:

### 1. Merge Everything into Wave 1 (except Blueprint Enablement)
- Remove `vpc_result` parameter from `deploy_iam_roles()` and `deploy_eventbridge_rules()`
- Remove `iam_result` parameter from `create_s3_bucket()`
- Update `execute_wave_parallel()` in Wave 1 to include all operations:
  ```python
  # Wave 1: Foundation + Domain Access (parallel, ~150s)
  vpc_result, iam_result, eb_result, s3_result, ram_result = execute_wave_parallel([
      lambda: deploy_vpc(account_id, config),
      lambda: deploy_iam_roles(account_id, config),
      lambda: deploy_eventbridge_rules(account_id, config),
      lambda: create_s3_bucket(account_id, config),
      lambda: create_ram_share_and_verify_domain(account_id, config)
  ])
  ```

### 2. Combine RAM Share with Domain Visibility
- Create new function `create_ram_share_and_verify_domain()` that:
  1. Creates RAM share
  2. Waits for RAM share to become ACTIVE
  3. Waits for domain resource to be added to share
  4. Verifies domain is accessible via DataZone GetDomain API
  5. Returns only when domain is confirmed visible
- This ensures Wave 1 doesn't complete until domain is ready for DataZone API calls

### 3. Update Wave Structure
```python
# Wave 1: Foundation + Domain Access (parallel, ~150s)
vpc_result, iam_result, eb_result, s3_result, ram_result = execute_wave_parallel([...])

# Wave 2: Blueprint Enablement (~180s)
bp_result = enable_blueprints(account_id, config, vpc_result, iam_result, s3_result)
```

### 4. Update Progress Tracking
- Update DynamoDB progress tracking to reflect 2-wave structure
- Update CloudWatch metrics and dashboards
- Update Architecture.md documentation

**Risk**: Low
- IAM/EventBridge have no VPC dependency (verified in templates)
- S3 bucket has no IAM dependency (verified in code)
- Domain visibility is already required for blueprint enablement (just moving the check earlier)

**Testing**: 
- Verify all operations in Wave 1 complete successfully in parallel
- Verify domain is accessible before blueprint enablement starts
- Verify blueprint enablement succeeds without domain visibility errors
