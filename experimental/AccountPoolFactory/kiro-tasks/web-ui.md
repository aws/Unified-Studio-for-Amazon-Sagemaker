# Web UI — Project Creator & Pool Management Console

## Status

| Field | Value |
|-------|-------|
| Status | 🔵 In Design |
| Last Updated | — |
| Current Phase | — |
| Current Task | — |
| Blocked By | — |

### Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Auth module (IDC OIDC + AssumeRoleWithWebIdentity) | ⬜ Not started |
| 2 | AWS client module (SDK v3 from CDN) | ⬜ Not started |
| 3 | Project Creator UI | ⬜ Not started |
| 4 | Pool Management Console UI | ⬜ Not started |
| 5 | Infrastructure (S3, CloudFront, IAM role) | ⬜ Not started |
| 6 | Deploy scripts | ⬜ Not started |
| 7 | Testing | ⬜ Not started |

> Status legend: ⬜ Not started · 🔄 In progress · ✅ Done · ❌ Blocked

---

## Goal

Two serverless web UIs hosted on S3 + CloudFront. **No Lambda, no API Gateway, no Cognito.** The browser authenticates with IDC, gets temporary IAM credentials via STS `AssumeRoleWithWebIdentity`, and calls AWS services directly using the AWS SDK v3 loaded from CDN.

**UI 1 — Project Creator**: replaces `tests/setup/create-test-project.sh`. A user fills in a form, picks a project profile, and creates a DataZone project. The UI handles the multi-step flow (resolve pool account → build environment configs → call DataZone CreateProject) that the script currently does.

**UI 2 — Pool Management Console**: replaces ad-hoc DynamoDB queries and `check-pool-status.sh`. Gives the domain admin a live view of pool health, account states, and the ability to trigger operations and edit pool configuration.

---

## System Context

### Key AWS Resources (already exist)

| Resource | Value |
|----------|-------|
| Domain Account | 994753223772 |
| DataZone Domain ID | dzd-4h7jbz76qckoh5 |
| Root Domain Unit ID | bsmdc8e4dwye5l |
| Region | us-east-2 |
| DynamoDB Table | `AccountPoolFactory-AccountState` (PK: accountId, SK: timestamp) |
| DynamoDB GSI | `StateIndex` (PK: state, SK: createdDate) |
| DynamoDB GSI | `ProjectIndex` (PK: projectId) |
| Lambda: PoolManager | triggers replenishment, deletes failed accounts |
| Lambda: AccountReconciler | hourly health check |
| Lambda: AccountRecycler | fixes FAILED/ORPHANED accounts |

### DynamoDB Account Record Shape

```json
{
  "accountId": "123456789012",
  "timestamp": 1234567890,
  "state": "AVAILABLE",
  "poolName": "analytics",
  "accountName": "smus-analytics-a3f8b2c1",
  "accountEmail": "analytics-pool+a3f8b2c1@example.com",
  "projectId": "proj-xxx",
  "deployedStackSets": ["SMUS-AccountPoolFactory-DomainAccess", ...],
  "createdDate": "2025-01-01T00:00:00Z",
  "setupCompleteDate": "2025-01-01T00:10:00Z",
  "assignedDate": "2025-01-01T01:00:00Z",
  "retryCount": 0,
  "errorMessage": "",
  "reconciliationNote": ""
}
```

### Relevant Files

- `tests/setup/create-test-project.sh` — full project creation flow the UI replicates
- `scripts/utils/check-pool-status.sh` — pool status queries the console replaces
- `src/pool-manager/lambda_function.py` — `force_replenishment`, `delete_failed_account` actions
- `src/account-reconciler/lambda_function.py` — `dryRun`, `autoRecycle`, `autoReplenish` actions
- `src/account-recycler/lambda_function.py` — `recycleAll` action

---

## Technology Stack

**No build pipeline. No npm install. Files are edited and uploaded directly.**

