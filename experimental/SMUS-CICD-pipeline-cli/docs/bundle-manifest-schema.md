# Bundle Manifest Schema

← [Back to Main README](../README.md)

This directory contains the JSON schema and validation tools for SMUS CI/CD bundle manifests.

## Files

- **`pipeline-manifest-schema.yaml`** - YAML Schema definition for bundle manifests
- **`pipeline-manifest-schema.json`** - JSON Schema definition (legacy)
- **`validate_manifests.py`** - Python script to validate manifests against the schema
- **`INCONSISTENCIES.md`** - Documentation of inconsistencies found during schema creation
- **`README.md`** - This documentation file

## Schema Overview

The schema defines the structure for SMUS CI/CD bundle manifests with the following main sections:

### Required Fields
- **`bundleName`** - Unique bundle identifier
- **`domain`** - DataZone domain configuration (name, region)
- **`targets`** - Target environments (dev, test, prod, etc.)

### Optional Fields
- **`bundle`** - Bundle creation configuration
- **`workflows`** - Global workflow definitions

## Usage

### Validate All Manifests
```bash
cd /path/to/smus_cicd
python schema/validate_manifests.py
```

### Validate Single Manifest (Python)
```python
import yaml
from jsonschema import validate

# Load schema
with open('schema/pipeline-manifest-schema.yaml', 'r') as f:
    schema = yaml.safe_load(f)

# Load manifest
with open('bundle.yaml', 'r') as f:
    manifest = yaml.safe_load(f)

# Validate
validate(manifest, schema)
print("✅ Valid!")
```

### Integration with CLI
The schema can be integrated into the CLI commands for validation:

```python
from smus_cicd.validation import validate_manifest_schema

# In describe command
if not validate_manifest_schema(manifest_path):
    typer.echo("❌ Invalid manifest schema", err=True)
    raise typer.Exit(1)
```

## Schema Structure

### Domain Configuration
```yaml
domain:
  name: cicd-test-domain    # Required: DataZone domain name
  region: us-east-1         # Required: AWS region
```

### Bundle Configuration
```yaml
bundle:
  bundlesDirectory: ./bundles  # Optional: Bundle output directory (local or S3)
  storage:                     # Optional: Storage bundle config (unified - includes workflows)
    - name: code               # Required: Unique name for this bundle item
      connectionName: default.s3_shared
      append: false            # Optional: Append vs replace
      include: ['src/']        # Optional: Include patterns
      exclude: ['*.pyc']       # Optional: Exclude patterns
    - name: workflows          # Required: Unique name for workflows
      connectionName: default.s3_shared
      append: true
      include: ['workflows/']
  git:                         # Optional: Git repository
    repository: my-repo
    url: https://github.com/user/repo.git
  catalog:                     # Optional: Catalog asset access
    assets:                    # Required: List of assets
      - selector:              # Required: Asset selector
          search:              # Required: Search configuration
            assetType: GlueTable  # Required: Asset type
            identifier: db.table  # Required: Asset identifier
        permission: READ       # Required: Access permission
        requestReason: "Pipeline access"  # Required: Access justification
```

### Target Configuration
```yaml
targets:
  dev:                         # Target name (required)
    stage: DEV                 # Optional: Stage identifier
    default: true              # Optional: Default target flag
    project:                   # Required: Project config
      name: dev-project        # Required: Project name
    initialization:            # Optional: Init config
      project:                 # Optional: Project creation
        create: true           # Optional: Auto-create project
        profileName: 'All capabilities'
        owners: [Eng1]         # Optional: Project owners
        contributors: []       # Optional: Project contributors
        role:                  # Optional: Customer-provided IAM role
          arn: arn:aws:iam::123456789012:role/MyProjectRole
      environments:            # Optional: Environment configs
        - EnvironmentConfigurationName: 'OnDemand Workflows'
    bundle_target_configuration: # Optional: Target-specific bundle config
      storage:
        - name: code           # Required: Name matching bundle storage item
          connectionName: default.s3_shared
          targetDirectory: 'src'  # Required: Target directory on connection
        - name: workflows
          connectionName: default.s3_shared
          targetDirectory: 'workflows'
    workflows:                 # Optional: Target-specific workflows
      - workflowName: prepareData
        parameters:
          stage_database: DevDB
```

### Workflow Configuration
```yaml
workflows:
  - workflowName: test_dag           # Required: Workflow name
    connectionName: project.workflow_mwaa  # Required: Connection
    triggerPostDeployment: true      # Optional: Auto-trigger
    engine: MWAA                     # Optional: Engine type
    parameters:                      # Optional: Workflow parameters
      default-sql-connection: project.athena
    logging: console                 # Optional: Logging config
```

## Validation Rules

### Naming Conventions
- **Pipeline names**: Must start with letter, contain only alphanumeric, underscore, hyphen
- **Target names**: Must start with letter, contain only alphanumeric, underscore, hyphen
- **Regions**: Must match AWS region pattern (e.g., `us-east-1`)

### Constraints
- At least one target must be defined
- Only string, number, or boolean values allowed in parameters
- Connection names should follow DataZone naming conventions
- File patterns should use forward slashes

### Optional vs Required
- Most fields are optional to accommodate different use cases
- Only core identification fields are required
- Schema allows for flexible manifest structures

## Common Patterns

### Dev-Only Pipeline
```yaml
bundleName: DevOnlyBundle
domain:
  name: my-domain
  region: us-east-1
targets:
  dev:
    default: true
    project:
      name: dev-project
```

### Multi-Target Pipeline
```yaml
bundleName: MultiTargetBundle
domain:
  name: my-domain
  region: us-east-1
targets:
  dev:
    default: true
    project:
      name: dev-project
  test:
    project:
      name: test-project
    initialization:
      project:
        create: true
        owners: [Eng1]
  prod:
    project:
      name: prod-project
    initialization:
      project:
        create: true
        owners: [Eng1]
```

## Error Handling

The validation script provides detailed error messages including:
- **Path**: Location of the error in the manifest
- **Message**: Description of the validation failure
- **Expected**: What the schema expected (for enum/pattern violations)

Example error output:
```
❌ INVALID - Found 2 schema violations:
  1. Path: domain -> region
     Error: 'invalid-region' does not match '^[a-z0-9-]+$'
     Expected: ^[a-z0-9-]+$

  2. Path: targets -> dev -> project
     Error: 'name' is a required property
```


