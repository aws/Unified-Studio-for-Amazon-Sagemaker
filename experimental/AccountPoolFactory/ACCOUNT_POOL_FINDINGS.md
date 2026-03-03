# Account Pool Investigation Findings

## Date: March 2, 2026

## Critical Discovery: ON_CREATE Does NOT Work with Account Pools

### Issue
ON_CREATE environments are NOT being created automatically when using account pools with MANUAL resolution strategy.

### Test Setup
- Domain ID: dzd-4igt64u5j25ko9
- Account Pool ID: d47walsa85zkx5
- Lambda: AccountProvider-dzd-4igt64u5j25ko9 (deployed and working)
- Region: us-east-2

## Profile Configuration Tests

### Test 1: Four Blueprints as ON_CREATE
- **Profile ID**: 3q3bu487vip8a1 (initial configuration)
- **Test Project**: 4own4h2510q9wp
- **ON_CREATE** (4): Tooling, Lakehouse Database, Lakehouse Catalog, RedshiftServerless
- **ON_DEMAND** (4): Workflows, MLExperiments, EMR on EC2, EMRServerless
- **Result**: ❌ 0 environments created, Lambda NOT invoked

### Test 2: Only Tooling as ON_CREATE
- **Profile ID**: 3q3bu487vip8a1 (updated configuration)
- **Test Project**: 62aerryv7mwq3t
- **ON_CREATE** (1): Tooling only
- **ON_DEMAND** (7): All others
- **Result**: ❌ 0 environments created, Lambda NOT invoked

## Observations

### 1. Project Creation Behavior
- Projects created successfully with status ACTIVE in both tests
- **0 environments created** despite ON_CREATE configuration
- Lambda was NEVER invoked (no CloudWatch logs in either test)
- Project members added successfully (PROJECT_OWNER and PROJECT_CONTRIBUTOR)
- Profile updates applied successfully but behavior unchanged

### 2. Lambda Testing
- ✅ Manual Lambda test works perfectly
- ✅ Returns correct account: 004878717744
- ✅ Comprehensive logging with emojis and timestamps
- ✅ CloudWatch metrics published
- ✅ Lambda has correct permissions and is properly configured in account pool

### 3. API Model Discovery
Examined DataZone API model at:
`/Users/amirbo/code/smus-cicd/experimental/SMUS-CICD-pipeline-cli/src/smus_cicd/resources/datazone-internal-2018-05-10.json`

**Key Finding**: `ResolutionStrategy` enum has only ONE value:
```json
"ResolutionStrategy": {
  "type": "string",
  "enum": ["MANUAL"]
}
```

This confirms that MANUAL is the ONLY valid resolution strategy for custom account pool handlers.

## Root Cause Analysis

**ON_CREATE does NOT work with account pools using MANUAL resolution strategy.**

The term "MANUAL" likely means:
- Environments must be created manually by users (not automatically)
- Lambda is only invoked when user explicitly creates an environment
- ON_CREATE deployment mode is ignored when using account pools
- Account pools fundamentally change the environment creation workflow

## Evidence
1. ✅ No environments created despite ON_CREATE configuration (tested with 4 and 1 blueprint)
2. ✅ Lambda never invoked during project creation in either test
3. ✅ API model shows MANUAL as only option for custom account pool handlers
4. ✅ AWS documentation doesn't mention automatic environment creation with account pools
5. ✅ Profile updates applied successfully but behavior unchanged
6. ✅ Lambda works perfectly when tested manually

## Conclusion

**Account pools with MANUAL resolution strategy are incompatible with ON_CREATE automatic environment creation.**

When using account pools:
- All environments must be created manually by users
- ON_CREATE deployment mode is effectively ignored
- Lambda is only invoked during manual environment creation
- This is a fundamental limitation of the account pool architecture

## Test Accounts Created
- Account 100: 004878717744 (amirbo+100@amazon.com) - TestAccount-OrgsApi-100
- Account 101: 400398152132 (amirbo+101@amazon.com) - TestAccount-OrgsApi-101

## Configuration Files
- `config.yaml`: Main configuration
- `account-pool-details.json`: Account pool configuration (ID: d47walsa85zkx5)
- `project-profile-details.json`: Project profile summary
- `project-profile-full-details.json`: Complete profile configuration (ID: 3q3bu487vip8a1)
- `test-project-details.json`: Test project information (ID: 62aerryv7mwq3t)

## Next Steps
1. ✅ Confirmed: ON_CREATE does NOT work with account pools (tested twice)
2. ⏭️ Test manual environment creation through API
3. ⏭️ Verify Lambda is invoked during manual environment creation
4. ⏭️ Update requirements to reflect manual environment creation workflow
5. ⏭️ Document this limitation in design and testing guide