| Layer | Choice | Why |
|-------|--------|-----|
| HTML/CSS/JS | Vanilla ES modules | No build step, works directly from S3 |
| CSS | [Pico CSS](https://picocss.com/) v2 via CDN | Single `<link>`, classless semantic HTML, modern look |
| AWS SDK | AWS SDK v3 browser bundles via CDN (unpkg) | Browser calls AWS directly — no Lambda proxy needed |
| Auth | IDC OIDC → STS `AssumeRoleWithWebIdentity` | Same identity as SMUS, no Cognito needed |

**File structure:**
```
ui/
  auth.js           # IDC OIDC PKCE + AssumeRoleWithWebIdentity (~80 lines)
  aws.js            # AWS SDK client factory (creates clients from temp creds)
  config.js         # generated at deploy time from CF outputs
  mock/             # local dev only (mock-server.py + mock data)
  project-creator/
    index.html
    app.js
    style.css
  pool-console/
    index.html
    app.js
    style.css
```

**SDK CDN tags (per HTML file):**
```html
<script src="https://unpkg.com/@aws-sdk/client-sts/dist/cjs/index.js"></script>
<script src="https://unpkg.com/@aws-sdk/client-dynamodb/dist/cjs/index.js"></script>
<script src="https://unpkg.com/@aws-sdk/client-datazone/dist/cjs/index.js"></script>
<script src="https://unpkg.com/@aws-sdk/client-ssm/dist/cjs/index.js"></script>
<script src="https://unpkg.com/@aws-sdk/client-lambda/dist/cjs/index.js"></script>
<script src="https://unpkg.com/@aws-sdk/client-identitystore/dist/cjs/index.js"></script>
```

---

## Architecture

```
Browser
  │
  ├── S3 + CloudFront  (static HTML/CSS/JS + SDK from CDN)
  │
  ├── IDC OIDC (PKCE) → STS AssumeRoleWithWebIdentity → temp IAM creds
  │
  └── AWS SDK v3 (browser) → direct AWS API calls
        ├── DynamoDB       pool console: query account state
        ├── SSM            pool console: read/write pool config
        ├── Lambda invoke  pool console: PoolManager, Reconciler, Recycler
        ├── DataZone       project creator: list profiles, create project, poll status
        └── IdentityStore  project creator: search IDC users/groups
```

### Authentication Flow

1. User opens UI → `auth.js` checks sessionStorage for valid credentials
2. If none: redirect to IDC OIDC authorization endpoint (PKCE)
3. IDC redirects back with auth code → exchange for ID token
4. Call `sts:AssumeRoleWithWebIdentity` with ID token → get `AccessKeyId` + `SecretAccessKey` + `SessionToken`
5. Store in sessionStorage (1 hour TTL, refreshed automatically)
6. `aws.js` creates all SDK clients with these credentials

### IAM Role — `AccountPoolFactory-UIRole`

One role for both UIs. Trust policy trusts the IDC OIDC provider.

Permissions:
- `dynamodb:Query`, `dynamodb:Scan`, `dynamodb:GetItem` on AccountState table + all GSIs
- `ssm:GetParametersByPath`, `ssm:PutParameter` on `/AccountPoolFactory/Pools/*`
- `lambda:InvokeFunction` on PoolManager, AccountReconciler, AccountRecycler
- `datazone:ListProjectProfiles`, `datazone:GetProjectProfile`, `datazone:ListAccountPools`, `datazone:ListAccountsInAccountPool`, `datazone:CreateProject`, `datazone:GetProject`, `datazone:ListEnvironments`
- `identitystore:ListUsers`, `identitystore:ListGroups`

Role must also be added as a DataZone domain member (CONTRIBUTOR) so it can create projects.

### `config.js` (generated at deploy time)

```js
export const CONFIG = {
  region: 'us-east-2',
  domainId: 'dzd-4h7jbz76qckoh5',
  portalUrl: 'https://dzd-4h7jbz76qckoh5.datazone.us-east-2.on.aws',
  dynamoTable: 'AccountPoolFactory-AccountState',
  uiRoleArn: 'arn:aws:iam::994753223772:role/AccountPoolFactory-UIRole',
  idcIssuerUrl: 'https://identitycenter.amazonaws.com/ssoins-xxxxxxxx',
  idcClientId: 'xxxxxxxx',
  identityStoreId: 'd-xxxxxxxxxx',
  mock: false,
};
```

In mock mode (local dev), `mock-server.py` serves this file with `mock: true` and a local API URL.

---

## UI 1 — Project Creator

### Screens

**1. Create Project form**
- Project name (full-width text input)
- Region (dropdown — populated from selected profile's `allowedRegions`)
- Project owner (searchable — calls `identitystore:ListUsers` + `identitystore:ListGroups`, shows USER/GROUP badge)
- Project profile (dropdown — only pool-backed profiles from `datazone:ListProjectProfiles`)
- Submit — disabled until all fields filled

**2. Progress view** (auto-refreshes every 3s)
- Step indicators: Resolving account → Creating project → Deploying environments
- Live environment status list
- On success: "Open in SageMaker Unified Studio" button → navigates to `{portalUrl}/projects/{projectId}`

---

## UI 2 — Pool Management Console

### Screens

**1. Dashboard** — pool capacity cards per pool, force replenish + reconcile buttons, auto-refresh 30s

**2. Accounts** — table with per-column filters (account ID/name, pool, state, project); all filtering via API; click row → detail panel

**3. Account Detail panel** — all DynamoDB fields, deployed StackSets, contextual actions (recycle, remove, copy ID)

**4. Configuration** — per-pool editable form: min size, target size, max concurrent setups, reclaim strategy; Save writes to SSM immediately

**5. Operations log** — last 20 actions stored in localStorage

---

## Infrastructure Changes Required

### New resource: `AccountPoolFactory-UIRole`

Add to `01-infrastructure.yaml`:
- IAM role with trust policy for IDC OIDC provider (`AssumeRoleWithWebIdentity`)
- Permissions as listed above
- Output: `UIRoleArn`

### New resource: S3 UI bucket + CloudFront

Add to `01-infrastructure.yaml`:
- S3 bucket: `accountpoolfactory-ui-{account-id}`, private, CloudFront OAC
- CloudFront distribution, HTTPS only, two path behaviors
- Output: `ProjectCreatorUrl`, `PoolConsoleUrl`

### Existing resource change: DynamoDB `AccountStateTable`

Add `PoolIndex` GSI (PK: `poolName`, SK: `state`) — required for per-pool queries. Add `poolName` to `AttributeDefinitions`. Non-breaking, in-place update.

### One-time manual step: IDC OIDC application

Register an OIDC application in IDC pointing at the CloudFront URL as redirect URI. This gives you the `idcClientId` and `idcIssuerUrl` for `config.js`. Done once by the domain admin.

**Nothing else changes** — no existing Lambdas, no EventBridge, no SNS, no existing roles.

---

## Tasks

### Phase 1: Auth Module

- [ ] 1.1 Create `ui/auth.js` — IDC OIDC PKCE flow:
  - `login()`: generate code verifier + challenge, redirect to IDC authorization endpoint
  - `handleCallback()`: exchange auth code for ID token
  - `getCredentials()`: call `sts:AssumeRoleWithWebIdentity` with ID token, cache in sessionStorage
  - `isAuthenticated()`: check sessionStorage for non-expired credentials
  - Mock mode: return fake credentials immediately, skip IDC redirect

### Phase 2: AWS Client Module

- [ ] 2.1 Create `ui/aws.js` — SDK client factory:
  - `getClients()`: returns `{ dynamo, datazone, ssm, lambda, identityStore }` initialized with credentials from `auth.js`
  - Handles credential refresh when TTL < 5 minutes
  - Mock mode: returns mock implementations that call `fetch('/api/...')` instead

### Phase 3: Project Creator UI

- [ ] 3.1 Update `ui/project-creator/index.html` — add SDK CDN script tags
- [ ] 3.2 Update `ui/project-creator/app.js` — replace `fetch('/api/...')` calls with direct AWS SDK calls:
  - `datazone:ListProjectProfiles` → filter for pool-backed profiles → populate dropdown
  - `identitystore:ListUsers` + `identitystore:ListGroups` → owner search
  - `datazone:ListAccountPools` + `datazone:ListAccountsInAccountPool` → resolve account
  - `datazone:GetProjectProfile` → build userParameters
  - `datazone:CreateProject` → create
  - `datazone:GetProject` → poll status

### Phase 4: Pool Management Console UI

- [ ] 4.1 Update `ui/pool-console/index.html` — add SDK CDN script tags
- [ ] 4.2 Update `ui/pool-console/app.js` — replace `fetch('/api/...')` calls with direct AWS SDK calls:
  - `dynamodb:Query` on StateIndex GSI → dashboard counts per pool
  - `dynamodb:Query` on PoolIndex GSI + filters → accounts table
  - `dynamodb:GetItem` → account detail
  - `ssm:GetParametersByPath` on `/AccountPoolFactory/Pools/` → config view
  - `ssm:PutParameter` → save config
  - `lambda:InvokeFunction` on PoolManager → replenish, delete failed
  - `lambda:InvokeFunction` on AccountReconciler → reconcile
  - `lambda:InvokeFunction` on AccountRecycler → recycle account

### Phase 5: Infrastructure

- [ ] 5.1 Add `AccountPoolFactory-UIRole` to `01-infrastructure.yaml` with IDC OIDC trust + permissions
- [ ] 5.2 Add S3 UI bucket + CloudFront to `01-infrastructure.yaml`
- [ ] 5.3 Add `PoolIndex` GSI to `AccountStateTable` in `01-infrastructure.yaml`
- [ ] 5.4 Add deploy script step to register `UIRole` as DataZone domain member (CONTRIBUTOR)

### Phase 6: Deploy Scripts

- [ ] 6.1 Create `scripts/02-domain-account/deploy/04-deploy-ui.sh`:
  - Generate `ui/config.js` from CF stack outputs (UIRoleArn, IDC config, domain ID, etc.)
  - `aws s3 sync ui/ s3://{bucket}/` (excludes `mock/`)
  - CloudFront invalidation
  - Print URLs

### Phase 7: Testing

- [ ] 7.1 Open Project Creator, sign in via IDC, verify profile dropdown populates from DataZone
- [ ] 7.2 Create a project, verify COMPLETED status and "Open in SMUS" button works
- [ ] 7.3 Open Pool Console, verify dashboard counts match DynamoDB
- [ ] 7.4 Filter accounts table, verify API-side filtering works
- [ ] 7.5 Edit pool config, verify SSM parameter is updated
- [ ] 7.6 Trigger replenishment, verify PoolManager Lambda is invoked
- [ ] 7.7 Verify unauthenticated access redirects to IDC login

---

## Open Questions

- **Q1**: Should the Project Creator derive the pool from the selected profile automatically, or let the user pick? Suggest: derive from profile → pool SSM mapping.
- **Q2**: IDC OIDC application registration — can this be automated via CloudFormation or does it require manual console steps? Likely manual for now.
