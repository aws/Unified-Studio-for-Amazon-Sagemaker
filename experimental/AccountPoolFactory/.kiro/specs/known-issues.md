# Known Issues

## 1. Blueprint authorization failure when creating project from pool account

**Status:** Open — needs investigation  
**Observed:** 2026-03-08 during end-to-end testing of move-lambda-to-domain-account

### Symptom
Running `.test-create-from-pool-IDC.py` — project creates successfully but environment deployment fails immediately:
```
Tooling: [403] Caller is not authorized to create environment using blueprintId 3owsbi7jjppvc9
```
`projectStatus=ACTIVE`, `deploymentStatus=FAILED_DEPLOYMENT`

### Impact
- No `DataZone-Env-*` CF stacks created in project account
- No EventBridge `CREATE_IN_PROGRESS` events fire → account never transitions to ASSIGNED

### Context
- Domain: `dzd-4h7jbz76qckoh5`
- Project profile: `5riu03k7l71zc9` (All Capabilities - Account Pool)
- Blueprint ID: `3owsbi7jjppvc9` (Tooling)
- Pool account: `050366487338`
- Region: `us-east-2`

### Likely cause
Blueprint not enabled/authorized for the pool account, or project profile's Tooling environment config needs explicit cross-account blueprint authorization.

### To investigate
1. Check if blueprint `3owsbi7jjppvc9` is enabled in pool account via DataZone console
2. Check if SetupOrchestrator's blueprint enablement step ran correctly on this account
3. Compare with a working non-pool project profile
