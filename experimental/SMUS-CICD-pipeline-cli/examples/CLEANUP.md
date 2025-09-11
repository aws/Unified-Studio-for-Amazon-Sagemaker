# Demo Resource Cleanup

This directory contains scripts to clean up resources created during SMUS CICD pipeline demonstrations.

## Quick Cleanup

```bash
# Clean up default demo resources
./cleanup-demo-resources.sh

# Clean up specific pipeline
./cleanup-demo-resources.sh MyPipeline.yaml

# Clean up with custom domain and project
./cleanup-demo-resources.sh DemoMarketingPipeline.yaml my-domain my-project
```

## What Gets Cleaned Up

The cleanup script attempts to delete the following common demo targets:

- `test` - Test environment resources
- `staging` - Staging environment resources  
- `prod` - Production environment resources
- `demo` - Demo-specific resources
- `example` - Example resources
- `marketing` - Marketing demo resources
- `analytics` - Analytics demo resources

## Manual Cleanup

For specific target cleanup:

```bash
# Delete specific target
smus-cli delete --pipeline DemoMarketingPipeline.yaml --targets my-target --force

# Delete multiple targets
smus-cli delete --pipeline DemoMarketingPipeline.yaml --targets test,staging --force

# Check what exists before cleanup
smus-cli describe --pipeline DemoMarketingPipeline.yaml --targets --connect
```

## GitHub Workflow Changes

The GitHub workflow `full-pipeline-lifecycle.yml` no longer includes automatic cleanup as the first step. This prevents interference with concurrent runs and allows for manual resource management.

To re-enable automatic cleanup in the workflow, uncomment the `cleanup` job section in `.github/workflows/full-pipeline-lifecycle.yml`.

## Troubleshooting

**Script not found:**
```bash
cd experimental/SMUS-CICD-pipeline-cli/examples
chmod +x cleanup-demo-resources.sh
```

**CLI not installed:**
```bash
cd experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

**Permission errors:**
- Ensure your AWS credentials have the necessary permissions
- Check that you're in the correct AWS account/region
- Verify the domain and projects exist

**Resources not found:**
- This is expected for clean environments
- The script ignores errors for non-existent resources
- Use `smus-cli describe` to check current state
