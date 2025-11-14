# SMUS Generic GitHub Workflow Templates

This directory contains generic, reusable GitHub Actions workflows for deploying SMUS applications. These templates are designed to be **application-agnostic** - DevOps teams can provide them to data teams without knowing the specifics of each application.

## Philosophy: Separation of Concerns

**DevOps Teams Own:**
- GitHub workflow templates (HOW and WHEN to deploy)
- CI/CD pipeline structure
- Security and compliance gates
- Infrastructure setup

**Data Teams Own:**
- Application manifest (`manifest.yaml`) (WHAT and WHERE to deploy)
- Application code and workflows
- Stage-specific configurations
- Business logic

## Available Deployment Strategies

### 1. Direct Branch-Based Deployment
**Location:** [`direct-branch/`](direct-branch/)

**Use Case:** Deploy directly from git branches without creating bundle artifacts

**Branch Strategy:**
- `feature/*` branches → Dev stage (manual deployment by developers)
- `*-test-branch` → Test stage (automated deployment)
- `*-prod-branch` → Prod stage (automated deployment with approval)

**Example branch names:**
- `demo-feature1-test-branch` → Test environment
- `demo-feature1-prod-branch` → Production environment

**Features:**
- ✅ No bundle creation (direct deployment)
- ✅ Branch-based promotion workflow
- ✅ Automated testing after deployment
- ✅ Manual approval for production
- ✅ Status checks enforcement

**Best For:**
- Teams using GitFlow or similar branching strategies
- Applications where git is the source of truth
- Fast iteration cycles
- Teams that want clear promotion paths

**Status:** ✅ **Available Now**

**Documentation:**
- [DevOps Guide](direct-branch/DEVOPS-GUIDE.md)
- [Application Admin Guide](direct-branch/APPLICATION-ADMIN-GUIDE.md)
- [README](direct-branch/README.md)

---

### 2. Bundle-Based Deployment
**Location:** [`bundle-based/`](bundle-based/)

**Use Case:** Create versioned bundle artifacts and deploy them across stages

**Features:**
- Create bundle once, deploy many times
- Versioned artifacts for audit trail
- Rollback to previous bundles instantly
- Compliance and governance support
- Deploy same artifact to multiple environments

**Best For:**
- Teams requiring artifact versioning
- Compliance-heavy environments
- Need for instant rollback capability
- Audit trail requirements
- Multi-region deployments

**Status:** 🚧 **Coming Soon** (Q1 2026)

**Documentation:**
- [README](bundle-based/README.md) - Overview and use cases

---

### 3. Hybrid Bundle-Branch Deployment
**Location:** [`hybrid-bundle-branch/`](hybrid-bundle-branch/)

**Use Case:** Combine direct deployment for code with bundle deployment for large artifacts (ML models, data, etc.)

**Features:**
- Direct deployment for code (fast)
- Bundle deployment for models/artifacts (versioned)
- Independent update paths
- Version pinning for artifacts
- Best of both approaches

**Best For:**
- ML/AI applications with large model files
- Applications with binary artifacts
- Mixed content (code + models + data)
- Need fast code updates, controlled model deployment

**Status:** 🚧 **Coming Soon** (Q2 2026)

**Documentation:**
- [README](hybrid-bundle-branch/README.md) - Overview and use cases
- [Quick Reference](direct-branch/QUICK-REFERENCE.md)
- [Architecture](direct-branch/ARCHITECTURE.md)

### 2. Bundle-Based Deployment (Coming Soon)
**Location:** `bundle-based/` (planned)

**Use Case:** Create versioned bundle artifacts and deploy them across stages

**Features:**
- Create bundle once, deploy many times
- Versioned artifacts for audit trail
- Rollback to previous bundles
- Compliance and governance support

**Best For:**
- Teams requiring artifact versioning
- Compliance-heavy environments
- Need for rollback capability
- Audit trail requirements

## Quick Start

### Choose Your Deployment Strategy

1. **Direct Branch-Based** (Recommended for most teams)
   - Go to [`direct-branch/`](direct-branch/)
   - Follow [SETUP-GUIDE.md](direct-branch/SETUP-GUIDE.md)

2. **Bundle-Based** (Coming soon)
   - For teams requiring artifact versioning
   - Documentation coming soon

## General Prerequisites

Before using any template:

1. **AWS Account Setup**
   - SageMaker Unified Studio domain created
   - Projects created for each stage (or enable auto-creation in manifest)
   - OIDC provider configured for GitHub Actions

2. **GitHub Repository Setup**
   - Repository with your application code
   - Application manifest file (`manifest.yaml`)

### Step 1: Set Up Branch Protection Rules

Configure branch protection in your repository settings:

**Branch: `test`**
- Settings → Branches → Add branch protection rule
- Branch name pattern: `test`
- Protection rules:
  - ✅ Require a pull request before merging
  - ✅ Require approvals: 1
  - ✅ Dismiss stale pull request approvals when new commits are pushed

**Branch: `main`**
- Settings → Branches → Add branch protection rule
- Branch name pattern: `main`
- Protection rules:
  - ✅ Require a pull request before merging
  - ✅ Require approvals: 1
  - ✅ Require status checks to pass before merging
  - ✅ Status checks: Select "Deploy to Test" (after first run)
  - ✅ Require branches to be up to date before merging
  - ✅ Dismiss stale pull request approvals when new commits are pushed

### Step 2: Configure GitHub Environments

Create two GitHub environments in your repository settings:

**Environment: `aws-test`**
- Variables:
  - `TEST_DOMAIN_REGION`: AWS region for test domain (e.g., `us-east-1`)
- Secrets:
  - `AWS_ROLE_ARN_TEST`: OIDC role ARN for test deployments
