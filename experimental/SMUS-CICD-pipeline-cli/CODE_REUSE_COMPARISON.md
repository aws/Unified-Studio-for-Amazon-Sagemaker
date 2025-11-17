# Code Reuse Comparison: CLI Commands vs WorkflowOperations

## Summary
The CLI commands contain **tested and validated logic** that is NOT currently used by `WorkflowOperations`. The new bootstrap handlers use simplified logic that may be missing important features.

---

## 1. Workflow Triggering (run command)

### CLI Command Logic (run.py) - TESTED ✅
```python
# Lines 550-650
# Generate expected workflow name
bundle_name = manifest.application_name
dag_name = workflow
stage_name = target_config.project.name.replace("-", "_")
safe_pipeline = bundle_name.replace("-", "_")
safe_dag = dag_name.replace("-", "_")
expected_workflow_name = f"{safe_pipeline}_{stage_name}_{safe_dag}"

# Use target's region (not hardcoded)
region = target_config.domain.region

# List workflows and find ARN
workflows = airflow_serverless.list_workflows(region=region)
workflow_arn = None
for wf in workflows:
    if wf["name"] == expected_workflow_name:
        workflow_arn = wf["workflow_arn"]
        break

if not workflow_arn:
    raise Exception(
        f"Workflow '{expected_workflow_name}' not found. "
        f"Available workflows: {[wf['name'] for wf in workflows]}"
    )

# Start workflow run
result = airflow_serverless.start_workflow_run(workflow_arn, region=region)

# IMPORTANT: Verify workflow actually started
if result.get("success"):
    run_id = result.get("run_id")
    initial_status = result.get("status")
    
    # Verify workflow transitioned from READY state
    if initial_status not in ["STARTING", "QUEUED", "RUNNING"]:
        # Wait and check again
        time.sleep(10)
        status_check = airflow_serverless.get_workflow_status(
            workflow_arn, region=region
        )
        current_status = status_check.get("status") if status_check.get("success") else initial_status
        
        if current_status not in ["STARTING", "QUEUED", "RUNNING"]:
            error_msg = (
                f"Workflow run started but status is '{current_status}' "
                f"(expected STARTING, QUEUED, or RUNNING). "
                f"The workflow may not have actually started."
            )
            raise Exception(error_msg)
```

**Key Features:**
- ✅ Proper workflow name generation with safe character replacement
- ✅ Uses target's region (not hardcoded)
- ✅ Lists all workflows and finds matching ARN
- ✅ Provides helpful error with available workflows
- ✅ **Verifies workflow actually started** (not just API success)
- ✅ Waits 10 seconds and re-checks status
- ✅ Validates status is in expected running states

### WorkflowOperations Logic - NEW ⚠️
```python
# Lines 13-65 in workflows/operations.py
region = region or target_config.domain.region

# Generate expected workflow name
bundle_name = manifest.application_name
project_name = target_config.project.name.replace("-", "_")
safe_pipeline = bundle_name.replace("-", "_")
safe_dag = workflow_name.replace("-", "_")
expected_workflow_name = f"{safe_pipeline}_{project_name}_{safe_dag}"

# Find workflow ARN
workflows = airflow_serverless.list_workflows(region=region)
workflow_arn = None
for wf in workflows:
    if wf["name"] == expected_workflow_name:
        workflow_arn = wf["workflow_arn"]
        break

if not workflow_arn:
    available = [wf["name"] for wf in workflows]
    raise Exception(
        f"Workflow '{expected_workflow_name}' not found. Available: {available}"
    )

# Start workflow run
result = airflow_serverless.start_workflow_run(workflow_arn, region=region)

if not result.get("success"):
    raise Exception(f"Failed to start workflow: {result.get('error')}")

return {
    "success": True,
    "run_id": result.get("run_id"),
    "status": result.get("status"),
    "workflow_arn": workflow_arn,
    "workflow_name": expected_workflow_name,
}
```

**Missing Features:**
- ❌ **No verification that workflow actually started**
- ❌ No status validation (STARTING/QUEUED/RUNNING)
- ❌ No retry/wait logic
- ❌ Could return success even if workflow didn't start

---

## 2. Workflow Monitoring (monitor command)

