# Test Failure Analysis - Phase 2 Step 3

## Summary
- **Total Errors**: 20 collection errors
- **Tests Collected**: 101 tests (but couldn't run due to import errors)
- **Root Cause**: 2 main issues preventing test execution

---

## Error Categories

### 🐛 CATEGORY 1: BUG IN CODE (Critical - Blocking all tests)

**Issue**: Missing module `smus_cicd.commands.content`
- **Error**: `ModuleNotFoundError: No module named 'smus_cicd.commands.content'`
- **Location**: `src/smus_cicd/cli.py:12`
- **Code**: `from .commands.content import bundle_command`
- **Impact**: Blocks 18 test files from loading

**Root Cause**: The `cli.py` file imports `bundle_command` from a non-existent module `commands.content`. This module was likely renamed or the import wasn't updated during refactoring.

**Affected Test Files** (18):
1. tests/integration/conftest.py
2. tests/test_json_output.py
3. tests/unit/commands/test_monitor_command.py
4. tests/unit/commands/test_run_command.py
5. tests/unit/commands/test_test_command.py
6. tests/unit/test_bundle.py
7. tests/unit/test_create.py
8. tests/unit/test_delete.py
9. tests/unit/test_describe.py
10. tests/unit/test_describe_comprehensive.py
11. tests/unit/test_describe_new_features.py
12. tests/unit/test_json_output.py
13. tests/unit/test_monitor.py
14. tests/unit/test_run.py
15. tests/unit/test_temp_directories.py
16. tests/unit/test_test_command.py

**Fix Required**: 
- Check if `commands/content.py` exists or was renamed
- Update import in `cli.py` to correct module name
- OR remove the import if `bundle_command` is no longer used

---

### 📝 CATEGORY 2: TESTS NEED UPDATE (Import paths changed)

**Issue**: Tests importing from old `smus_cicd.pipeline` module
- **Error**: `ModuleNotFoundError: No module named 'smus_cicd.pipeline'`
- **Root Cause**: Module was renamed from `pipeline` to `application`
- **Impact**: Blocks 4 test files

**Affected Test Files** (4):
1. tests/unit/helpers/test_monitoring.py
   - Line 13: `from smus_cicd.pipeline import BundleManifest`
   
2. tests/unit/test_manifest_monitoring.py
   - Line 5: `from smus_cicd.pipeline import BundleManifest`
   
3. tests/unit/test_region_config.py
   - Line 7: `from smus_cicd.pipeline import BundleManifest`
   
4. tests/unit/test_validation.py
   - Line 9: `from smus_cicd.pipeline.validation import (...)`

**Fix Required**:
- Update imports: `smus_cicd.pipeline` → `smus_cicd.application`
- Update class names: `BundleManifest` → `ApplicationManifest`

---

## Detailed Breakdown

### Files Requiring Code Fixes (1 file)
```
src/smus_cicd/cli.py
  Line 12: from .commands.content import bundle_command
  → Need to verify if commands/content.py exists or update import
```

### Files Requiring Test Updates (4 files)

#### 1. tests/unit/helpers/test_monitoring.py
```python
# Line 13 - BEFORE:
from smus_cicd.pipeline import BundleManifest

# AFTER:
from smus_cicd.application import ApplicationManifest
```

#### 2. tests/unit/test_manifest_monitoring.py
```python
# Line 5 - BEFORE:
from smus_cicd.pipeline import BundleManifest

# AFTER:
from smus_cicd.application import ApplicationManifest
```

#### 3. tests/unit/test_region_config.py
```python
# Line 7 - BEFORE:
from smus_cicd.pipeline import BundleManifest

# AFTER:
from smus_cicd.application import ApplicationManifest
```

#### 4. tests/unit/test_validation.py
```python
# Line 9 - BEFORE:
from smus_cicd.pipeline.validation import (...)

# AFTER:
from smus_cicd.application.validation import (...)
```

---

## Priority Order

### 🔴 CRITICAL (Must fix first)
1. **Fix `cli.py` import** - This blocks 18 test files (90% of failures)
   - Investigate `commands/content.py` or `bundle_command` usage
   - Either fix the import or remove if obsolete

### 🟡 MEDIUM (Fix after critical)
2. **Update test imports** - 4 test files need import path updates
   - Simple search/replace: `pipeline` → `application`
   - Update class names: `BundleManifest` → `ApplicationManifest`

---

## Expected Test Updates After Fixes

Once imports are fixed, tests will likely need updates for:
- Field name changes: `bundle_name` → `application_name`
- Field name changes: `targets` → `stages`
- Field name changes: `bundle` → `content`
- Method name changes: `get_target()` → `get_stage()`
- Test data/fixtures using old terminology

---

## Recommendation

**Step 1**: Fix the critical bug in `cli.py` (commands.content import)
**Step 2**: Update 4 test files with new import paths
**Step 3**: Run tests again to identify remaining test-specific updates needed
**Step 4**: Update test assertions and fixtures for new terminology

