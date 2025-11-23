# Glue-MWAA-Catalog Integration Test

**STATUS: IGNORED - Requires updated MWAA support**

This test validates the multi-target pipeline workflow with Glue, MWAA (Managed Workflows for Apache Airflow), and DataZone catalog integration across dev, test, and prod environments.

## Current Status

⚠️ **This test is currently marked as IGNORED** due to pending MWAA workflow execution support updates. The test infrastructure is complete but requires updated MWAA integration to be fully functional.

## Files

- `manifest.yaml` - Pipeline configuration with multiple targets
- `test_multi_target_app.py` - Integration test implementation (currently ignored)
- `code/` - Sample code and workflow files for testing

## Test Scenarios

### 1. Multi-Target Deployment
- Deploy to dev, test, and prod environments
- Validate Glue database creation per environment
- Deploy MWAA workflows to each target

### 2. Catalog Asset Integration
- Create DataZone catalog asset subscriptions
- Validate access to Glue tables (covid19_db.countries_aggregated, covid19_db.worldwide_aggregate)
- Test subscription idempotency

### 3. MWAA Workflow Deployment
- Deploy Airflow DAG files to MWAA environments
- Validate workflow detection
- Test workflow triggering (requires MWAA support)

### 4. Describe Command Validation
- Test describe with --connect flag
- Validate project details and connection information
- Error handling for invalid configurations

## Expected Behavior

- ✅ Describe should identify all 3 targets (dev, test, prod)
- ✅ Glue databases created with unique names per environment
- ✅ Catalog asset subscriptions created successfully
- ⚠️ MWAA workflow execution requires updated support

## Usage

```bash
# Currently ignored - will be re-enabled after MWAA support updates
python -m pytest tests/integration/glue-mwaa-catalog-app/ -v

# To run despite ignore marker (for development)
python -m pytest tests/integration/glue-mwaa-catalog-app/ -v --run-ignored
```

## TODO

- [ ] Update MWAA workflow execution support
- [ ] Re-enable test after MWAA integration is complete
- [ ] Validate end-to-end workflow execution
