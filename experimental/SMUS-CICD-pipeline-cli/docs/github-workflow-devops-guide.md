# DevOps Guide - SMUS Direct Branch Deployment

← [Back to Main README](../README.md)


← [Workflow Templates](../git-templates/) | [Application Guide](github-workflow-application-guide.md) | [Main README](../README.md)

**Audience:** DevOps, Platform Engineers, Infrastructure Teams  
**Purpose:** Set up and maintain the organization's deployment workflow template

---

## Overview

This guide covers how to set up and maintain the **organization-level workflow template** that application teams will use to deploy their SMUS applications.

### What You'll Provide

- ✅ Central workflow template (`org-template-workflow.yml`)
- ✅ Documentation for application teams
- ✅ AWS infrastructure setup (OIDC, IAM roles)
- ✅ GitHub organization configuration
- ✅ Version management and updates

### What Application Teams Will Do

- Configure their application-specific parameters
- Set up their GitHub secrets and environments
- Deploy their applications using your template

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Central Workflow Repository (your-org/workflow-templates)    │
│                                                              │
│  org-template-workflow.yml                                  │
│  ├─ Maintained by: DevOps team                              │
│  ├─ Versioned: v1.0.0, v1.1.0, etc.                         │
│  └─ Used by: All application teams                          │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ↓ called by
┌─────────────────────────────────────────────────────────────┐
│ Application Repositories (app teams)                         │
│                                                              │
│  .github/workflows/deploy.yml                               │
│  ├─ Calls: org-template-workflow.yml@v1                     │
│  ├─ Configures: Branch names, manifest path                 │
│  └─ Deploys: Their specific application                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1: Create Central Workflow Repository

### 1.1 Create Repository

```bash
# Create a new repository for workflow templates
gh repo create your-org/workflow-templates --public

# Clone it
git clone https://github.com/your-org/workflow-templates.git
cd workflow-templates
```

### 1.2 Add the Workflow Template

```bash
# Create workflows directory
mkdir -p .github/workflows

# Copy the template
cp /path/to/org-template-workflow.yml .github/workflows/smus-direct-branch.yml

# Commit and push
git add .github/workflows/smus-direct-branch.yml
git commit -m "feat: add SMUS direct branch deployment workflow"
git push origin main
```

### 1.3 Tag the First Version

```bash
# Create initial version tag
git tag -a v1.0.0 -m "Initial release of SMUS deployment workflow"
git push origin v1.0.0
```

---

## Step 2: Set Up AWS Infrastructure

### Configure GitHub Actions Authentication

Use the provided CloudFormation template:

```bash
aws cloudformation deploy \
  --template-file path/to/github-oidc-role.yaml \
  --stack-name smus-cli-github-integration \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    GitHubOrg=your-org \
    GitHubRepo='*' \
    GitHubEnvironment=aws-env
```

**Get the role ARN:**
```bash
aws cloudformation describe-stacks \
  --stack-name smus-cli-github-integration \
  --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
  --output text
```

**Template location:** `tests/scripts/setup/1-account-setup/github-oidc-role.yaml`

### Required Permissions

> **⚠️ TODO:** Document minimum required IAM permissions.
> 
> **Current reference:** See CloudFormation template for example permissions.

### Separate Test and Production Roles (Recommended)

