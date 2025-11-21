# SMUS CI/CD Issues Progress

## Issue 1: IAM Role Resolution in QuickSight/Glue Workflows ✅ FIXED

### Problem
- QuickSight workflow failing with Glue job error: `SMUSCICDTestRole` not found
- Root cause: Workflow YAML files uploaded to S3 had hardcoded `SMUSCICDTestRole` instead of resolved `{proj.iam_role_name}` placeholders

### Solution Implemented
- Modified `deploy.py` to resolve all context variables (`{env.*}`, `{proj.*}`, `{domain.*}`, `{stage.*}`) in YAML files before uploading to S3
- Added `_copy_and_resolve_yaml()` function that uses `ContextResolver` during initial deploy
- Variables now resolved at deploy time, not workflow creation time

### Files Changed
- `src/smus_cicd/commands/deploy.py`: Added variable resolution logic
- `tests/test_deploy_yaml_resolution.py`: Added unit tests

### Status
- ✅ Code committed and pushed (commit: eb3d388)
- ✅ Unit tests passing
- ⏳ Waiting for integration test run to verify fix in QuickSight workflow

### Next Steps
- Monitor QuickSight workflow run to confirm Glue jobs use correct IAM role
- Verify resolved YAML in S3 has `AmazonSageMakerUserIAMExecutionRole` instead of `SMUSCICDTestRole`

---

## Issue 2: ML Training Workflow Failures (SEPARATE ISSUE)

### Problem
- ML Training workflow failing during notebook execution
- Training job `orchestrated-training-1763676000` failed with dependency error

### Root Cause
```
ERROR: Could not find a version that satisfies the requirement mlflow==3.5.0rc0
```
- Training code `requirements.txt` specifies `mlflow==3.5.0rc0` (release candidate)
- This version requires Python >=3.10
- Training job uses Python 3.9
- Version `3.5.0rc0` doesn't exist in PyPI for Python 3.9

### Status
- ❌ NOT related to IAM role fix
- ❌ Separate issue in training code dependencies
- 📝 Needs fix in training code `requirements.txt`

### Solution Needed
- Update `requirements.txt` to use stable MLflow version compatible with Python 3.9
- OR update Python version to 3.10+

---

## Current Focus
**Issue 1 (IAM Role)** - Awaiting integration test results to confirm fix works
