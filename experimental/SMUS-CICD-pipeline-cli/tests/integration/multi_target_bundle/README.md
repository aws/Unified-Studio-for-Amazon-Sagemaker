# Multi-Target Pipeline Integration Test

This test validates the multi-target pipeline workflow with dev, test, and prod environments.

## Files

- `multi_target_pipeline.yaml` - Pipeline configuration with multiple targets
- `test_multi_target_pipeline.py` - Integration test implementation

## Test Scenarios

### 1. Multi-Target Describe
- Describe pipeline with multiple targets
- Verify all targets (dev, test, prod) are present

### 2. Target Specific Operations
- Bundle creation for each target individually
- Monitor each target individually
- Validate target-specific output

### 3. Pipeline Workflow Comparison
- Compare basic vs multi-target pipeline behavior
- Validate target count differences

### 4. Sequential Target Deployment (Slow)
- Deploy to targets in sequence (dev → test)
- Monitor all targets after deployment
- Skip prod for safety

## Expected Behavior

- ✅ Describe should identify all 3 targets
- ⚠️ Bundle/Monitor may fail per target if resources don't exist
- ✅ Target-specific commands should reference correct target

## Usage

```bash
# Run multi-target pipeline tests
python -m pytest tests/integration/multi_target_pipeline/ -v

# Run specific test
python -m pytest tests/integration/multi_target_pipeline/test_multi_target_pipeline.py::TestMultiTargetPipeline::test_multi_target_describe -v
```
