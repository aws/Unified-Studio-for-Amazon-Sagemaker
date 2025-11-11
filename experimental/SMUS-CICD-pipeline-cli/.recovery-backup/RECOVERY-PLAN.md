# Recovery Plan - Restore Latest Code with MCP Changes

## Backed Up Files
- `mcp_server.py` - MCP server implementation
- `integrate.py` - Integration command for Q CLI
- `run_mcp_server.sh` - MCP server wrapper script
- `pipeline-manifest-schema.yaml` - Updated schema with 6 new features

## Schema Changes Made (to re-apply)

### 1. Added 'airflow-serverless' to engine enum
Location: Line ~133
```yaml
engine:
  enum: 
    - "MWAA"
    - "airflow-serverless"  # ADD THIS
```

### 2. Added environment_variables at target level
Location: After tests property (~line 435)
```yaml
environment_variables:
  type: object
  description: "Environment variables for this target"
  additionalProperties:
    type: string
```

### 3. Changed bundle_target_configuration.storage to support array
Location: Line ~347
```yaml
storage:
  oneOf:
    - type: object  # Single storage
      required: [connectionName, directory]
      properties:
        connectionName: {type: string}
        directory: {type: string}
    - type: array   # Multiple storage configs
      items:
        type: object
        required: [connectionName]
        properties:
          connectionName: {type: string}
          targetDirectory: {type: string}
          compression: {type: string, enum: ['gz', 'tar.gz']}
```

### 4. Made domain.name optional, added domain.tags
Location: Line ~216
```yaml
domain:
  required: [region]  # Remove 'name' from required
  properties:
    name: {type: string}
    tags:  # ADD THIS
      type: object
      additionalProperties: {type: string}
    region: {type: string}
```

### 5. Added initialization.connections
Location: After initialization.project (~line 340)
```yaml
connections:
  type: array
  items:
    type: object
    required: [name, type]
    properties:
      name: {type: string}
      type: {type: string}
      properties:
        type: object
        additionalProperties: true
```

### 6. Added initialization.project.role
Location: In initialization.project properties (~line 300)
```yaml
role:
  type: object
  properties:
    arn:
      type: string
      pattern: "^arn:aws:iam::[0-9*]+:role/.+$"
```

## Recovery Steps

1. **Reset src/smus_cicd to internal/amirbo_beta_branch**
   ```bash
   cd experimental/SMUS-CICD-pipeline-cli
   git checkout internal/amirbo_beta_branch -- src/smus_cicd/
   ```

2. **Restore MCP files**
   ```bash
   cp .recovery-backup/mcp_server.py src/smus_cicd/
   cp .recovery-backup/integrate.py src/smus_cicd/commands/
   cp .recovery-backup/run_mcp_server.sh .
   ```

3. **Re-apply schema changes**
   ```bash
   # Use the backed up schema as reference
   # Apply the 6 changes listed above to:
   # src/smus_cicd/pipeline/pipeline-manifest-schema.yaml
   ```

4. **Verify manifests still validate**
   ```bash
   python -c "
   import sys
   sys.path.insert(0, 'src')
   from smus_cicd.pipeline.validation import validate_manifest_file
   # Test all 18 manifests
   "
   ```

## Files to Keep (already fixed)
- All manifest files in examples/ and tests/ (already updated with schema changes)
- q-tasks/ directory (task files)
- delete-incident-report.txt

## Source Branch
- Latest good code: `internal/amirbo_beta_branch` (commit 1cdfc32, Nov 10 10:59 AM)
- Has tags support in DomainConfig
- Has all latest features
