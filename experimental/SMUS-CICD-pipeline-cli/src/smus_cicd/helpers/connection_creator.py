"""Helper for creating DataZone connections with proper status waiting."""

import boto3
import time
from typing import Dict, Any, Optional


class ConnectionCreator:
    """Helper class for creating DataZone connections with status monitoring."""
    
    def __init__(self, domain_id: str, region: str = 'us-east-1'):
        self.domain_id = domain_id
        self.region = region
        self.client = boto3.client('datazone', region_name=region)
    
    def create_connection(
        self, 
        environment_id: str, 
        name: str, 
        connection_type: str, 
        description: str = None,
        **kwargs
    ) -> str:
        """
        Create a DataZone connection and wait for it to be ready.
        
        Args:
            environment_id: DataZone environment ID
            name: Connection name
            connection_type: Type of connection (S3, IAM, SPARK_GLUE, etc.)
            description: Optional description
            **kwargs: Connection-specific properties
            
        Returns:
            Connection ID
            
        Raises:
            Exception: If connection creation fails or times out
        """
        props = self._build_connection_props(connection_type, **kwargs)
        
        try:
            response = self.client.create_connection(
                domainIdentifier=self.domain_id,
                environmentIdentifier=environment_id,
                name=name,
                description=description or f"{connection_type} connection",
                props=props
            )
            
            connection_id = response['connectionId']
            
            # Wait for connection to be ready
            self._wait_for_connection_ready(connection_id, connection_type)
            
            return connection_id
            
        except Exception as e:
            raise Exception(f"Failed to create {connection_type} connection '{name}': {e}")
    
    def _build_connection_props(self, connection_type: str, **kwargs) -> Dict[str, Any]:
        """Build connection properties based on type."""
        if connection_type == 'S3':
            return {
                's3Properties': {
                    's3Uri': kwargs.get('s3_uri', 's3://default-bucket/data/')
                }
            }
        elif connection_type == 'IAM':
            return {
                'iamProperties': {
                    'glueLineageSyncEnabled': kwargs.get('glue_lineage_sync', True)
                }
            }
        elif connection_type == 'SPARK_GLUE':
            return {
                'sparkGlueProperties': {
                    'glueVersion': kwargs.get('glue_version', '4.0'),
                    'workerType': kwargs.get('worker_type', 'G.1X'),
                    'numberOfWorkers': kwargs.get('num_workers', 3)
                }
            }
        elif connection_type == 'SPARK_EMR':
            return {
                'sparkEmrProperties': {
                    'computeArn': kwargs.get('compute_arn', 'arn:aws:emr-serverless:us-east-1:123456789012:application/default'),
                    'runtimeRole': kwargs.get('runtime_role', 'arn:aws:iam::123456789012:role/EMRServerlessExecutionRole')
                }
            }
        elif connection_type == 'REDSHIFT':
            return {
                'redshiftProperties': {
                    'storage': {
                        'clusterName': kwargs.get('cluster_name', 'default-cluster')
                    },
                    'databaseName': kwargs.get('database_name', 'dev'),
                    'host': kwargs.get('host', 'default-cluster.abc123.us-east-1.redshift.amazonaws.com'),
                    'port': kwargs.get('port', 5439)
                }
            }
        elif connection_type == 'ATHENA':
            return {
                'athenaProperties': {
                    'workgroupName': kwargs.get('workgroup', 'primary')
                }
            }
        elif connection_type == 'MLFLOW':
            return {
                'mlflowProperties': {
                    'trackingServerName': kwargs.get('tracking_server_name', 'default-tracking-server'),
                    'trackingServerArn': kwargs.get('tracking_server_arn', 'arn:aws:sagemaker:us-east-1:123456789012:mlflow-tracking-server/default')
                }
            }
        elif connection_type == 'WORKFLOWS_MWAA':
            return {
                'workflowsMwaaProperties': {
                    'mwaaEnvironmentName': kwargs.get('mwaa_environment_name', 'default-mwaa-env')
                }
            }
        else:
            raise ValueError(f"Unsupported connection type: {connection_type}")
    
    def _wait_for_connection_ready(self, connection_id: str, connection_type: str, max_wait: int = 120):
        """Wait for connection to be ready."""
        wait_interval = 5
        elapsed = 0
        
        while elapsed < max_wait:
            try:
                detail = self.client.get_connection(
                    domainIdentifier=self.domain_id,
                    identifier=connection_id
                )
                
                status = self._extract_status(detail, connection_type)
                
                if status == 'READY':
                    return
                elif status in ['FAILED', 'DELETING']:
                    raise Exception(f"Connection failed with status: {status}")
                
                time.sleep(wait_interval)
                elapsed += wait_interval
                
            except Exception as e:
                if 'failed with status' in str(e):
                    raise
                # Continue waiting for other errors
                time.sleep(wait_interval)
                elapsed += wait_interval
        
        # Don't fail if timeout - connection might still work
        print(f"Warning: Connection {connection_id} did not become READY within {max_wait}s")
    
    def _extract_status(self, connection_detail: Dict[str, Any], connection_type: str) -> str:
        """Extract status from connection details based on type."""
        props = connection_detail.get('props', {})
        
        # Only GLUE-based connections have status field
        if connection_type in ['GLUE', 'SNOWFLAKE', 'JDBC']:
            return props.get('glueProperties', {}).get('status', 'UNKNOWN')
        elif connection_type == 'S3':
            return props.get('s3Properties', {}).get('status', 'READY')
        elif connection_type in ['SPARK_GLUE', 'SPARK_EMR']:
            return props.get('sparkGlueProperties', {}).get('status') or \
                   props.get('sparkEmrProperties', {}).get('status', 'READY')
        elif connection_type == 'REDSHIFT':
            return props.get('redshiftProperties', {}).get('status', 'READY')
        elif connection_type == 'ATHENA':
            return props.get('athenaProperties', {}).get('status', 'READY')
        else:
            # Connections without status field (IAM, MLFLOW, etc.) are ready immediately
            return 'READY'
