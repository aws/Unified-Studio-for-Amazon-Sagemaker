# Helper Refactoring Plan: Shared Workflow Logic

## Goal
Move duplicated workflow logic from commands and WorkflowOperations into helpers so both can share the same tested code.

---

## Current Duplication

### 1. Workflow Name Generation (4 places)
- `deploy.py:1669-1672`
- `run.py:561-563`
- `workflows/operations.py:40-42`
- `workflows/operations.py:151-153`

```python
# Duplicated in 4 places:
safe_pipeline = bundle_name.replace("-", "_")
safe_dag = dag_name.replace("-", "_")
expected_workflow_name = f"{safe_pipeline}_{stage_name}_{safe_dag}"
```

### 2. Workflow ARN Lookup (3 places)
- `run.py:565-577`
- `workflows/operations.py:45-56`
- `workflows/operations.py:155-166`

```python
# Duplicated in 3 places:
workflows = airflow_serverless.list_workflows(region=region)
workflow_arn = None
for wf in workflows:
    if wf["name"] == expected_workflow_name:
        workflow_arn = wf["workflow_arn"]
        break

if not workflow_arn:
    raise Exception(f"Workflow '{expected_workflow_name}' not found...")
```

### 3. Workflow Start Verification (only in run.py)
- `run.py:590-620` - **TESTED LOGIC** ✅

```python
# Only in run.py - should be in helper:
if initial_status not in ["STARTING", "QUEUED", "RUNNING"]:
    time.sleep(10)
    status_check = airflow_serverless.get_workflow_status(workflow_arn, region=region)
    current_status = status_check.get("status") if status_check.get("success") else initial_status
    
    if current_status not in ["STARTING", "QUEUED", "RUNNING"]:
        raise Exception("Workflow may not have actually started")
```

### 4. DataZone Connection Type Detection (only in monitor.py)
- `monitor.py:420-475` - **TESTED LOGIC** ✅

```python
# Only in monitor.py - should be in helper:
def _target_uses_airflow_serverless(manifest, target_config) -> bool:
    # Queries DataZone
    # Handles WORKFLOWS_MWAA bug
    # Checks physicalEndpoints for MWAA ARN
```

---

## Proposed Helper Functions

### Add to `helpers/airflow_serverless.py`:

