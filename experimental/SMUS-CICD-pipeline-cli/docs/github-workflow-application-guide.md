# Application Admin Guide - SMUS Direct Branch Deployment

← [Workflow Templates](../git-templates/) | [DevOps Guide](github-workflow-devops-guide.md) | [Main README](../README.md)

**Audience:** Application Team Leads, Data Engineers, ML Engineers  
**Purpose:** Set up automated deployment for your SMUS application

---

## Overview

This guide shows you how to set up automated deployment for your SMUS application using the organization's workflow template.

### What You'll Get

- ✅ Automated deployment to test environment
- ✅ Automated testing after deployment
- ✅ Approval-based promotion to production
- ✅ Automatic merge and deployment
- ✅ Complete audit trail

### Prerequisites

- Application code in a GitHub repository
- SMUS application manifest (`manifest.yaml`)
- AWS account access (provided by DevOps)
- GitHub repository admin access

---

## Quick Start (5 Steps)

### Step 1: Copy the Workflow File

```bash
# In your application repository
mkdir -p .github/workflows

# Copy the template (provided by DevOps)
cp /path/to/org-application-workflow.yml .github/workflows/deploy.yml
```

### Step 2: Configure the Workflow

Edit `.github/workflows/deploy.yml`:

```yaml
name: Deploy My Application

on:
  push:
    branches:
      - myapp-test-branch      # Change to your test branch name
      - myapp-prod-branch      # Change to your prod branch name

jobs:
  deploy:
    uses: your-org/workflows/.github/workflows/smus-direct-branch.yml@v1
    with:
      manifest_path: 'manifest.yaml'           # Path to your manifest
      test_branch: 'myapp-test-branch'         # Your test branch
      prod_branch: 'myapp-prod-branch'         # Your prod branch
    secrets:
      AWS_ROLE_ARN_TEST: ${{ secrets.AWS_ROLE_ARN_TEST }}
      AWS_ROLE_ARN_PROD: ${{ secrets.AWS_ROLE_ARN_PROD }}
      TEST_DOMAIN_REGION: ${{ vars.TEST_DOMAIN_REGION }}
      PROD_DOMAIN_REGION: ${{ vars.PROD_DOMAIN_REGION }}
```

### Step 3: Create GitHub Environments

Go to: **Repository Settings → Environments**

**Create `aws-test` environment:**
- Add variable: `TEST_DOMAIN_REGION` = `us-east-1` (or your region)
- Add secret: `AWS_ROLE_ARN_TEST` = (provided by DevOps)
- Deployment branches: Select "Selected branches" → Add your test branch

**Create `aws-prod` environment:**
- Add variable: `PROD_DOMAIN_REGION` = `us-east-1` (or your region)
- Add secret: `AWS_ROLE_ARN_PROD` = (provided by DevOps)
- **Required reviewers:** Add at least 1 reviewer
- Deployment branches: Select "Selected branches" → Add your prod branch

### Step 4: Create Branches

```bash
# Create test branch
git checkout -b myapp-test-branch
git push origin myapp-test-branch

# Create prod branch from test
git checkout -b myapp-prod-branch
git push origin myapp-prod-branch

# Go back to feature branch
git checkout -b feature/initial-setup
```

### Step 5: Deploy!

```bash
# Make changes
git add .
git commit -m "feat: initial setup"
git push origin feature/initial-setup

# Create PR to test branch
gh pr create --base myapp-test-branch --head feature/initial-setup

# Merge PR → Workflow runs automatically!
```

---

## Branch Strategy

### Branch Names

Use descriptive names that include your application:
- `{app-name}-test-branch` - e.g., `etl-pipeline-test-branch`
- `{app-name}-prod-branch` - e.g., `etl-pipeline-prod-branch`

### Branch Flow

```
feature/my-feature
    ↓ (PR + merge)
myapp-test-branch
    ↓ (approval + automatic merge)
myapp-prod-branch
```

### Development Workflow

1. **Develop:** Create feature branch from test
2. **Test:** Create PR to test branch
3. **Deploy to Test:** Merge PR → Automatic deployment
4. **Approve:** Review and approve production deployment
5. **Deploy to Prod:** Automatic merge and deployment

---

## Configuration Reference

### Required Parameters

**`manifest_path`**
- Path to your application manifest
- Example: `'manifest.yaml'` or `'config/app-manifest.yaml'`

**`test_branch`**
- Branch name for test deployments
- Example: `'myapp-test-branch'`

**`prod_branch`**
- Branch name for production deployments
- Example: `'myapp-prod-branch'`

### Required Secrets

**`AWS_ROLE_ARN_TEST`**
- IAM role ARN for test deployments
- Get from DevOps team
- Example: `arn:aws:iam::123456789012:role/GitHubActions-SMUS-Test`

**`AWS_ROLE_ARN_PROD`**
- IAM role ARN for production deployments
- Get from DevOps team
- Example: `arn:aws:iam::987654321098:role/GitHubActions-SMUS-Prod`

### Required Variables

