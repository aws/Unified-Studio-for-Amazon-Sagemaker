# Generic SMUS CI/CD Workflows

These workflows follow the **separation of concerns** principle where:
- **SMUS CLI** handles all AWS complexity
- **Workflows** enforce CI/CD best practices
- **Application teams** only configure parameters

## Available Workflows

### 1. Simple Deployment (`smus-deploy-reusable.yml`)

**Purpose:** Basic deployment to one or more targets

**Use when:**
- Single environment deployment
- Simple CI/CD pipeline
- No approval gates needed

**Example usage:**
```yaml
jobs:
  deploy:
    uses: ./.github/workflows/smus-deploy-reusable.yml
    with:
      manifest_path: 'manifest.yaml'
      targets: 'test'
      run_tests: true
    secrets:
      AWS_ROLE_ARN: ${{ secrets.AWS_ROLE_ARN_TEST }}
```

### 2. Multi-Environment Deployment (`smus-multi-env-reusable.yml`)

**Purpose:** Test → Prod pipeline with approval gates

**Use when:**
- Multiple environments (test, prod)
- Approval required for production
- Automated testing between stages

**Example usage:**
```yaml
jobs:
  deploy:
    uses: ./.github/workflows/smus-multi-env-reusable.yml
    with:
      manifest_path: 'manifest.yaml'
      test_target: 'test'
      prod_target: 'prod'
      deploy_to_prod: true
```

## Setup Instructions

### 1. Configure GitHub Environments

**Test Environment:**
```
Repository Settings → Environments → New environment: "test"
- No protection rules needed
```

**Production Environment:**
```
Repository Settings → Environments → New environment: "production"
- Required reviewers: Add at least 1 reviewer
- Deployment branches: Limit to main/prod branches
```

### 2. Configure Secrets

**Environment Secrets (Recommended):**
```
Settings → Environments → test → Add secret
  AWS_ROLE_ARN: arn:aws:iam::ACCOUNT:role/GitHubActions-SMUS-Test

Settings → Environments → production → Add secret
  AWS_ROLE_ARN: arn:aws:iam::ACCOUNT:role/GitHubActions-SMUS-Prod
```

Each environment has its own `AWS_ROLE_ARN` secret, automatically used based on the environment.

### 3. Create Application Workflow

Copy `deploy-example.yml` and customize:

```yaml
name: Deploy My Application

on:
  push:
    branches: [main, test]
  workflow_dispatch:

jobs:
  deploy:
    uses: ./.github/workflows/smus-multi-env-reusable.yml
    with:
      manifest_path: 'my-app/manifest.yaml'  # Your manifest path
      test_target: 'test'                     # Your test target
      prod_target: 'prod'                     # Your prod target
```

## Key Features

### ✅ Application-Agnostic
- Works for Glue, SageMaker, Bedrock, or any AWS service
- No AWS API calls in workflow
- SMUS CLI handles all complexity

### ✅ Reusable
- One workflow serves all applications
- Maintained by DevOps team
- Application teams just configure parameters

### ✅ Secure
- OIDC authentication (no long-lived credentials)
- Separate roles for test and prod
- Environment protection rules

### ✅ Automated
- Validate → Deploy → Test → Approve → Deploy
- Automatic infrastructure creation
- Idempotent operations

## Workflow Parameters

### Common Inputs

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `manifest_path` | Path to manifest file | `manifest.yaml` | No |
| `python_version` | Python version | `3.12` | No |
| `aws_region` | AWS region | `us-east-1` | No |

### Simple Deployment Inputs

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `targets` | Comma-separated targets | - | Yes |
| `run_tests` | Run tests after deploy | `true` | No |

### Multi-Environment Inputs

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `test_target` | Test target name | `test` | No |
| `prod_target` | Prod target name | `prod` | No |
| `skip_tests` | Skip test execution | `false` | No |
| `deploy_to_prod` | Deploy to prod | `true` | No |

## Examples

### Example 1: Deploy to Test Only

```yaml
jobs:
  deploy-test:
    uses: ./.github/workflows/smus-deploy-reusable.yml
    with:
      manifest_path: 'manifest.yaml'
      targets: 'test'
    secrets:
      AWS_ROLE_ARN: ${{ secrets.AWS_ROLE_ARN_TEST }}
```

### Example 2: Test → Prod Pipeline

```yaml
jobs:
  deploy:
    uses: ./.github/workflows/smus-multi-env-reusable.yml
    with:
      manifest_path: 'manifest.yaml'
```

### Example 3: Multiple Targets at Once

```yaml
jobs:
  deploy-all:
    uses: ./.github/workflows/smus-deploy-reusable.yml
    with:
      manifest_path: 'manifest.yaml'
      targets: 'dev,test,staging'
    secrets:
      AWS_ROLE_ARN: ${{ secrets.AWS_ROLE_ARN }}
```

## Troubleshooting

### Workflow not found
- Ensure workflow file is in `.github/workflows/`
- Check file name matches the `uses:` reference

### Permission denied
- Verify AWS role ARN is correct
- Check OIDC provider is configured
- Ensure role trust policy allows GitHub Actions

### Tests failing
- Check application code and manifest
- Review test logs in workflow output
- Run `smus-cli test` locally to debug

## Migration from Old Workflows

If you have existing workflows that directly call AWS APIs:

1. **Identify AWS API calls** in your workflow
2. **Replace with SMUS CLI commands**:
   - AWS API → `smus-cli deploy`
   - Custom scripts → `smus-cli test`
3. **Use reusable workflow** instead of custom logic
4. **Configure parameters** for your application

**Before:**
```yaml
- name: Deploy to MWAA
  run: |
    aws mwaa create-environment ...
    aws s3 cp dags/ s3://...
    # 50+ lines of AWS API calls
```

**After:**
```yaml
uses: ./.github/workflows/smus-deploy-reusable.yml
with:
  manifest_path: 'manifest.yaml'
  targets: 'test'
```

## Support

- **Documentation:** [GitHub Actions Integration](../../docs/github-actions-integration.md)
- **Templates:** [git-templates/](../../git-templates/)
- **Examples:** [examples/](../../examples/)
