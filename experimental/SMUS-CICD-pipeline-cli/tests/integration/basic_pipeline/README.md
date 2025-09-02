# Basic Pipeline Integration Test

This test validates the basic single-target pipeline workflow.

## Files

- `basic_pipeline.yaml` - Pipeline configuration with single dev target
- `test_basic_pipeline.py` - Integration test implementation

## Test Scenarios

### 1. Basic Pipeline Workflow
- Parse pipeline configuration
- Parse with workflows flag
- Parse with targets flag
- Attempt bundle creation
- Monitor pipeline status

### 2. Pipeline Validation
- Valid pipeline file parsing
- Error handling for non-existent files
- Bundle with specific target
- Monitor specific target

### 3. Full Pipeline with Resources (Slow)
- End-to-end workflow with actual AWS resources
- Requires configured DataZone domain and projects

## Expected Behavior

- ✅ Parse commands should always succeed
- ⚠️ Bundle/Monitor may fail if AWS resources don't exist (expected)
- ❌ Unexpected CLI errors indicate bugs

## Usage

```bash
# Run basic pipeline tests
python -m pytest tests/integration/basic_pipeline/ -v

# Run with markers
python -m pytest tests/integration/basic_pipeline/ -m "integration and not slow" -v
```
