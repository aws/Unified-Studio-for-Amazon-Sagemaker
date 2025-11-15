# GitHub Actions Workflow Templates

Pre-built GitHub Actions workflows for automating SMUS application deployments.

## Why These Templates?

**The CLI is the Abstraction Layer:** These templates are designed to be **application-agnostic** because the SMUS CLI encapsulates all AWS complexity. DevOps teams provide them once, and they work for ANY SMUS application - whether it uses Glue, SageMaker, Bedrock, or any combination of AWS services.

**What makes this possible:**
- **DevOps teams** create workflows that just call `smus-cli deploy`
- **SMUS CLI** handles all AWS service interactions (DataZone, Glue, Athena, SageMaker, MWAA, S3, IAM, etc.)
- **Data teams** define what to deploy in `manifest.yaml`

**The workflow doesn't need to know:**
- Which AWS services the application uses
- How to configure DataZone projects
- How to deploy to MWAA
- How to manage S3 artifacts
- How to handle IAM roles

**The workflow just needs to:**
- Run `smus-cli deploy --manifest manifest.yaml`
- Run `smus-cli test --manifest manifest.yaml`
- Enforce approval gates and notifications

**Result:** DevOps teams enforce best practices (testing, approvals, security) without calling a single AWS API. The CLI handles everything.

---

**Quick links:**
- **Application teams:** [Setup Guide](../docs/github-workflow-application-guide.md) (~30 min)
- **DevOps teams:** [Template Setup](../docs/github-workflow-devops-guide.md) (~15 min)
- **Back to CLI docs:** [Main README](../README.md)

---

## Available Templates

### Direct Branch Deployment (Available Now)

Deploy directly from git branches with automatic promotion.

**Files:**
- `direct-branch/org-template-workflow.yml` - Reusable workflow (for DevOps)
- `direct-branch/org-application-workflow.yml` - Caller workflow (for app teams)
- `direct-branch/example-config.yml` - Configuration example

**Setup:** [Application Guide](../docs/github-workflow-application-guide.md)

### Bundle-Based Deployment (Coming Q1 2026)

Create versioned artifacts for compliance and rollback.

**Files:** `bundle-based/` directory

### Hybrid Deployment (Coming Q2 2026)

Combine direct deployment for code with bundled artifacts for models.

**Files:** `hybrid-bundle-branch/` directory

---

## Quick Comparison

| Approach | Speed | Rollback | Best For |
|----------|-------|----------|----------|
| Direct Branch | Fast | Git revert | Code-only apps |
| Bundle-Based | Slower | Instant | Compliance needs |
| Hybrid | Mixed | Mixed | ML/AI apps |

**Not sure which to use?** Start with Direct Branch (simplest).

---

## Prerequisites

1. AWS account with SMUS domain
2. GitHub repository with manifest.yaml
3. AWS authentication configured (see [Admin Guide](../docs/getting-started/admin-quickstart.md#step-8-set-up-cicd-authentication-optional))

---

## Platform Note

These templates are for GitHub Actions. The SMUS CLI commands work with any CI/CD platform - just adapt the workflow syntax.


