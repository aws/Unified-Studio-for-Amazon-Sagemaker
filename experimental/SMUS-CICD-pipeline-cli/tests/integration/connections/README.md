# DataZone Connection Testing

This directory contains all DataZone connection testing and validation work.

## Structure

### `api_validation/`
Python scripts for testing DataZone connection API functionality:

- `test_workflows_mwaa_connection.py` - Custom service model testing for WORKFLOWS_MWAA
- `test_workflows_mwaa_connection_v2.py` - Standard client testing for WORKFLOWS_MWAA  
- `test_all_connection_types.py` - Systematic validation of all connection types

### `examples/`
Connection configuration examples and schemas:

- `connection-examples.yaml` - Basic examples for 9 connection types
- `connection-examples-variants.yaml` - Multiple auth methods and configurations
- `connection-schemas.yaml` - Full connection schemas
- `minimal-connection-schemas.yaml` - Minimal required schemas

## Current Status

**Confirmed Working Connection Types:**
- SPARK (Glue) - ✅ Tested and working

**API Findings:**
- API requires `environmentIdentifier` (not `projectIdentifier`)
- Connection type inferred from props structure
- 8 supported property types: athena, glue, hyperPod, iam, redshift, s3, sparkEmr, sparkGlue
- WORKFLOWS_MWAA exists in projects but not accessible via public create-connection API

## Next Steps

1. Complete validation of all 8 supported connection types
2. Create validated examples for working connection types
3. Build connection helper for gamma endpoint integration
4. Integrate with bundle manifest processing
