#!/usr/bin/env python3

import boto3
import json
import time
from botocore.client import BaseClient
from botocore.model import ServiceModel
from botocore.config import Config

def create_custom_datazone_client():
    """Create a custom DataZone client with WORKFLOWS_MWAA support"""
    
    # Load custom service model
    with open('/tmp/datazone-2018-05-10.json', 'r') as f:
        service_model_data = json.load(f)
    
    # Create session
    session = boto3.Session()
    
    # Get the standard client first
    standard_client = session.client('datazone', region_name='us-west-2')
    
    # Create custom service model
    service_model = ServiceModel(service_model_data, 'datazone')
    
    # Create a new client with the custom service model
    # We'll use the internal botocore mechanisms
    from botocore.client import ClientCreator
    from botocore.endpoint import Endpoint
    
    # Get the event system and credentials from the standard client
    event_system = standard_client._client_config.events
    credentials = standard_client._get_credentials()
    
    # Create client creator
    client_creator = ClientCreator(
        loader=standard_client._service_model._service_description,
        endpoint_resolver=standard_client._endpoint,
        user_agent=standard_client._client_config.user_agent,
        event_emitter=event_system,
        retry_handler_factory=standard_client._client_config.retry_handler_factory,
        retry_config_translator=standard_client._client_config.retry_config_translator,
        response_parser_factory=standard_client._response_parser_factory,
        exceptions_factory=standard_client.exceptions
    )
    
    # This approach is getting complex. Let me try a simpler method.
    return standard_client

def test_workflows_mwaa_with_standard_client():
    """Test if WORKFLOWS_MWAA works with standard client by trying the API call"""
    
    client = boto3.client('datazone', region_name='us-west-2')
    
    # Test parameters
    domain_id = "dzd_4s3r2q1p0o9n8m7l6k5j4i"
    project_id = "5mrkpk3iwpwx0n"
    
    # Create unique connection name with timestamp
    timestamp = str(int(time.time()))
    connection_name = f"test-mwaa-connection-{timestamp}"
    
    try:
        # Try to create WORKFLOWS_MWAA connection with standard client
        response = client.create_connection(
            domainIdentifier=domain_id,
            projectIdentifier=project_id,
            name=connection_name,
            description="Test WORKFLOWS_MWAA connection with standard client",
            connectionType="WORKFLOWS_MWAA",
            props={
                "workflowsMwaaProperties": {
                    "airflowVersion": "2.4.3",
                    "environmentArn": "arn:aws:mwaa:us-west-2:123456789012:environment/test-mwaa-env",
                    "executionRoleArn": "arn:aws:iam::123456789012:role/service-role/AmazonMWAA-test-mwaa-env-role",
                    "region": "us-west-2"
                }
            }
        )
        
        print("✅ WORKFLOWS_MWAA connection created successfully with standard client!")
        print(f"Connection ID: {response['connectionId']}")
        print(f"Connection Name: {response['name']}")
        print(f"Connection Type: {response['connectionType']}")
        print(f"Status: {response['status']}")
        
        return response['connectionId']
        
    except Exception as e:
        print(f"❌ Error creating WORKFLOWS_MWAA connection: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        
        # Check if it's a validation error about the connection type
        if "WORKFLOWS_MWAA" in str(e) and "not supported" in str(e).lower():
            print("🔍 WORKFLOWS_MWAA connection type is not supported in the current API schema")
        elif "ValidationException" in str(e):
            print("🔍 This appears to be a validation error - the connection type might not be available")
        
        return None

def list_available_connection_types():
    """Try to determine what connection types are available"""
    
    client = boto3.client('datazone', region_name='us-west-2')
    
    # Test with known working connection types
    known_types = [
        "ATHENA", "BIGQUERY", "DATABRICKS", "DOCUMENTDB", "DYNAMODB", 
        "GLUE", "MYSQL", "OPENSEARCH", "ORACLE", "POSTGRESQL", 
        "REDSHIFT", "SAGEMAKER", "SNOWFLAKE", "SPARK", "SQLSERVER", "TERADATA"
    ]
    
    print("Testing known connection types to see which ones are accepted...")
    
    domain_id = "dzd_4s3r2q1p0o9n8m7l6k5j4i"
    project_id = "5mrkpk3iwpwx0n"
    
    for conn_type in known_types:
        try:
            # Try with minimal properties - this should fail but tell us if the type is valid
            response = client.create_connection(
                domainIdentifier=domain_id,
                projectIdentifier=project_id,
                name=f"test-{conn_type.lower()}-validation",
                connectionType=conn_type,
                props={}  # Empty props should cause validation error but not type error
            )
            print(f"✅ {conn_type}: Accepted (unexpected success)")
            
        except Exception as e:
            error_msg = str(e)
            if "ValidationException" in error_msg and "props" in error_msg.lower():
                print(f"✅ {conn_type}: Accepted (validation error on props as expected)")
            elif "not supported" in error_msg.lower() or "invalid" in error_msg.lower():
                print(f"❌ {conn_type}: Not supported")
            else:
                print(f"❓ {conn_type}: Unknown error - {error_msg[:100]}...")

if __name__ == "__main__":
    print("Testing WORKFLOWS_MWAA connection creation...")
    print("=" * 80)
    
    # First test with standard client
    connection_id = test_workflows_mwaa_with_standard_client()
    
    if not connection_id:
        print("\n" + "=" * 80)
        print("Testing other connection types for comparison...")
        list_available_connection_types()
    
    print("\n" + "=" * 80)
    if connection_id:
        print(f"🎉 Successfully created WORKFLOWS_MWAA connection: {connection_id}")
    else:
        print("💥 WORKFLOWS_MWAA connection creation failed")
        print("This suggests that WORKFLOWS_MWAA is not yet available in the public API schema")
        print("even though it exists in DataZone projects as we observed earlier.")