### CLI Command Logic (monitor.py) - TESTED ✅
```python
# Lines 420-475
def _target_uses_airflow_serverless(manifest, target_config) -> bool:
    """Check if target uses serverless Airflow by querying DataZone."""
    if hasattr(manifest.content, "workflows") and manifest.content.workflows:
        region = target_config.domain.region
        project_name = target_config.project.name
        
        # Resolve domain and project IDs
        domain_id, _ = resolve_domain_id(
            target_config.domain.name,
            target_config.domain.tags if hasattr(target_config.domain, "tags") else None,
            region,
        )
        
        if not domain_id:
            return False
        
        project_id = get_project_id_by_name(project_name, domain_id, region)
        if not project_id:
            return False
        
        # Query DataZone connections
        client = boto3.client("datazone", region_name=region)
        response = client.list_connections(
            domainIdentifier=domain_id, projectIdentifier=project_id
        )
        
        # Check each workflow's connection type
        for workflow in manifest.content.workflows:
            conn_name = workflow.get("connectionName", "")
            for conn in response.get("items", []):
                if conn["name"] == conn_name and conn["type"] == "WORKFLOWS_MWAA":
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
                    if not has_mwaa_arn:
                        return True
    return False
```

**Key Features:**
- ✅ Queries DataZone at runtime (not naming conventions)
- ✅ Resolves domain and project IDs properly
- ✅ **Handles DataZone bug**: WORKFLOWS_MWAA type for both serverless and MWAA
- ✅ Checks physicalEndpoints for MWAA ARN to distinguish
- ✅ Tested and validated in integration tests

### CLI Command Monitoring Logic (monitor.py) - TESTED ✅
```python
# Lines 500-600
# Filter workflows by tags
bundle_name = manifest.application_name
stage_name = target_config.project.name

relevant_workflows = []
for workflow in all_workflows:
    workflow_tags = workflow.get("tags", {})
    # Check if workflow tags match pipeline and target
    if (
        workflow_tags.get("Pipeline") == bundle_name
        and workflow_tags.get("Target") == stage_name
    ):
        relevant_workflows.append(workflow)

# Get workflow details and recent runs
for workflow in relevant_workflows:
    workflow_arn = workflow["workflow_arn"]
    workflow_name = workflow["name"]
    
    # Get workflow status
    workflow_status = airflow_serverless.get_workflow_status(
        workflow_arn, region=config.get("region")
    )
    
    # Get recent runs
    recent_runs = airflow_serverless.list_workflow_runs(
        workflow_arn, region=config.get("region"), max_results=1
    )
    
    # Extract run details
    if recent_runs:
        latest_run = recent_runs[0]
        run_id = latest_run.get("run_id", "N/A")
        run_status = latest_run.get("RunDetailSummary", {}).get("Status")
        
        # Handle None status (initializing)
        if run_status is None:
            run_status = "INITIALIZING"
        
        # Calculate duration
        started_at = latest_run.get("started_at")
        ended_at = latest_run.get("ended_at")
        
        if started_at and ended_at:
            duration_seconds = (ended_at - started_at).total_seconds()
            hours = int(duration_seconds // 3600)
            minutes = int((duration_seconds % 3600) // 60)
            duration = f"{hours}h {minutes}m"
```

**Key Features:**
- ✅ Filters workflows by Pipeline and Target tags
- ✅ Gets both workflow status and recent runs
- ✅ Handles None status as INITIALIZING
- ✅ Calculates duration for completed runs
- ✅ Formats output nicely

### WorkflowOperations.get_workflow_status() - NEW ⚠️
```python
# Lines 125-169 in workflows/operations.py
region = region or target_config.domain.region

# Generate expected workflow name
bundle_name = manifest.application_name
project_name = target_config.project.name.replace("-", "_")
safe_pipeline = bundle_name.replace("-", "_")
safe_dag = workflow_name.replace("-", "_")
expected_workflow_name = f"{safe_pipeline}_{project_name}_{safe_dag}"

# Find workflow ARN
workflows = airflow_serverless.list_workflows(region=region)
workflow_arn = None
for wf in workflows:
    if wf["name"] == expected_workflow_name:
        workflow_arn = wf["workflow_arn"]
        break

if not workflow_arn:
    return {"success": False, "error": f"Workflow '{expected_workflow_name}' not found"}

# Get recent runs
runs = airflow_serverless.list_workflow_runs(workflow_arn, region=region)

return {
    "success": True,
    "workflow_arn": workflow_arn,
    "workflow_name": expected_workflow_name,
    "runs": runs[:5] if runs else [],  # Last 5 runs
}
```

**Missing Features:**
- ❌ No workflow status check (only runs)
- ❌ No duration calculation
- ❌ No INITIALIZING status handling
- ❌ No tag-based filtering
- ❌ Returns raw runs without formatting

---

## 3. Log Fetching (logs command)

