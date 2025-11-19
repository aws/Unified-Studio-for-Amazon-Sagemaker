# ML Training Workflow Bug Reproduction

## GitHub Actions Failure
**Run:** https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/19518064784/job/55876433542  
**Branch:** `amirb_feature_branch`  
**Commit:** `9b66600`  
**Date:** 2025-11-19T22:31:23Z

## Observed Behavior

```
❌ Project info not available in context
2025-11-19 22:31:23,497 - smus_cicd.bootstrap.executor - INFO - Successfully executed: workflow.create
2025-11-19 22:31:23,497 - smus_cicd.bootstrap.executor - INFO - Executing bootstrap action: workflow.run
❌ Error: Bootstrap action failed: Workflow 'IntegrationTestMLTraining_test_marketing_ml_training_workflow' not found
```

## Root Cause Analysis

### The Bug Chain

1. **Metadata Collection Returns None**
   - `collect_metadata()` returns `None` when monitoring is disabled
   - This is expected behavior when EventBridge monitoring is not configured

2. **Missing Initialization (Remote Branch)**
   - Remote branch code at commit `9b66600` is missing:
     ```python
     if metadata is None:
         metadata = {}
     ```
   - Without this, metadata remains `None`

3. **Conditional Assignment Prevents project_info**
   - Remote branch has:
     ```python
     if metadata is not None:
         metadata["project_info"] = project_info
     ```
   - Since metadata is `None`, project_info is never added

4. **Handler Fails Silently (Old Code)**
   - Remote branch handler code:
     ```python
     project_info = metadata.get("project_info", {})
     if not project_id or not domain_id:
         typer.echo("❌ Project info not available in context")
         return False  # BUG: Should raise exception
     ```
   - Handler returns `False` instead of raising an exception

5. **Executor Treats False as Success**
   - Executor code:
     ```python
     result = handler(action, context)
     if result is not False:  # BUG: False is treated as success!
         logger.info(f"Successfully executed: {action.type}")
     ```
   - Logs "Successfully executed" even though handler returned `False`

6. **Workflow Not Created**
   - Because handler returned `False`, workflow was never created
   - Next bootstrap action tries to run non-existent workflow
   - Deployment fails with "Workflow not found"

## Code Comparison

### Remote Branch (9b66600) - BUGGY
```python
# deploy.py - Missing initialization
metadata = collect_metadata(...)
# No: if metadata is None: metadata = {}

# Missing project_info assignment
if metadata is not None:  # Skipped when None!
    metadata["project_info"] = project_info

# workflow_create_handler.py - Returns False
if not project_id or not domain_id:
    typer.echo("❌ Project info not available in context")
    return False  # Silent failure
```

### Local Code - FIXED
```python
# deploy.py - Initializes metadata
metadata = collect_metadata(...)
if metadata is None:
    metadata = {}  # Always a dict

# Unconditional assignment
metadata["project_info"] = project_info

# workflow_create_handler.py - Raises exception
if not project_id or not domain_id:
    raise ValueError("Project info not available in context")  # Proper error
```

## Test Reproduction

Created `tests/unit/test_reproduce_ml_training_bug.py` with two tests:

### Test 1: metadata=None causes AttributeError
```python
def test_ml_training_bug_metadata_none_causes_crash():
    context = {"metadata": None}
    # Crashes: AttributeError: 'NoneType' object has no attribute 'get'
    with pytest.raises(AttributeError):
        handle_workflow_create(action, context)
```

This shows what happens when metadata isn't initialized - the handler crashes immediately.

### Test 2: metadata={} raises ValueError (fixed behavior)
```python
def test_ml_training_bug_missing_project_info_raises():
    context = {"metadata": {}}  # Initialized but empty
    # Current local code: Raises ValueError (correct!)
    with pytest.raises(ValueError, match="Project info not available"):
        handle_workflow_create(action, context)
```

This shows the correct behavior after the fix - handler raises a proper exception.

## The Three Bugs

1. **Missing Metadata Initialization**
   - Location: `src/smus_cicd/commands/deploy.py`
   - Fix: Add `if metadata is None: metadata = {}`
   - Status: ✅ Fixed locally, ❌ Missing in remote

2. **Handler Returns False Instead of Raising**
   - Location: `src/smus_cicd/bootstrap/handlers/workflow_create_handler.py`
   - Fix: Change `return False` to `raise ValueError(...)`
   - Status: ✅ Fixed locally, ❌ Old code in remote

3. **Executor Treats False as Success**
   - Location: `src/smus_cicd/bootstrap/executor.py`
   - Fix: Change `if result is not False:` to proper exception handling
   - Status: ❌ Not yet fixed

## Next Steps

1. **Push Complete Fix to Remote**
   - Ensure metadata initialization is in remote branch
   - Ensure handler raises exceptions not returns False
   - Test with workflow trigger

2. **Fix Executor Logic**
   - Handlers should only raise exceptions, never return False
   - Executor should catch exceptions and handle them properly
   - Remove `if result is not False:` logic

3. **Add Integration Test**
   - Test complete deploy flow with monitoring disabled
   - Verify workflows are created successfully
   - Verify proper error messages on actual failures

## Related Documentation

- `q-tasks/bootstrap-handler-errors.md` - Original bug analysis
- `q-tasks/metadata-architecture-improvements.md` - Long-term fixes
- `q-tasks/workflow-failures-analysis.md` - All workflow test results
