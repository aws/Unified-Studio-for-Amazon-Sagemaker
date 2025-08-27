# SMUS CI/CD Pipeline Examples

This directory contains example scripts and configurations demonstrating various SMUS CI/CD pipeline features and workflows.

## Example Pipeline Manifest

**File**: `pipeline.yaml`

A comprehensive example pipeline manifest showing all available configuration options including:

- **Multi-target deployment** (dev, test, prod)
- **S3 and local bundle storage** options
- **Auto-initialization** with custom parameters
- **Bundle configuration** for workflows, storage, and Git repositories
- **Target-specific workflows** with environment parameters
- **Global workflow definitions** with MWAA configuration
- **Testing configuration** and validation settings

### Usage

```bash
# Copy to your project root and customize
cp examples/pipeline.yaml ./pipeline.yaml

# Validate the configuration
smus-cli describe --connect

# Create a bundle from dev environment
smus-cli bundle --targets dev

# Deploy to test environment
smus-cli deploy --targets test
```

## Full Pipeline Lifecycle Demo

**File**: `full-pipeline-lifecycle.sh`

A comprehensive bash script that demonstrates the complete SMUS CI/CD pipeline lifecycle from creation to monitoring. This script showcases extensive CLI features and best practices.

### Features Demonstrated

- **S3 Bundle Storage**: Uses DataZone domain S3 bucket for centralized bundle storage
- **Multi-Target Deployment**: Deploys across dev, test, and production environments
- **Auto-Initialization**: Automatically creates projects and environments with custom parameters
- **Comprehensive Bundle Configuration**: Includes workflows, storage, and Git repositories
- **Target-Specific Parameters**: Different workflow parameters per environment
- **Integration Testing**: Automated testing of deployed environments
- **Workflow Operations**: DAG listing, triggering, and status monitoring
- **Safety Checks**: Production deployment confirmations and validations
- **Multiple Output Formats**: JSON and TEXT output options
- **Monitoring and Reporting**: Comprehensive status monitoring across all targets

### Usage

```bash
# Make the script executable
chmod +x examples/full-pipeline-lifecycle.sh

# Run the demo with your DataZone domain and project IDs
./examples/full-pipeline-lifecycle.sh <domain-id> <dev-project-id>

# Example:
./examples/full-pipeline-lifecycle.sh <domain-id> <dev-project-id>
```

### Prerequisites

1. **AWS Credentials**: Configured with DataZone and SMUS permissions
2. **SMUS CLI**: Installed and available in PATH
3. **Valid IDs**: DataZone domain ID and existing dev project ID
4. **Permissions**: S3 read/write access to DataZone domain bucket

### Script Flow

1. **Create Pipeline Manifest**: Generates comprehensive pipeline configuration
2. **Validate Configuration**: Checks connectivity and validates settings
3. **Create Bundle**: Downloads and packages content from dev environment
4. **Deploy to Test**: Auto-initializes test environment and deploys bundle
5. **Run Tests**: Executes integration tests to validate deployment
6. **Execute Workflows**: Demonstrates workflow operations and monitoring
7. **Monitor Status**: Provides comprehensive status across all environments
8. **Production Deployment**: Optional production deployment with safety checks
9. **Final Report**: Generates comprehensive status report
10. **Cleanup**: Optional cleanup function for demo resources

### Generated Files

- `demo-pipeline.yaml`: Complete pipeline manifest with advanced configuration
- `pipeline-status-report.json`: Final status report in JSON format

### Advanced Configuration Examples

The script demonstrates:

- **S3 Bundle Storage**: `s3://sagemaker-unified-studio-{account}-{region}-{domain}/bundles`
- **Multi-Source Bundles**: Workflows, storage, and Git repositories
- **Environment-Specific Parameters**: Different settings per target
- **Auto-Initialization**: Project creation with custom user parameters
- **Comprehensive Testing**: Integration test execution
- **Workflow Management**: DAG operations and monitoring
- **Production Safety**: Confirmation prompts and validation checks

### Customization

To adapt this script for your environment:

1. Update the `DOMAIN_NAME` and `REGION` variables
2. Modify the S3 bucket path to match your DataZone domain
3. Adjust project names and parameters as needed
4. Update Git repository URLs and workflow names
5. Customize test configurations and validation steps

This script serves as both a demonstration and a template for implementing comprehensive SMUS CI/CD pipelines in your organization.
