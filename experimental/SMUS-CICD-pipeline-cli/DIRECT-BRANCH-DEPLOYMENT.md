# Direct Branch Deployment Implementation

## Overview

This feature enables deploying code directly from the local filesystem to SMUS projects without requiring the intermediate bundle creation step. This is particularly useful for CI/CD workflows where code is checked out from git branches.

## Changes Made

### 1. Schema Updates

**Files Modified:**
- `src/smus_cicd/application/application_manifest.py`
- `src/smus_cicd/application/manifest-schema.yaml`
- `src/smus_cicd/application/application-manifest-schema.yaml`

**Changes:**
- Made `connectionName` optional in `StorageConfig` dataclass
- Updated schema definitions to allow missing `connectionName` in content storage items

### 2. Deploy Command Enhancements

**File Modified:** `src/smus_cicd/commands/deploy.py`

**New Functions:**
- `_has_local_content()` - Detects if manifest has local content (no connectionName)
- `_deploy_local_content()` - Orchestrates local filesystem deployment
- `_deploy_local_storage_item()` - Deploys individual storage items from local filesystem

**Modified Functions:**
- `_deploy_bundle_to_target()` - Added manifest_file parameter and local content detection

**Key Features:**
- Paths are resolved relative to manifest file location
- Supports include/exclude patterns
- Maintains compatibility with S3-based deployments
- Respects deployment_configuration overrides

### 3. Manifest Updates

**File Modified:** `examples/analytic-workflow/genai/manifest.yaml`

**Changes:**
- Removed `connectionName` from content section storage items
- Fixed include paths to match actual directory structure

## Usage

### Manifest Configuration

For local deployment, omit `connectionName` from content storage items:

```yaml
content:
  storage:
  - name: agent-code
    include:
    - job-code
  - name: genai-workflows
    include:
    - workflows
```

The `deployment_configuration` section still requires `connectionName` to specify the target S3 location:

```yaml
stages:
  test:
    deployment_configuration:
      storage:
      - name: agent-code
        connectionName: default.s3_shared
        targetDirectory: genai/bundle/agent-code
```

### Deployment Command

```bash
# Set required environment variables
export AWS_ACCOUNT_ID=198737698272
export TEST_DOMAIN_REGION=us-east-2

# Deploy directly from local filesystem
smus-cli deploy --manifest manifest.yaml --targets test
```

### Expected Output

```
📁 Detected local content - deploying directly from filesystem
📁 Manifest directory: /path/to/manifest/dir

Deploying local storage item 'agent-code' to genai/bundle/agent-code...
  Pattern: job-code → /path/to/manifest/dir/job-code
  Found 8 files
  All 8 files already up to date

📦 Deployment Summary:
  ✅ agent-code: 8 files → s3://bucket/shared/
  ✅ genai-workflows: 2 files → s3://bucket/shared/

✅ Deployment completed successfully!
```

## Testing

Run the test script:

```bash
cd experimental/SMUS-CICD-pipeline-cli
./test-direct-deploy.sh
```

## Backward Compatibility

This feature is fully backward compatible:
- Manifests with `connectionName` in content section continue to work (bundle-based deployment)
- Manifests without `connectionName` use local filesystem deployment
- Mixed mode is supported (some items from S3, some from local)

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Deploy to SMUS
  env:
    AWS_ACCOUNT_ID: ${{ secrets.AWS_ACCOUNT_ID }}
    TEST_DOMAIN_REGION: us-east-1
  run: |
    smus-cli deploy --manifest manifest.yaml --targets test
```

### Benefits

1. **No Bundle Step Required** - Eliminates the need to upload to S3 before bundling
2. **Faster Deployments** - Direct sync from filesystem to target S3
3. **Simpler Workflows** - One command instead of upload → bundle → deploy
4. **Git Branch Support** - Works seamlessly with checked-out git branches

## Path Resolution

All paths in `include` patterns are resolved relative to the manifest file location, not the current working directory. This ensures consistent behavior regardless of where the command is executed.

Example:
```
Manifest: examples/analytic-workflow/genai/manifest.yaml
Include:  job-code
Resolved: examples/analytic-workflow/genai/job-code
```

## Limitations

- Only storage items support local deployment (workflows still require connectionName)
- Git items are not supported for local deployment
- Include patterns must point to files/directories relative to manifest location
