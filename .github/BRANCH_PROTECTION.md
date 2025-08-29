# Branch Protection Setup

To ensure all unit tests pass before PRs can be merged, configure the following branch protection rules in GitHub:

## Required Settings

1. **Go to**: Repository Settings → Branches → Add rule
2. **Branch name pattern**: `main` (or `master`)
3. **Enable**: 
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
4. **Required status checks**:
   - ✅ `unit-tests` (from PR Unit Tests workflow)
5. **Additional recommended settings**:
   - ✅ Restrict pushes that create files larger than 100MB
   - ✅ Require conversation resolution before merging

## GitHub CLI Setup (Alternative)

```bash
# Enable branch protection with required unit tests
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["unit-tests"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field restrictions=null
```

## Workflow Details

The `pr-tests.yml` workflow will:
- ✅ Run on every PR to main/master
- ✅ Execute unit tests only (fast feedback)
- ✅ Block merge if any unit tests fail
- ✅ Upload test artifacts for debugging
- ✅ Support Python 3.12

Integration tests are not required for PR merge to avoid AWS dependency issues in CI.