**`TEST_DOMAIN_REGION`**
- AWS region for test domain
- Example: `us-east-1`

**`PROD_DOMAIN_REGION`**
- AWS region for production domain
- Example: `us-east-1`

---

## Daily Usage

### Deploying Changes

```bash
# 1. Create feature branch
git checkout myapp-test-branch
git pull
git checkout -b feature/add-new-workflow

# 2. Make changes
vim src/my_workflow.py
vim manifest.yaml

# 3. Commit and push
git add .
git commit -m "feat: add new workflow"
git push origin feature/add-new-workflow

# 4. Create PR
gh pr create --base myapp-test-branch --head feature/add-new-workflow

# 5. Get PR approved and merge
# Workflow automatically:
#   - Deploys to test
#   - Runs tests
#   - Waits for approval
#   - Merges to prod branch
#   - Deploys to prod
```

### Approving Production Deployment

1. Go to **Actions** tab in GitHub
2. Click on the running workflow
3. Click **Review deployments**
4. Select **aws-prod**
5. Add optional comment
6. Click **Approve and deploy**

### Monitoring Deployments

- **Actions tab:** See all workflow runs
- **Environments:** See deployment history
- **Workflow logs:** Detailed execution logs

---

## Rollback Procedure

If you need to rollback production:

```bash
# 1. Revert the problematic commit on test branch
git checkout myapp-test-branch
git pull
git revert HEAD  # Or specific commit: git revert abc123
git push origin myapp-test-branch

# 2. Workflow automatically:
#    - Deploys reverted code to test
#    - Runs tests
#    - Waits for approval

# 3. Approve deployment
#    - Workflow merges to prod
#    - Deploys reverted code to prod
```

---

## Best Practices

### 1. Branch Naming
- Use descriptive names: `{app}-{stage}-branch`
- Be consistent across your team
- Document your naming convention

### 2. Feature Branches
- Always work on feature branches
- Never push directly to test or prod branches
- Use descriptive feature branch names

### 3. Pull Requests
- Write clear PR descriptions
- Link to related issues/tickets
- Get code review before merging

### 4. Testing
- Test thoroughly in dev environment first
- Ensure tests pass before creating PR
- Monitor test results in workflow

### 5. Approvals
- Review changes before approving prod
- Check test results
- Verify no breaking changes

### 6. Monitoring
- Watch workflow runs
- Check application health after deployment
- Set up alerts for failures

---

## Examples

### Example 1: ETL Pipeline

```yaml
name: Deploy ETL Pipeline

on:
  push:
    branches:
      - etl-pipeline-test-branch
      - etl-pipeline-prod-branch

jobs:
  deploy:
    uses: myorg/workflows/.github/workflows/smus-direct-branch.yml@v1
    with:
      manifest_path: 'etl-manifest.yaml'
      test_branch: 'etl-pipeline-test-branch'
      prod_branch: 'etl-pipeline-prod-branch'
    secrets:
      AWS_ROLE_ARN_TEST: ${{ secrets.AWS_ROLE_ARN_TEST }}
      AWS_ROLE_ARN_PROD: ${{ secrets.AWS_ROLE_ARN_PROD }}
      TEST_DOMAIN_REGION: ${{ vars.TEST_DOMAIN_REGION }}
      PROD_DOMAIN_REGION: ${{ vars.PROD_DOMAIN_REGION }}
```

### Example 2: ML Model

```yaml
name: Deploy ML Model

on:
  push:
    branches:
      - ml-model-test-branch
      - ml-model-prod-branch

jobs:
  deploy:
    uses: myorg/workflows/.github/workflows/smus-direct-branch.yml@v1
    with:
      manifest_path: 'model/manifest.yaml'
      test_branch: 'ml-model-test-branch'
      prod_branch: 'ml-model-prod-branch'
      smus_cli_path: 'tools/smus-cli'  # Custom path
    secrets:
      AWS_ROLE_ARN_TEST: ${{ secrets.AWS_ROLE_ARN_ML_TEST }}
      AWS_ROLE_ARN_PROD: ${{ secrets.AWS_ROLE_ARN_ML_PROD }}
      TEST_DOMAIN_REGION: ${{ vars.TEST_DOMAIN_REGION }}
      PROD_DOMAIN_REGION: ${{ vars.PROD_DOMAIN_REGION }}
```

---

## Getting Help

### Self-Service
1. Check this guide
2. Review workflow logs in Actions tab
3. Check AWS CloudTrail for permission issues

### Contact DevOps
- **Slack:** #smus-deployments
- **Email:** devops@your-org.com
- **Office Hours:** Tuesdays 2-3pm

### Common Questions

**Q: Can I deploy to prod without going through test?**
A: No. Test deployment and tests must pass first (for safety).

**Q: How long does deployment take?**
A: Typically 15-25 minutes (including approval wait time).

**Q: Can multiple people deploy at once?**
A: No. GitHub environment protection queues deployments.

**Q: What if I need to hotfix production?**
A: Create hotfix branch, test it, follow normal flow through test.