Create separate roles for better security isolation. See [Admin Guide](getting-started/admin-quickstart.md#step-8-set-up-cicd-authentication-optional) for details.

---

## Step 3: Document for Application Teams

Create documentation for application teams. Provide them with:

1. **Link to workflow template repository**
2. **IAM role ARNs** they should use
3. **Required GitHub secrets** they need to configure
4. **Example configuration** for their workflow

See `APPLICATION-ADMIN-GUIDE.md` for the documentation to provide to teams.

---

## Step 4: Version Management

### Versioning Strategy

Use semantic versioning:
- **Major version (v2.0.0):** Breaking changes
- **Minor version (v1.1.0):** New features, backward compatible
- **Patch version (v1.0.1):** Bug fixes

### Creating New Versions

```bash
# Make changes to the workflow
vim .github/workflows/smus-direct-branch.yml

# Commit changes
git add .github/workflows/smus-direct-branch.yml
git commit -m "feat: add support for custom AWS regions"

# Tag new version
git tag -a v1.1.0 -m "Add custom AWS region support"
git push origin v1.1.0

# Update major version tag (optional)
git tag -f v1
git push origin v1 --force
```

### Communicating Updates

When releasing new versions:

1. **Create GitHub Release** with changelog
2. **Notify application teams** via Slack/email
3. **Provide migration guide** if breaking changes
4. **Update documentation**

---

## Step 5: Monitoring and Support

### Monitor Workflow Usage

```bash
# See which repositories are using your workflow
gh api /repos/your-org/workflow-templates/dependents
```

### Common Support Issues

**Issue: "Workflow not found"**
- Check repository visibility (must be public or internal)
- Verify path: `.github/workflows/smus-direct-branch.yml`

**Issue: "Permission denied"**
- Check IAM role trust policy
- Verify OIDC provider exists
- Check role permissions

**Issue: "Tests failing"**
- This is application-specific
- Direct teams to check their application code
- Not a workflow issue

---

## Maintenance Tasks

### Regular Updates

- **Monthly:** Review and update dependencies
- **Quarterly:** Review IAM permissions
- **As needed:** Add new features based on feedback

### Breaking Changes

If you need to make breaking changes:

1. Create new major version (v2.0.0)
2. Maintain old version (v1.x.x) for 6 months
3. Provide migration guide
4. Give teams advance notice

---

## Best Practices

1. **Version pinning:** Encourage teams to use `@v1` not `@main`
2. **Testing:** Test changes with a pilot application first
3. **Documentation:** Keep docs up to date with workflow changes
4. **Communication:** Announce changes before releasing
5. **Backward compatibility:** Avoid breaking changes when possible

---

## Support Channels

Set up support channels for application teams:
- **Slack:** #smus-deployments
- **Email:** devops@your-org.com
- **Documentation:** Link to APPLICATION-ADMIN-GUIDE.md
- **Office hours:** Weekly Q&A sessions

---

## Summary

As DevOps, you provide:
- ✅ Central workflow template
- ✅ AWS infrastructure (OIDC, IAM roles)
- ✅ Documentation and support
- ✅ Version management
- ✅ Updates and improvements

Application teams handle:
- Their application code
- Their manifest configuration
- Their GitHub secrets
- Their deployments

This separation of concerns allows you to maintain one workflow that serves all applications!


---

## Alternative Deployment Strategies

This guide focuses on **direct branch-based deployment**, but SMUS supports three deployment strategies. Here's an overview of the alternatives:

### Bundle-Based Deployment

**Location:** [`bundle-based/`](../git-templates/bundle-based/)

**How it works:**
1. Create versioned bundle artifact (tar.gz)
2. Upload bundle to artifact repository (S3)
3. Deploy same bundle to test
4. Deploy same bundle to prod (after approval)

**Key differences from direct-branch:**
- Creates versioned artifacts
- Same artifact deployed to all environments
- Instant rollback (redeploy old bundle)
- Requires artifact storage (S3)

**Best for:**
- Compliance requirements (artifact versioning)
- Multi-region deployments
- Need for instant rollback
- Audit trail requirements

**Setup differences:**
- Configure S3 bucket for artifacts
- Bundle creation step in workflow
- Download bundle before deployment

### Hybrid Bundle-Branch Deployment

**Location:** [`hybrid-bundle-branch/`](../git-templates/hybrid-bundle-branch/)

**How it works:**
1. Code: Direct deployment from git (fast)
2. Models/Artifacts: Bundle deployment (versioned)
3. Combined deployment to test and prod

**Key differences from direct-branch:**
- Code deployed directly (like direct-branch)
- Large artifacts deployed as bundles
- Independent update paths
- Version pinning for artifacts

**Best for:**
- ML/AI applications with large models
- Applications with binary artifacts
- Mixed content (code + models + data)
- Need fast code updates, controlled model deployment

**Setup differences:**
- Configure artifact repository for models
- Manifest specifies which content is bundled
- Workflow handles both direct and bundle deployment

---

## Choosing a Strategy

| Criteria | Direct Branch | Bundle-Based | Hybrid |
|----------|---------------|--------------|--------|
| **Speed** | Fast | Slower | Fast for code |
| **Artifacts** | None | Versioned | Versioned for models |
| **Rollback** | Git revert | Instant | Mixed |
| **Storage** | None | S3 required | S3 for models |
| **Complexity** | Simple | Medium | Complex |
| **Best For** | Code-only apps | Compliance | ML/AI apps |

**Recommendation:**
- Start with **direct-branch** (simplest)
- Move to **bundle-based** if you need compliance/rollback
- Use **hybrid** for ML/AI applications with large models

---

## Support

For questions about alternative strategies:
- Review the workflow templates in each folder
- Contact DevOps team for guidance
- Start with direct-branch and migrate later if needed

All three strategies use the same AWS infrastructure (OIDC, IAM roles) and GitHub setup (environments, secrets).
