# Documentation Link Fixes

## Summary
Fixed all broken internal documentation links. The issue was that links referenced non-existent subdirectories (`docs/guides/`, `docs/reference/`, `docs/concepts/`, `docs/examples/`) when files were actually in `docs/` root.

## Files Updated

### 1. README.new.md
- ✅ Fixed: `docs/reference/airflow-aws-operators.md` → `docs/airflow-aws-operators.md`
- ✅ Fixed: `docs/guides/pipeline-manifest.md` → `docs/pipeline-manifest.md`
- ✅ Fixed: `docs/guides/cli-commands.md` → `docs/cli-commands.md`
- ✅ Fixed: `docs/guides/substitutions-and-variables.md` → `docs/substitutions-and-variables.md`
- ✅ Fixed: `docs/guides/github-actions-integration.md` → `docs/github-actions-integration.md`
- ✅ Fixed: `docs/reference/pipeline-manifest-schema.md` → `docs/pipeline-manifest-schema.md`
- ✅ Removed: Non-existent concept pages (pipeline-architecture, bundle-management, catalog-integration)
- ✅ Removed: Non-existent example pages (simple-pipeline, multi-environment, advanced-features)
- ✅ Updated: Examples section now points to actual example directories

### 2. docs/getting-started/quickstart.md
- ✅ Fixed: All `../guides/` references → `../` (direct docs/ references)
- ✅ Fixed: All `../reference/` references → `../` (direct docs/ references)
- ✅ Removed: `../guides/installation.md` (doesn't exist)
- ✅ Removed: `../guides/catalog-integration.md` → replaced with pipeline-manifest.md anchor
- ✅ Removed: Non-existent example pages → replaced with `../../examples/` directory reference

### 3. docs/getting-started/admin-quickstart.md
- ✅ Fixed: All `../guides/` references → `../` (direct docs/ references)
- ✅ Fixed: All `../reference/` references → `../` (direct docs/ references)
- ✅ Removed: `../guides/troubleshooting.md` (doesn't exist)
- ✅ Removed: Non-existent example pages → replaced with `../../examples/` directory reference

## Actual File Structure

```
docs/
├── airflow-aws-operators.md          ✓ exists
├── cli-commands.md                    ✓ exists
├── development.md                     ✓ exists
├── github-actions-integration.md      ✓ exists
├── pipeline-architecture-diagram.md   ✓ exists
├── pipeline-manifest-schema.md        ✓ exists
├── pipeline-manifest.md               ✓ exists
├── pypi-publishing.md                 ✓ exists
├── substitutions-and-variables.md     ✓ exists
└── getting-started/
    ├── README.md                      ✓ exists
    ├── quickstart.md                  ✓ exists
    └── admin-quickstart.md            ✓ exists

examples/
├── analytic-workflow/
│   ├── etl/                           ✓ exists
│   └── ml/                            ✓ exists
├── serverless-example/                ✓ exists
└── mwaa-example/                      ✓ exists
```

## Verification

All internal documentation links now point to existing files or directories. External links (https://) were not modified.

Run this to verify:
```bash
cd /Users/amirbo/code/smus/experimental/SMUS-CICD-pipeline-cli
grep -r "\](docs/" docs/getting-started/*.md README.new.md | grep -v "https://"
```

All links should resolve to actual files in the repository.
