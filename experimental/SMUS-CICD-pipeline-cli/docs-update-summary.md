# Documentation Update Summary

## Question
Do any of the markdown docs require updates?

## Answer
**Yes, one documentation file needed updates.** ✅ Fixed

## Files Checked

### ✅ Already Correct
1. **docs/pipeline-manifest.md** - All examples use correct schema format
   - Bundle storage with `name` field ✅
   - `targetDirectory` in bundle_target_configuration ✅
   - No `workflow:` field ✅

2. **Integration test manifests** - All using correct format
   - `tests/integration/multi_target_pipeline/multi_target_pipeline.yaml` ✅
   - Other integration test manifests ✅

3. **README.md** - No manifest examples, only CLI commands ✅

### ❌ Required Updates (Fixed)

**File:** `docs/pipeline-manifest-schema.md`

#### Issue 1: Bundle Configuration
**Old (incorrect):**
```yaml
bundle:
  workflow:                    # ❌ Wrong field name
    - connectionName: default.s3_shared
  storage:
    - connectionName: default.s3_shared  # ❌ Missing 'name' field
```

**New (correct):**
```yaml
bundle:
  storage:                     # ✅ Unified storage (includes workflows)
    - name: code               # ✅ Required 'name' field
      connectionName: default.s3_shared
    - name: workflows          # ✅ Workflows as named storage item
      connectionName: default.s3_shared
```

#### Issue 2: Bundle Target Configuration
**Old (incorrect):**
```yaml
bundle_target_configuration:
  storage:
    connectionName: default.s3_shared
    directory: 'src'           # ❌ Wrong field name, wrong structure
  workflows:                   # ❌ Not allowed here
    connectionName: default.s3_shared
    directory: 'workflows'
```

**New (correct):**
```yaml
bundle_target_configuration:
  storage:
    - name: code               # ✅ Array format with name
      connectionName: default.s3_shared
      targetDirectory: 'src'   # ✅ Correct field name
    - name: workflows
      connectionName: default.s3_shared
      targetDirectory: 'workflows'
```

#### Issue 3: Git Configuration
**Old (incorrect):**
```yaml
git:
  repository: my-repo
  url: https://github.com/user/repo.git
  targetDir: ./src             # ❌ Wrong field name
```

**New (correct):**
```yaml
git:
  repository: my-repo
  url: https://github.com/user/repo.git
  # Note: targetDirectory is only in bundle_target_configuration, not bundle.git
```

## Schema Changes Documented

### 1. Bundle Storage Items
- Now require `name` field
- Workflows are storage items with `name: workflows`
- No separate `workflow:` field

### 2. Bundle Target Configuration
- Must be array format
- Uses `targetDirectory` not `directory`
- No `workflows:` field at this level

### 3. Field Naming
- Bundle level: `storage` (array of items with `name`)
- Target level: `bundle_target_configuration.storage` (array with `targetDirectory`)

## Validation

All documentation examples now:
- ✅ Pass schema validation
- ✅ Match actual implementation
- ✅ Use correct field names
- ✅ Show proper structure

## Files Modified
1. `docs/pipeline-manifest-schema.md` - Updated bundle and bundle_target_configuration examples

## Files Verified Correct
1. `docs/pipeline-manifest.md` - Already correct
2. `README.md` - No manifest examples
3. Integration test manifests - Already correct
4. Other docs - No manifest examples