### CLI Command Logic (logs.py) - TESTED ✅
```python
# Lines 150-250
def _fetch_static_logs(workflow_arn, region, output, lines, config):
    """Fetch static logs for a workflow."""
    # Extract workflow name and construct log group
    workflow_name = workflow_arn.split("/")[-1]
    log_group = f"/aws/mwaa-serverless/{workflow_name}/"
    
    log_events = airflow_serverless.get_cloudwatch_logs(
        log_group, region=region, limit=lines
    )
    
    if output.upper() == "JSON":
        output_data = {
            "workflow_arn": workflow_arn,
            "log_events": log_events,
            "total_events": len(log_events),
        }
        typer.echo(json.dumps(output_data, indent=2, default=str))
    else:
        if log_events:
            typer.echo(f"📄 Showing {len(log_events)} log events:")
            for event in log_events:
                timestamp = time.strftime(
                    "%Y-%m-%d %H:%M:%S", 
                    time.localtime(event["timestamp"] / 1000)
                )
                stream = event.get("log_stream_name", "unknown")
                message = event["message"]
                typer.echo(f"[{timestamp}] [{stream}] {message}")

def _live_log_monitoring(workflow_arn, region, output, config):
    """Continuously monitor workflow logs until completion."""
    workflow_name = workflow_arn.split("/")[-1]
    log_group = f"/aws/mwaa-serverless/{workflow_name}/"
    
    last_timestamp = None
    
    while True:
        # Get current workflow runs
        runs = airflow_serverless.list_workflow_runs(
            workflow_arn, region=region, max_results=5
        )
        
        # Check for active vs completed runs
        active_runs = []
        terminal_statuses = {"SUCCESS", "FAILED", "STOPPED", "COMPLETED"}
        
        for run in runs:
            status = run.get("RunDetailSummary", {}).get("Status")
            ended_at = run.get("ended_at")
            
            if status not in terminal_statuses and not ended_at:
                active_runs.append(run)
        
        # Fetch new logs since last_timestamp
        # ... streaming logic ...
```

**Key Features:**
- ✅ Constructs proper CloudWatch log group path
- ✅ Formats timestamps nicely
- ✅ Shows log stream names
- ✅ Supports both static and live monitoring
- ✅ Checks for terminal statuses
- ✅ Streams logs continuously with timestamp tracking

### WorkflowOperations.fetch_logs() - NEW ⚠️
```python
# Lines 68-122 in workflows/operations.py
# Get workflow runs
runs = airflow_serverless.list_workflow_runs(workflow_arn, region=region)

if not runs:
    return {"success": False, "error": "No workflow runs found"}

# Use specified run_id or most recent
target_run = None
if run_id:
    target_run = next((r for r in runs if r["run_id"] == run_id), None)
else:
    target_run = runs[0]  # Most recent

if not target_run:
    return {"success": False, "error": f"Run {run_id} not found"}

# Fetch logs
logs = airflow_serverless.get_workflow_logs(
    workflow_arn, target_run["run_id"], region=region, max_lines=lines
)

return {
    "success": True,
    "run_id": target_run["run_id"],
    "status": target_run.get("status"),
    "logs": logs,
    "workflow_arn": workflow_arn,
}
```

**Missing Features:**
- ❌ No live monitoring support
- ❌ No timestamp formatting
- ❌ No log stream information
- ❌ Returns raw logs without formatting
- ❌ No CloudWatch log group construction

---

## Recommendations

### Option 1: Keep CLI Commands As-Is (RECOMMENDED)
- CLI commands have tested, production-ready logic
- Bootstrap handlers use simplified `WorkflowOperations` for basic needs
- No code reuse, but both work correctly for their use cases

### Option 2: Enhance WorkflowOperations
Copy the tested CLI logic into `WorkflowOperations`:
1. Add workflow start verification (10s wait + status check)
2. Add DataZone connection type detection
3. Add duration calculation and status formatting
4. Add live log monitoring support
5. Then refactor CLI commands to use enhanced `WorkflowOperations`

### Option 3: Hybrid Approach
- Keep CLI commands using direct `airflow_serverless` calls
- Keep bootstrap handlers using simplified `WorkflowOperations`
- Document the differences and use cases

---

## Critical Missing Features in WorkflowOperations

1. **Workflow Start Verification** - CLI waits 10s and verifies status
2. **DataZone Connection Detection** - CLI queries DataZone for connection type
3. **Status Handling** - CLI handles INITIALIZING and terminal statuses
4. **Duration Calculation** - CLI calculates and formats run duration
5. **Live Monitoring** - CLI supports continuous log streaming
6. **Error Messages** - CLI provides helpful error messages with available options

**Conclusion:** The CLI commands contain significantly more robust, tested logic that should NOT be removed without careful migration to `WorkflowOperations`.