```python
def generate_workflow_name(
    bundle_name: str,
    project_name: str,
    dag_name: str
) -> str:
    """
    Generate standardized workflow name.
    
    Args:
        bundle_name: Application/bundle name
        project_name: Project name
        dag_name: DAG/workflow name
    
    Returns:
        Formatted workflow name: {bundle}_{project}_{dag}
    """
    safe_pipeline = bundle_name.replace("-", "_")
    safe_project = project_name.replace("-", "_")
    safe_dag = dag_name.replace("-", "_")
    return f"{safe_pipeline}_{safe_project}_{safe_dag}"


def find_workflow_arn(
    workflow_name: str,
    region: str,
    connection_info: Dict[str, Any] = None
) -> str:
    """
    Find workflow ARN by name.
    
    Args:
        workflow_name: Name of workflow to find
        region: AWS region
        connection_info: Optional connection info
    
    Returns:
        Workflow ARN
    
    Raises:
        Exception: If workflow not found
    """
    workflows = list_workflows(region=region, connection_info=connection_info)
    
    for wf in workflows:
        if wf["name"] == workflow_name:
            return wf["workflow_arn"]
    
    available = [wf["name"] for wf in workflows]
    raise Exception(
        f"Workflow '{workflow_name}' not found. "
        f"Available workflows: {available}"
    )


def start_workflow_run_verified(
    workflow_arn: str,
    region: str,
    run_name: str = None,
    connection_info: Dict[str, Any] = None,
    verify_started: bool = True,
    wait_seconds: int = 10
) -> Dict[str, Any]:
    """
    Start workflow run and optionally verify it actually started.
    
    This is the TESTED logic from run.py that ensures the workflow
    actually transitions to a running state, not just API success.
    
    Args:
        workflow_arn: Workflow ARN
        region: AWS region
        run_name: Optional run name
        connection_info: Optional connection info
        verify_started: Whether to verify workflow started (default: True)
        wait_seconds: Seconds to wait before verification (default: 10)
    
    Returns:
        Dict with run_id, status, workflow_arn, success
    
    Raises:
        Exception: If workflow fails to start or verification fails
    """
    logger = get_logger("airflow_serverless")
    
    # Start the workflow
    result = start_workflow_run(
        workflow_arn=workflow_arn,
        run_name=run_name,
        connection_info=connection_info,
        region=region
    )
    
    if not result.get("success"):
        raise Exception(f"Failed to start workflow: {result.get('error')}")
    
    run_id = result.get("run_id")
    initial_status = result.get("status")
    
    # Optionally verify workflow actually started
    if verify_started:
        logger.info(f"Verifying workflow started (initial status: {initial_status})")
        
        # Valid running states
        running_states = ["STARTING", "QUEUED", "RUNNING"]
        
        if initial_status not in running_states:
            logger.info(f"Waiting {wait_seconds}s before re-checking status...")
            time.sleep(wait_seconds)
            
            # Re-check status
            status_check = get_workflow_status(
                workflow_arn=workflow_arn,
                connection_info=connection_info,
                region=region
            )
            
            current_status = (
                status_check.get("status") 
                if status_check.get("success") 
                else initial_status
            )
            
            if current_status not in running_states:
                raise Exception(
                    f"Workflow run started but status is '{current_status}' "
                    f"(expected {running_states}). "
                    f"The workflow may not have actually started."
                )
            
            logger.info(f"✓ Verified workflow status: {current_status}")
            result["status"] = current_status
    
    return result


def get_workflow_logs(
    workflow_arn: str,
    run_id: str,
    region: str,
    max_lines: int = 100,
    connection_info: Dict[str, Any] = None
) -> List[str]:
    """
    Get workflow logs for a specific run.
    
    Args:
        workflow_arn: Workflow ARN
        run_id: Run ID
        region: AWS region
        max_lines: Maximum number of log lines
        connection_info: Optional connection info
    
    Returns:
        List of log lines
    """
    # Extract workflow name and construct log group
    workflow_name = workflow_arn.split("/")[-1]
    log_group = f"/aws/mwaa-serverless/{workflow_name}/"
    
    log_events = get_cloudwatch_logs(
        log_group=log_group,
        region=region,
        limit=max_lines
    )
    
    # Format log events as strings
    formatted_logs = []
    for event in log_events:
        timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(event["timestamp"] / 1000)
        )
        stream = event.get("log_stream_name", "unknown")
        message = event["message"]
        formatted_logs.append(f"[{timestamp}] [{stream}] {message}")
    
    return formatted_logs
```

### Add to `helpers/datazone.py`:

```python
def is_connection_serverless_airflow(
    connection_name: str,
    domain_id: str,
    project_id: str,
    region: str
) -> bool:
    """
    Check if a DataZone connection is serverless Airflow.
    
    This handles the DataZone bug where both serverless and MWAA
    connections have type WORKFLOWS_MWAA. We distinguish by checking
    if physicalEndpoints contains a MWAA ARN.
    
    Args:
        connection_name: Connection name to check
        domain_id: DataZone domain ID
        project_id: DataZone project ID
        region: AWS region
    
    Returns:
        True if connection is serverless Airflow, False otherwise
    """
    import boto3
    
    try:
        client = boto3.client("datazone", region_name=region)
        response = client.list_connections(
            domainIdentifier=domain_id,
            projectIdentifier=project_id
        )
        
        for conn in response.get("items", []):
            if conn["name"] == connection_name:
                # Check if it's a workflow connection
                if conn["type"] == "WORKFLOWS_MWAA":
                    # CRITICAL: Check physicalEndpoints for MWAA ARN
                    # Serverless: type=WORKFLOWS_MWAA WITHOUT MWAA ARN
                    # MWAA: type=WORKFLOWS_MWAA WITH MWAA ARN
                    physical_endpoints = conn.get("physicalEndpoints", [])
                    has_mwaa_arn = any(
                        "glueConnection" in ep
                        and "arn:aws:airflow" in str(ep.get("glueConnection", ""))
                        for ep in physical_endpoints
                    )
                    # If no MWAA ARN, it's serverless
                    return not has_mwaa_arn
        
        return False
        
    except Exception:
        return False


def target_uses_serverless_airflow(
    manifest,
    target_config
) -> bool:
    """
    Check if a target uses serverless Airflow workflows.
    
    This is the TESTED logic from monitor.py that properly detects
    serverless Airflow by querying DataZone at runtime.
    
    Args:
        manifest: Application manifest
        target_config: Target configuration
    
    Returns:
        True if target uses serverless Airflow, False otherwise
    """
    if not hasattr(manifest.content, "workflows") or not manifest.content.workflows:
        return False
    
    region = target_config.domain.region
    project_name = target_config.project.name
    
    try:
        # Resolve domain and project IDs
        domain_id, _ = resolve_domain_id(
            target_config.domain.name,
            (
                target_config.domain.tags
                if hasattr(target_config.domain, "tags")
                else None
            ),
            region,
        )
        
        if not domain_id:
            return False
        
        project_id = get_project_id_by_name(project_name, domain_id, region)
        if not project_id:
            return False
        
        # Check each workflow's connection
        for workflow in manifest.content.workflows:
            conn_name = workflow.get("connectionName", "")
            if conn_name:
                if is_connection_serverless_airflow(
                    conn_name, domain_id, project_id, region
                ):
                    return True
        
        return False
        
    except Exception:
        return False
```