- Protection rules:
  - Deployment branches: Select "Selected branches" → Add `test`

**Environment: `aws-prod`**
- Variables:
  - `PROD_DOMAIN_REGION`: AWS region for prod domain (e.g., `us-east-1`)
- Secrets:
  - `AWS_ROLE_ARN_PROD`: OIDC role ARN for prod deployments
- **Protection rules (REQUIRED):**
  - ✅ Required reviewers: Add at least 1 reviewer (different from PR author)
  - ✅ Wait timer: 0 minutes (or as needed)
  - ✅ Deployment branches: Select "Selected branches" → Add `main`

### Step 3: Create Required Branches

Create the `test` and `main` branches if they don't exist:

```bash
# Create test branch from your current branch
git checkout -b test
git push origin test

# Create main branch from test
git checkout -b main
git push origin main

# Go back to your feature branch
git checkout -b feature/initial-setup
```

### Step 4: Copy Workflow Template

1. Copy the desired template from `git-templates/` to `.github/workflows/` in your repository
2. Rename it to something meaningful (e.g., `deploy-my-app.yml`)
3. Customize the workflow inputs if needed (manifest path, stage names, etc.)

### Step 3: Configure Your Manifest

Ensure your `manifest.yaml` has the required structure:

```yaml
applicationName: MyApplication

content:
  storage:
    - name: code
      connectionName: default.s3_shared
      include:
        - src/

initialization:
  - type: workflow
    workflowName: my_workflow
    connectionName: project.workflow_serverless
    engine: airflow-serverless

tests:
  folder: tests/

stages:
  dev:
    stage: DEV
    domain:
      name: my-domain
      region: ${DEV_DOMAIN_REGION}
    project:
      name: dev-myapp
  
  test:
    stage: TEST
    domain:
      name: my-domain
      region: ${TEST_DOMAIN_REGION}
    project:
      name: test-myapp
  
  prod:
    stage: PROD
    domain:
      name: my-domain
      region: ${PROD_DOMAIN_REGION}
    project:
      name: prod-myapp
```

### Step 4: Run the Workflow

**Manual Trigger:**
```
GitHub UI → Actions → Select workflow → Run workflow
```

**Automatic Trigger:**
- Push to `main` branch (if configured)
- Create pull request (if configured)

## Customization Guide

### Changing Manifest Path

If your manifest is not at the root, update the workflow input:

```yaml
inputs:
  manifest_path:
    default: 'path/to/your/manifest.yaml'
```

### Adding Additional Steps

You can add custom steps before or after deployment:

```yaml
- name: Custom validation
  run: |
    # Your custom validation logic
    
- name: Deploy
  run: smus-cli deploy --manifest ${{ inputs.manifest_path }} ${{ matrix.stage }}

- name: Custom post-deployment
  run: |
    # Your custom post-deployment logic
```

### Changing Stage Names

If you use different stage names (e.g., `staging` instead of `test`):

1. Update the matrix in the workflow
2. Update your manifest to match

### Adding Slack/Email Notifications

Add notification steps at the end of jobs:

```yaml
- name: Notify on success
  if: success()
  run: |
    # Send notification
    
- name: Notify on failure
  if: failure()
  run: |
    # Send failure notification
```

## Environment Variables Reference

### Required by SMUS CLI

These are automatically set by the workflow:

- `DEV_DOMAIN_REGION`: Set from GitHub environment variable
- `TEST_DOMAIN_REGION`: Set from GitHub environment variable
- `PROD_DOMAIN_REGION`: Set from GitHub environment variable
- `SMUS_LOG_LEVEL`: Set to `WARNING` (can be changed to `INFO` or `DEBUG`)

### Available in Manifest

You can reference these in your manifest using `${VAR_NAME}` syntax:

```yaml
stages:
  dev:
    domain:
      region: ${DEV_DOMAIN_REGION}
```

## Troubleshooting

### "Domain not found" Error

**Cause:** Domain name in manifest doesn't match actual domain name in AWS

**Solution:** Verify domain name in your manifest matches exactly:
```bash
aws datazone list-domains --query "items[].name"
```

### "Project not found" Error

**Cause:** Project doesn't exist and auto-creation is disabled

**Solution:** Either:
1. Create the project manually in AWS
2. Enable auto-creation in manifest:
   ```yaml
   stages:
     dev:
       project:
         name: dev-myapp
         create: true
   ```

### "Permission denied" Error

**Cause:** OIDC role doesn't have required permissions

**Solution:** Ensure the role has:
- `datazone:*` permissions for domain/project operations
- `s3:*` permissions for storage operations
- `airflow:*` permissions for workflow operations

### Workflow Fails on Test Stage

**Cause:** Tests are failing after deployment

**Solution:** 
1. Check test logs in the workflow output
2. Run tests locally: `smus-cli test --manifest manifest.yaml`
3. Fix failing tests in your application

## Best Practices

1. **Use Environment Protection Rules**
   - Require manual approval for production deployments
   - Restrict production deployments to specific branches

2. **Keep Manifests Simple**
   - Let the workflow handle the complexity
   - Focus manifest on application definition

3. **Version Your Workflows**
   - Tag workflow versions when making changes
   - Document breaking changes

4. **Test in Dev First**
   - Always deploy to dev before test/prod
   - Use dev for experimentation

5. **Monitor Deployments**
   - Check workflow logs regularly
   - Set up notifications for failures

## Examples

See the `examples/` directory for complete examples of:
- ETL pipeline deployment
- ML model deployment
- Notebook deployment
- Multi-workflow applications

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the SMUS CLI documentation
3. Contact your DevOps team

## Contributing

To add new templates:
1. Create the workflow file in `git-templates/`
2. Update this README with template description
3. Add example usage
4. Test with a real application