---

## Summary

**Setup (one-time):**
1. Copy workflow file
2. Configure parameters
3. Set up GitHub environments
4. Create branches

**Daily usage:**
1. Create feature branch
2. Make changes
3. Create PR to test branch
4. Merge → Auto-deploy to test
5. Approve → Auto-deploy to prod

**That's it!** The workflow handles everything else automatically.


---

## Alternative Deployment Strategies

This guide focuses on **direct branch-based deployment**, but SMUS supports three deployment strategies. Here's when you might use the alternatives:

### Bundle-Based Deployment

**Location:** [`bundle-based/`](../git-templates/bundle-based/)

**What it is:**
Creates a versioned bundle (artifact) that is deployed to all environments. The same bundle goes to test and prod.

**When to use:**
- Your organization requires artifact versioning
- You need instant rollback capability
- Compliance requires deploying exact same artifact everywhere
- You deploy to multiple regions

**How it's different:**
```
Direct Branch:
  Code → Deploy to Test → Deploy to Prod

Bundle-Based:
  Code → Create Bundle → Deploy Bundle to Test → Deploy Same Bundle to Prod
```

**Key benefits:**
- ✅ Instant rollback (redeploy old bundle)
- ✅ Guaranteed same code in all environments
- ✅ Artifact repository for audit trail

**Trade-offs:**
- ❌ Slower (bundle creation step)
- ❌ Requires S3 storage for bundles
- ❌ More complex workflow

### Hybrid Bundle-Branch Deployment

**Location:** [`hybrid-bundle-branch/`](../git-templates/hybrid-bundle-branch/)

**What it is:**
Combines direct deployment for code with bundle deployment for large artifacts (ML models, data files).

**When to use:**
- ML/AI applications with large model files
- Applications with binary artifacts
- Need fast code updates but controlled model deployment
- Models change less frequently than code

**How it's different:**
```
Direct Branch:
  All content deployed directly from git

Hybrid:
  Code → Deploy directly (fast)
  Models → Create bundle → Deploy bundle (versioned)
```

**Example use case:**
```yaml
# Code deployed directly
content:
  git:
    - repository: training-code
      include: [src/]

# Models deployed as bundles
bundles:
  - name: trained-models
    source: s3://ml-models/
    versioning: true
```

**Key benefits:**
- ✅ Fast code deployment
- ✅ Versioned model deployment
- ✅ Independent update paths
- ✅ Pin model versions per environment

**Trade-offs:**
- ❌ More complex setup
- ❌ Requires understanding both approaches
- ❌ More complex manifest

---

## Comparison Table

| Feature | Direct Branch | Bundle-Based | Hybrid |
|---------|---------------|--------------|--------|
| **Deployment Speed** | Fast (~15 min) | Slower (~25 min) | Fast for code |
| **Rollback** | Git revert + redeploy | Instant (redeploy old bundle) | Mixed |
| **Artifacts** | None | Versioned bundles | Versioned models |
| **Storage Required** | None | S3 for bundles | S3 for models |
| **Complexity** | Simple | Medium | Complex |
| **Best For** | Code-only apps | Compliance needs | ML/AI apps |
| **Setup Time** | 30 minutes | 45 minutes | 60 minutes |

---

## Which Strategy Should I Use?

### Choose Direct Branch if:
- ✅ Your application is primarily code
- ✅ You want the simplest setup
- ✅ Git history is sufficient for audit
- ✅ You don't need instant rollback
- ✅ You're just getting started

**→ This is the recommended starting point for most teams**

### Choose Bundle-Based if:
- ✅ You need compliance/audit trail
- ✅ You need instant rollback capability
- ✅ You deploy to multiple regions
- ✅ Your organization requires artifact versioning
- ✅ You need to prove same code went everywhere

### Choose Hybrid if:
- ✅ You have ML models or large binary files
- ✅ Models change less frequently than code
- ✅ You need version pinning for models
- ✅ You want fast code deployment
- ✅ You're comfortable with complexity

---

## Migrating Between Strategies

You can start with one strategy and migrate to another later:

**Direct Branch → Bundle-Based:**
- Add S3 bucket for artifacts
- Update workflow to create bundles
- No manifest changes needed

**Direct Branch → Hybrid:**
- Add S3 bucket for models
- Update manifest to specify bundled content
- Update workflow to handle both types

**Bundle-Based → Hybrid:**
- Update manifest to separate code and models
- Update workflow to deploy code directly
- Keep bundle logic for models

---

## Getting Help

**For direct branch (this guide):**
- Follow the steps in this guide
- Contact DevOps team for setup help

**For alternative strategies:**
- Review workflow templates in respective folders
- Contact DevOps team for guidance
- Consider starting with direct-branch first

All three strategies use the same:
- AWS infrastructure (OIDC, IAM roles)
- GitHub setup (environments, secrets)
- SMUS CLI commands
- Manifest format (with minor additions)

The main difference is in the workflow logic, not the infrastructure setup.