---

## Refactoring Steps

### Phase 1: Add Helper Functions (No Breaking Changes)
1. Add `generate_workflow_name()` to `airflow_serverless.py`
2. Add `find_workflow_arn()` to `airflow_serverless.py`
3. Add `start_workflow_run_verified()` to `airflow_serverless.py`
4. Add `get_workflow_logs()` to `airflow_serverless.py`
5. Add `is_connection_serverless_airflow()` to `datazone.py`
6. Add `target_uses_serverless_airflow()` to `datazone.py`
7. Run all tests to ensure helpers work

### Phase 2: Update WorkflowOperations (Bootstrap Actions)
1. Replace duplicated logic with helper calls
2. Add verification to `trigger_workflow()` using `start_workflow_run_verified()`
3. Update `fetch_logs()` to use `get_workflow_logs()`
4. Update `get_workflow_status()` to use helper functions
5. Run bootstrap action tests

### Phase 3: Update CLI Commands (Optional)
1. Update `run.py` to use helpers
2. Update `monitor.py` to use helpers
3. Update `logs.py` to use helpers
4. Update `deploy.py` to use helpers
5. Run integration tests

---

## Benefits

1. **Single Source of Truth**: Workflow logic in one place
2. **Tested Logic Preserved**: CLI command logic moves to helpers
3. **Easy Maintenance**: Fix bugs once, benefits all callers
4. **Consistent Behavior**: Commands and bootstrap actions work identically
5. **Better Testing**: Test helpers independently
6. **No Breaking Changes**: Helpers are additive, existing code works

---

## Testing Strategy

1. **Unit Tests**: Test each helper function independently
2. **Integration Tests**: Verify commands still work
3. **Bootstrap Tests**: Verify actions still work
4. **Comparison Tests**: Ensure helpers produce same results as old code

---

## Priority Functions to Add First

1. ✅ `generate_workflow_name()` - Used everywhere
2. ✅ `find_workflow_arn()` - Used everywhere
3. ✅ `start_workflow_run_verified()` - Critical for reliability
4. ✅ `target_uses_serverless_airflow()` - Critical for detection
5. ⚠️ `get_workflow_logs()` - Nice to have
6. ⚠️ `is_connection_serverless_airflow()` - Nice to have

---

## Example Usage After Refactoring

### WorkflowOperations (simplified):
```python
def trigger_workflow(manifest, target_config, workflow_name, wait=False, region=None):
    region = region or target_config.domain.region
    
    # Use helpers
    full_workflow_name = airflow_serverless.generate_workflow_name(
        bundle_name=manifest.application_name,
        project_name=target_config.project.name,
        dag_name=workflow_name
    )
    
    workflow_arn = airflow_serverless.find_workflow_arn(
        workflow_name=full_workflow_name,
        region=region
    )
    
    result = airflow_serverless.start_workflow_run_verified(
        workflow_arn=workflow_arn,
        region=region,
        verify_started=True  # Use tested verification logic
    )
    
    return result
```

### CLI Commands (simplified):
```python
# run.py - same helper usage
full_workflow_name = airflow_serverless.generate_workflow_name(
    bundle_name=manifest.application_name,
    project_name=target_config.project.name,
    dag_name=workflow
)

workflow_arn = airflow_serverless.find_workflow_arn(
    workflow_name=full_workflow_name,
    region=region
)

result = airflow_serverless.start_workflow_run_verified(
    workflow_arn=workflow_arn,
    region=region
)
```

Both use the same tested, reliable code!
