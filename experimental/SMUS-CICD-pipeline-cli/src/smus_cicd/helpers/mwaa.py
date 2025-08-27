"""MWAA (Managed Workflows for Apache Airflow) helper functions."""
from typing import Dict, Any, Optional, List
from . import boto3_client


def get_environment_status(environment_name: str, region: str = None, connection_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get MWAA environment status and details."""
    try:
        mwaa_client = boto3_client.create_client('mwaa', connection_info, region)
        response = mwaa_client.get_environment(Name=environment_name)
        environment = response.get('Environment', {})
        
        return {
            'status': environment.get('Status', 'UNKNOWN'),
            'name': environment.get('Name'),
            'arn': environment.get('Arn'),
            'webserver_url': environment.get('WebserverUrl'),
            'airflow_version': environment.get('AirflowVersion'),
            'created_at': environment.get('CreatedAt'),
            'last_update': environment.get('LastUpdate')
        }
    except Exception as e:
        return {
            'status': 'ERROR',
            'error': str(e)
        }


def get_all_dag_details(environment_name: str, region: str = None, connection_info: Dict[str, Any] = None) -> Dict[str, Dict[str, Any]]:
    """Get detailed information for all DAGs in a single call for better performance."""
    try:
        mwaa_client = boto3_client.create_client('mwaa', connection_info, region)
        
        # Get CLI token to execute Airflow commands
        token_response = mwaa_client.create_cli_token(Name=environment_name)
        cli_token = token_response['CliToken']
        web_server_hostname = token_response['WebServerHostname']
        
        import requests
        import base64
        
        headers = {
            'Authorization': f'Bearer {cli_token}',
            'Content-Type': 'text/plain'
        }
        
        url = f'https://{web_server_hostname}/aws_mwaa/cli'
        
        # Get all DAG info in one call using dags list
        raw_data = 'dags list'
        response = requests.post(url, headers=headers, data=raw_data, timeout=30)
        
        dag_details = {}
        
        if response.status_code == 200:
            result = response.json()
            stdout_b64 = result.get('stdout', '')
            
            if stdout_b64:
                stdout = base64.b64decode(stdout_b64).decode('utf8')
                lines = stdout.strip().split('\n')
                
                for line in lines:
                    if '|' in line and not line.startswith('dag_id'):  # Skip header
                        parts = [p.strip() for p in line.split('|')]
                        if len(parts) >= 4:
                            # Format: dag_id | filepath | owner | paused
                            dag_id = parts[0]
                            paused_str = parts[3] if len(parts) > 3 else 'True'
                            is_paused = 'True' in paused_str
                            
                            dag_details[dag_id] = {
                                'dag_id': dag_id,
                                'is_paused': is_paused,
                                'schedule_interval': 'Manual',  # Default
                                'last_run_state': None,
                                'next_run': None,
                                'active': not is_paused,
                                'successful_runs': 0,
                                'failed_runs': 0
                            }
        
        return dag_details
        
    except Exception as e:
        return {}


def run_airflow_command(environment_name: str, command: str, region: str = None, connection_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run an arbitrary Airflow CLI command and return the output."""
    try:
        mwaa_client = boto3_client.create_client('mwaa', connection_info, region)
        
        # Get CLI token to execute Airflow commands
        token_response = mwaa_client.create_cli_token(Name=environment_name)
        cli_token = token_response['CliToken']
        web_server_hostname = token_response['WebServerHostname']
        
        import requests
        import base64
        
        headers = {
            'Authorization': f'Bearer {cli_token}',
            'Content-Type': 'text/plain'
        }
        
        url = f'https://{web_server_hostname}/aws_mwaa/cli'
        
        # Execute the command
        response = requests.post(url, headers=headers, data=command, timeout=60)
        
        result = {
            'command': command,
            'environment': environment_name,
            'status_code': response.status_code,
            'stdout': '',
            'stderr': '',
            'success': False
        }
        
        if response.status_code == 200:
            response_data = response.json()
            stdout_b64 = response_data.get('stdout', '')
            stderr_b64 = response_data.get('stderr', '')
            
            if stdout_b64:
                result['stdout'] = base64.b64decode(stdout_b64).decode('utf8')
            if stderr_b64:
                result['stderr'] = base64.b64decode(stderr_b64).decode('utf8')
            
            result['success'] = True
        else:
            result['stderr'] = f"HTTP {response.status_code}: {response.text}"
        
        return result
        
    except Exception as e:
        return {
            'command': command,
            'environment': environment_name,
            'status_code': None,
            'stdout': '',
            'stderr': str(e),
            'success': False
        }


def delete_dag_from_history(environment_name: str, dag_id: str, region: str = None, connection_info: Dict[str, Any] = None) -> bool:
    """Delete a DAG from Airflow history using 'dags delete' command."""
    try:
        mwaa_client = boto3_client.create_client('mwaa', connection_info, region)
        
        # Get CLI token to execute Airflow commands
        token_response = mwaa_client.create_cli_token(Name=environment_name)
        cli_token = token_response['CliToken']
        web_server_hostname = token_response['WebServerHostname']
        
        import requests
        import base64
        
        headers = {
            'Authorization': f'Bearer {cli_token}',
            'Content-Type': 'text/plain'
        }
        
        url = f'https://{web_server_hostname}/aws_mwaa/cli'
        
        # Execute dags delete command
        raw_data = f'dags delete {dag_id}'
        response = requests.post(url, headers=headers, data=raw_data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            stdout_b64 = result.get('stdout', '')
            stderr_b64 = result.get('stderr', '')
            
            if stdout_b64:
                stdout = base64.b64decode(stdout_b64).decode('utf8')
                # Check for success indicators
                if 'deleted' in stdout.lower() or 'removed' in stdout.lower():
                    return True
            
            if stderr_b64:
                stderr = base64.b64decode(stderr_b64).decode('utf8')
                # Some success messages might be in stderr
                if 'deleted' in stderr.lower() or 'removed' in stderr.lower():
                    return True
        
        return False
        
    except Exception as e:
        return False


def delete_multiple_dags_from_history(environment_name: str, dag_ids: List[str], region: str = None, connection_info: Dict[str, Any] = None) -> Dict[str, bool]:
    """Delete multiple DAGs from Airflow history."""
    results = {}
    for dag_id in dag_ids:
        results[dag_id] = delete_dag_from_history(environment_name, dag_id, region, connection_info)
    return results


def get_airflow_ui_url(environment_name: str, region: str = None, connection_info: Dict[str, Any] = None) -> str:
    """Get the Airflow UI URL for the MWAA environment."""
    try:
        mwaa_client = boto3_client.create_client('mwaa', connection_info, region)
        
        # Get environment details
        response = mwaa_client.get_environment(Name=environment_name)
        environment = response.get('Environment', {})
        
        # Extract web server URL
        web_server_url = environment.get('WebserverUrl')
        if web_server_url:
            return f"https://{web_server_url}"
        
        return None
        
    except Exception as e:
        return None


def get_dag_details(environment_name: str, dag_id: str, region: str = None, connection_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get detailed DAG information including schedule, status, and run history."""
    try:
        mwaa_client = boto3_client.create_client('mwaa', connection_info, region)
        
        # Get CLI token to execute Airflow commands
        token_response = mwaa_client.create_cli_token(Name=environment_name)
        cli_token = token_response['CliToken']
        web_server_hostname = token_response['WebServerHostname']
        
        import requests
        import base64
        
        headers = {
            'Authorization': f'Bearer {cli_token}',
            'Content-Type': 'text/plain'
        }
        
        url = f'https://{web_server_hostname}/aws_mwaa/cli'
        
        dag_info = {
            'dag_id': dag_id,
            'is_paused': None,
            'schedule_interval': None,
            'last_run_state': None,
            'next_run': None,
            'active': None,
            'successful_runs': 0,
            'failed_runs': 0
        }
        
        # Get DAG info from dags list command (we know this works)
        raw_data = 'dags list'
        response = requests.post(url, headers=headers, data=raw_data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            stdout_b64 = result.get('stdout', '')
            
            if stdout_b64:
                stdout = base64.b64decode(stdout_b64).decode('utf8')
                lines = stdout.strip().split('\n')
                
                for line in lines:
                    if '|' in line and dag_id in line:
                        parts = [p.strip() for p in line.split('|')]
                        if len(parts) >= 4:
                            # Format: dag_id | filepath | owner | paused
                            paused_str = parts[3] if len(parts) > 3 else 'True'
                            dag_info['is_paused'] = 'True' in paused_str
                            dag_info['active'] = not dag_info['is_paused']
                            dag_info['schedule_interval'] = 'Manual'  # Default for now
                            break
        
        # Try to get DAG runs using tasks list (alternative approach)
        raw_data = f'tasks list {dag_id}'
        response = requests.post(url, headers=headers, data=raw_data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            stdout_b64 = result.get('stdout', '')
            
            if stdout_b64:
                stdout = base64.b64decode(stdout_b64).decode('utf8')
                # If we get task list, the DAG is active and parseable
                if stdout.strip() and 'No data found' not in stdout:
                    dag_info['active'] = True
                    # Count lines as rough indicator of complexity
                    task_count = len([line for line in stdout.split('\n') if line.strip() and not line.startswith('task_id')])
                    if task_count > 0:
                        dag_info['schedule_interval'] = 'Manual'  # We know it exists
        
        # Set reasonable defaults if we got basic info
        if dag_info['is_paused'] is not None:
            if dag_info['schedule_interval'] is None:
                dag_info['schedule_interval'] = 'Manual'
            if dag_info['active'] is None:
                dag_info['active'] = not dag_info['is_paused']
        
        return dag_info
        
    except Exception as e:
        return {
            'dag_id': dag_id,
            'error': str(e),
            'is_paused': None,
            'schedule_interval': None,
            'last_run_state': None,
            'active': None,
            'successful_runs': 0,
            'failed_runs': 0
        }


def list_dags(environment_name: str, region: str = None, connection_info: Dict[str, Any] = None) -> List[str]:
    """List all DAGs in the MWAA environment."""
    try:
        mwaa_client = boto3_client.create_client('mwaa', connection_info, region)
        
        # Get CLI token to execute Airflow commands
        token_response = mwaa_client.create_cli_token(Name=environment_name)
        cli_token = token_response['CliToken']
        web_server_hostname = token_response['WebServerHostname']
        
        # Use the CLI token to execute 'dags list' command
        import requests
        import base64
        
        headers = {
            'Authorization': f'Bearer {cli_token}',
            'Content-Type': 'text/plain'
        }
        
        # Execute airflow dags list command with correct AWS MWAA format
        url = f'https://{web_server_hostname}/aws_mwaa/cli'
        # AWS MWAA expects raw command string
        raw_data = 'dags list'
        
        response = requests.post(url, headers=headers, data=raw_data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            stdout_b64 = result.get('stdout', '')
            
            if stdout_b64:
                # Decode base64 stdout
                stdout = base64.b64decode(stdout_b64).decode('utf8')
                
                # Parse output from airflow dags list
                lines = stdout.strip().split('\n')
                dag_names = []
                
                for line in lines:
                    line = line.strip()
                    # Skip header lines, separator lines, empty lines, and log messages
                    if (line and 
                        not line.startswith('dag_id') and 
                        not line.startswith('---') and 
                        not line.startswith('===') and  # Skip table separators
                        not line.startswith('INFO') and 
                        not line.startswith('WARNING') and
                        not line.startswith('[') and  # Skip timestamp lines
                        not line.startswith('AIRFLOW') and
                        '|' in line and  # Must be a table row
                        line != ''):
                        # Extract DAG name from table format: "dag_name | path | owner | paused"
                        parts = line.split('|')
                        if len(parts) >= 1:
                            dag_name = parts[0].strip()
                            if dag_name and dag_name != 'dag_id':
                                dag_names.append(dag_name)
                
                return sorted(dag_names)
        
        return []
    except Exception as e:
        # If listing fails, return empty list
        return []


def check_environment_available(environment_name: str, region: str = None, connection_info: Dict[str, Any] = None) -> bool:
    """Check if MWAA environment is available and ready."""
    env_info = get_environment_status(environment_name, region, connection_info)
    return env_info.get('status') == 'AVAILABLE'


def create_mwaa_client(connection_info: Dict[str, Any] = None, region: str = None):
    """Create MWAA client using connection info or region."""
    return boto3_client.create_client('mwaa', connection_info, region)
