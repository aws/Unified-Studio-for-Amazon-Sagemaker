# Documentation Validation Scripts

Scripts to ensure documentation examples remain consistent with the codebase.

## Scripts

### validate_doc_manifests.py

Extracts and validates all complete YAML manifests from documentation files.

**Usage:**
```bash
python tests/scripts/validate_doc_manifests.py
```

**What it checks:**
- ✅ Uses `applicationName` (not outdated `bundleName`)
- ✅ Uses `stages` (not outdated `targets`)
- ✅ Uses `content` section (not outdated `bundle`)
- ✅ Workflows in `content.workflows` (not deprecated `activation`)
- ✅ Stage structure has required `domain.region` and `project.name`

**Exit codes:**
- `0` - All manifests valid
- `1` - Validation errors found

### fix_doc_manifests.py

Auto-fixes common manifest issues in documentation files.

**Usage:**
```bash
python tests/scripts/fix_doc_manifests.py
```

**What it fixes:**
- `bundleName:` → `applicationName:`
- `bundle:` → `content:`
- `activation: workflows:` → `content: workflows:`

### validate_doc_backlinks.py

Validates that all documentation files have back links to main README.

**Usage:**
```bash
python tests/scripts/validate_doc_backlinks.py
```

**Exit codes:**
- `0` - All docs have back links
- `1` - Missing back links

### add_doc_backlinks.py

Adds back links to main README in all documentation files that are missing them.

**Usage:**
```bash
python tests/scripts/add_doc_backlinks.py
```

**What it does:**
- Scans all `.md` files in `docs/`
- Adds `← [Back to Main README](../README.md)` after first heading
- Calculates correct relative path based on file location

## CI Integration

The validation scripts run automatically in CI on every PR and push to main:

```yaml
validate-docs:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    - name: Validate documentation manifests
      run: python tests/scripts/validate_doc_manifests.py
    - name: Validate documentation back links
      run: python tests/scripts/validate_doc_backlinks.py
```

## Development Workflow

1. **Make documentation changes**
2. **Run auto-fix** (optional): 
   ```bash
   python tests/scripts/fix_doc_manifests.py
   python tests/scripts/add_doc_backlinks.py
   ```
3. **Validate**: 
   ```bash
   python tests/scripts/validate_doc_manifests.py
   python tests/scripts/validate_doc_backlinks.py
   ```
4. **Commit** if validation passes

## Notes

- Only validates **complete manifests** (must have both `applicationName` and `stages`)
- Partial YAML snippets are ignored (e.g., showing only a `content:` section)
- Validation focuses on structure, not AWS-specific values
- Back links use relative paths calculated from file location
