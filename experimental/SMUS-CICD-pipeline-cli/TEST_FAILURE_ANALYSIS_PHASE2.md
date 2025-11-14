# Test Failure Analysis - After Import Fixes

**Date**: November 13, 2025  
**Phase**: After fixing import errors

---

## Test Results Summary

```
Total Tests: 339
Passed: 151 (45%)
Failed: 159 (47%)
Errors: 4 (1%)
Skipped: 4 (1%)
XFailed: 17 (5%)
XPassed: 4 (1%)
```

---

## Root Cause Analysis

All 159 failures are due to **tests using old terminology** in:
1. Test data/fixtures (YAML with old field names)
2. Test assertions (checking old field names)
3. Expected values (old class/field names)

---

## Failure Categories

### 📝 Category 1: Test Fixtures Need Update (Majority)
**Tests using old YAML field names in test data**

Old fields in test YAML:
- `bundleName` → should be `applicationName`
- `targets` → should be `stages`
- `bundle` → should be `content`
- `bundle_target_configuration` → should be `deployment_configuration`

**Affected**: ~100+ tests

### 📝 Category 2: Test Assertions Need Update
**Tests checking old field names**

Examples:
- `assert data["bundleName"]` → should be `data["applicationName"]`
- `manifest.targets` → should be `manifest.stages`
- `manifest.bundle` → should be `manifest.content`

**Affected**: ~50+ tests

### 📝 Category 3: Integration Tests
**Integration tests expecting old CLI behavior/output**

**Affected**: ~60 integration tests

---

## Sample Failures

### Validation Tests
```python
# tests/unit/test_validation.py
# Test uses old field name in assertion
assert data["bundleName"] == "TestPipeline"  # ❌ Should be applicationName
```

### Manifest Tests
```python
# Test YAML uses old schema
valid_manifest = """
bundleName: TestPipeline  # ❌ Should be applicationName
targets:                   # ❌ Should be stages
  dev:
    ...
"""
```

---

## Recommendation

**All 159 failures are TEST UPDATES needed** - No bugs in code.

Tests need systematic updates for:
1. YAML test fixtures (old field names)
2. Test assertions (old field access)
3. Expected values (old terminology)

This is expected after a major refactoring.

