"""Parser for Airflow CLI command outputs."""
import re
from typing import Dict, List, Any


def parse_dags_list(stdout: str) -> List[Dict[str, Any]]:
    """Parse 'dags list' command output into structured data."""
    dags = []
    lines = stdout.strip().split('\n')
    
    # Skip header lines and find data rows
    data_started = False
    for line in lines:
        if '===' in line:  # Header separator
            data_started = True
            continue
        if not data_started or not line.strip():
            continue
            
        # Parse DAG row: dag_id | fileloc | owners | is_paused
        parts = [part.strip() for part in line.split('|')]
        if len(parts) >= 4:
            dags.append({
                "dag_id": parts[0],
                "fileloc": parts[1],
                "owners": parts[2],
                "is_paused": parts[3].lower() == 'true'
            })
    
    return dags


def parse_tasks_list(stdout: str) -> List[str]:
    """Parse 'tasks list' command output into list of task names."""
    tasks = []
    lines = stdout.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('Task') and '=' not in line:
            tasks.append(line)
    
    return tasks


def parse_version(stdout: str) -> Dict[str, str]:
    """Parse 'version' command output."""
    version = stdout.strip()
    return {"version": version}


def parse_dag_state(stdout: str) -> Dict[str, str]:
    """Parse 'dags state' command output."""
    state = stdout.strip()
    return {"state": state}


def parse_airflow_output(command: str, stdout: str, stderr: str) -> Dict[str, Any]:
    """Parse Airflow command output into structured JSON."""
    result = {
        "command": command,
        "raw_stdout": stdout,
        "raw_stderr": stderr
    }
    
    # Parse based on command type
    if command.startswith("dags list"):
        result["dags"] = parse_dags_list(stdout)
    elif command.startswith("tasks list"):
        result["tasks"] = parse_tasks_list(stdout)
    elif command == "version":
        result.update(parse_version(stdout))
    elif command.startswith("dags state"):
        result.update(parse_dag_state(stdout))
    else:
        # For unknown commands, just return raw output
        result["output"] = stdout.strip() if stdout.strip() else None
    
    return result
