# Schema Validation Summary: targetDirectory

## Question
Should `targetDirectory` be allowed under `bundle.storage`?

## Answer
**No, and it is correctly NOT allowed.** ✅

## Schema Configuration

### 1. Bundle Storage Items (`bundle.storage`)
**Schema Definition:** `bundleStorageItem`
**Location:** Top-level `bundle.storage` array

**Allowed Properties:**
- `name` (required)
- `connectionName` (required)
- `append` (optional)
- `include` (optional)
- `exclude` (optional)

**NOT Allowed:**
- ❌ `targetDirectory` - Correctly rejected by schema

**Reason:** Bundle storage items define what to bundle from the source. They don't need a target directory because they're not being deployed yet.

### 2. Bundle Target Configuration (`targets.*.bundle_target_configuration.storage`)
**Schema Definition:** `bundleTargetStorageItem`
**Location:** Per-target deployment configuration

**Required Properties:**
- `name` (required)
- `connectionName` (required)
- `targetDirectory` (required) ✅

**Reason:** Target configuration defines WHERE to deploy the bundled items. The `targetDirectory` specifies the destination path on the target connection.

## Validation Tests

### Test 1: Reject targetDirectory under bundle.storage
```yaml
bundle:
  storage:
    - name: code
      connectionName: default.s3_shared
      targetDirectory: src  # ❌ Should be rejected
```
**Result:** ✅ PASS - Correctly rejected with error:
```
Additional properties are not allowed ('targetDirectory' was unexpected)
```

### Test 2: Require targetDirectory under bundle_target_configuration
```yaml
targets:
  dev:
    bundle_target_configuration:
      storage:
        - name: code
          connectionName: default.s3_shared
          # Missing targetDirectory
```
**Result:** ✅ PASS - Correctly rejected as required field missing

### Test 3: Accept targetDirectory under bundle_target_configuration
```yaml
targets:
  dev:
    bundle_target_configuration:
      storage:
        - name: code
          connectionName: default.s3_shared
          targetDirectory: src  # ✅ Correct usage
```
**Result:** ✅ PASS - Correctly accepted

## Schema Enforcement

Both schemas have `additionalProperties: false` which ensures:
1. No unexpected properties can be added
2. Typos are caught at validation time
3. Clear separation between bundle definition and deployment configuration

## Conclusion

The schema is correctly configured:
- `targetDirectory` is NOT allowed under `bundle.storage` ✅
- `targetDirectory` IS required under `bundle_target_configuration.storage` ✅
- Schema validation properly enforces these rules ✅
