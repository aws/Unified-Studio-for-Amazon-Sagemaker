# DataZone Connections Pipeline Integration Test

This test validates DataZone connections integration in the CICD pipeline.

## Test Coverage

### Connection Types Tested (6/8 working types)
✅ **S3** - Object storage  
✅ **IAM** - Identity and access management  
✅ **SPARK_GLUE** - Spark on AWS Glue  
✅ **ATHENA** - SQL query engine  
✅ **REDSHIFT** - Data warehouse  
✅ **SPARK_EMR** - Spark on EMR  

### Test Cases

1. **test_connections_pipeline_describe**
   - Tests `describe --pipeline` shows all 6 connection types
   - Validates connection names and types appear in output

2. **test_connections_pipeline_describe_connect_flag**
   - Tests `describe --pipeline --connect` flag
   - Validates focused connections output

3. **test_connections_pipeline_validation**
   - Tests bundle manifest validation with connections
   - Ensures no validation errors

4. **test_connections_pipeline_end_to_end** (slow)
   - Tests full workflow: validate → create → describe → cleanup
   - Validates connections persist through deployment

## Pipeline Manifest

The test uses `connections_pipeline.yaml` with:
- Single test target
- All 6 working connection types in initialization section
- Realistic connection properties based on API validation

## Running Tests

```bash
# Run all connection tests
pytest tests/integration/connections_pipeline/ -v

# Run specific test
pytest tests/integration/connections_pipeline/test_connections_pipeline.py::TestConnectionsPipeline::test_connections_pipeline_describe -v

# Skip slow tests
pytest tests/integration/connections_pipeline/ -v -m "not slow"
```

## Expected Output

The CLI describe command should show:
- Pipeline name: ConnectionsTestPipeline
- Connections section with all 6 connection types
- Connection names and properties
- No validation errors
