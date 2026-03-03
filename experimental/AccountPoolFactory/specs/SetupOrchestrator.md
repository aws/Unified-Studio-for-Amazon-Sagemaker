# Setup Orchestrator Lambda - Specification

## Overview

The Setup Orchestrator Lambda automates the complete setup of new AWS accounts when they are added to the DataZone account pool. It coordinates deployment of infrastructure, IAM roles, DataZone blueprints, and policy grants to make accounts ready for project creation.

## Context

### What We Know
- Account creation takes < 1 minute (Organizations API)
- Complete account setup takes 10-12 minutes
- Setup includes: VPC, IAM roles, S3 bucket, 17 blueprints, 17 policy grants, RAM share
- Manual setup is working end-to-end (tested with account 004878717744)
- Project creation with environment deployment is successful

### Current State
- Manual scripts exist for each setup step
- Scripts are tested and working
- No automation - accounts must be manually configured
- No state tracking or error recovery

## Requirements

### Functional Requirements

#### FR1: Automated Account Setup
The Lambda must automatically set up new accounts when they are added to the pool.

**Trigger**: EventBridge event from account creation
**Input**: Account ID, Region, OU ID
**Output**: Fully configured account ready for DataZone projects

#### FR2: Complete Infrastructure Deployment
The Lambda must deploy all required infrastructure:
- VPC with 3 private subnets across 3 AZs
- IAM roles (ManageAccess + Provisioning)
- S3 bucket for blueprint artifacts
- DataZone blueprint enablement (17 blueprints)
- Policy grants (17 grants in project account)
- RAM share for domain access

#### FR3: State Management
The Lambda must track setup progress to enable:
- Resume from last successful step if timeout occurs
- Query account setup status via API
- Debugging failed setups
- Audit trail of setup activities

#### FR4: Error Handling
The Lambda must handle failures gracefully:
- Retry transient failures with exponential backoff
- Mark accounts as FAILED after max retries
- Send SNS notifications for manual intervention
- Log detailed error information for debugging

#### FR5: Verification
The Lambda must verify each setup step:
- CloudFormation stack status = CREATE_COMPLETE
- Domain visible in project account
- Blueprints enabled successfully
- Policy grants created

### Non-Functional Requirements

#### NFR1: Performance
- Complete setup within 15 minutes (Lambda timeout limit)
- Minimize API calls to avoid throttling
- Use parallel execution where possible

#### NFR2: Reliability
- Idempotent operations (safe to retry)
- Atomic state updates
- No partial configurations left behind

#### NFR3: Observability
- CloudWatch metrics for success/failure rates
- Detailed logging with timestamps
- X-Ray tracing for debugging
- CloudWatch dashboard for monitoring

#### NFR4: Security
- Least privilege IAM permissions
- Assume role in target accounts
- No hardcoded credentials
- Audit logging enabled

## Design Questions

### Q1: Deployment Method
**Question**: Should we use StackSets (centralized) or direct CloudFormation in each account (Lambda assumes role)?

**Options**:
A. **StackSets** - Lambda creates StackSet instances
   - Pros: Centralized management, approved templates, drift detection
   - Cons: Additional API calls, StackSet overhead, harder to customize per account

B. **Direct CloudFormation** - Lambda assumes role and deploys stacks
   - Pros: Faster, simpler, easier to customize, direct control
   - Cons: No centralized drift detection, templates not pre-approved

**Recommendation**: ?

### Q2: State Management
**Question**: Should we track setup progress in DynamoDB?

**Options**:
A. **DynamoDB State Table**
   - Schema: AccountId (PK), SetupStep, Status, Timestamp, ErrorMessage
   - Enables resume, querying, debugging
   - Additional cost and complexity

B. **CloudWatch Logs Only**
   - Simpler, no additional infrastructure
   - Harder to query, no resume capability

**Recommendation**: ?

### Q3: Error Handling Strategy
**Question**: What should happen if setup fails?

**Options**:
A. **Mark FAILED + Alert**
   - Set account status to FAILED
   - Send SNS notification
   - Require manual intervention

B. **Automatic Retry**
   - Retry setup automatically (e.g., 3 attempts)
   - Exponential backoff between retries
   - Mark FAILED only after max retries

C. **Remove from Pool**
   - Remove failed account from pool
   - Create new account to replace it
   - Most aggressive approach

**Recommendation**: ?

### Q4: Monitoring & Alerting
**Question**: What metrics and alarms do we need?

**Metrics to Track**:
- Setup success/failure rate
- Setup duration (p50, p99)
- Pool size (available vs total)
- Failed accounts count
- Step-level success rates

**Alarms**:
- Setup failure rate > threshold
- Pool size below minimum
- Setup duration > threshold
- Failed accounts > threshold

**Recommendation**: Which metrics/alarms are most important?

### Q5: Execution Model
**Question**: Should we use Lambda or Step Functions?

**Options**:
A. **Single Lambda Function**
   - Simpler, fewer moving parts
   - 15-minute timeout limit
   - Harder to visualize workflow

B. **Step Functions State Machine**
   - Visual workflow, longer execution time
   - Built-in retry and error handling
   - More complex, higher cost

**Recommendation**: ?

### Q6: Parallel vs Sequential Execution
**Question**: Should we run some steps in parallel?

**Possible Parallelization**:
- VPC deployment + RAM share creation (independent)
- Blueprint enablement + Policy grants (must be sequential)
- IAM roles + S3 bucket (independent)

**Trade-offs**:
- Parallel: Faster, more complex, harder to debug
- Sequential: Slower, simpler, easier to understand

**Recommendation**: ?

### Q7: Rollback Strategy
**Question**: Should we rollback on failure?

**Options**:
A. **No Rollback**
   - Leave partial setup in place
   - Manual cleanup required
   - Simpler implementation

B. **Automatic Rollback**
   - Delete all created resources on failure
   - Clean slate for retry
   - More complex, risk of incomplete cleanup

**Recommendation**: ?

## Implementation Approach

### Phase 1: Core Orchestration
1. Implement Lambda handler
2. Add EventBridge trigger
3. Implement sequential setup steps
4. Add basic error handling

### Phase 2: State Management
1. Create DynamoDB table (if needed)
2. Track setup progress
3. Implement resume logic

### Phase 3: Monitoring
1. Add CloudWatch metrics
2. Create CloudWatch dashboard
3. Configure SNS alerts

### Phase 4: Optimization
1. Add parallel execution (if needed)
2. Optimize API calls
3. Add retry logic

## Success Criteria

- [ ] Account setup completes successfully without manual intervention
- [ ] Setup time < 15 minutes
- [ ] Failed setups trigger alerts
- [ ] Setup status queryable via API or console
- [ ] All 17 blueprints enabled and authorized
- [ ] Projects can create environments immediately after setup

## Open Questions

1. Should we support multiple regions per account?
2. Should we support custom VPC CIDR ranges?
3. Should we support custom blueprint configurations?
4. How do we handle blueprint updates (new blueprints added)?
5. Should we support account removal from pool (cleanup)?

## Next Steps

1. Answer design questions above
2. Create detailed technical design
3. Implement Lambda function
4. Create CloudFormation template for Lambda infrastructure
5. Test with account 101
6. Document operational procedures
