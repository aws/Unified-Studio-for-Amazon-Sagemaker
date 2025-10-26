#!/usr/bin/env python3

import boto3
import json
import time
from botocore.loaders import Loader
from botocore.model import ServiceModel

def load_custom_datazone_model():
    """Load custom DataZone service model with WORKFLOWS_MWAA support"""
    with open('/tmp/datazone-2018-05-10.json', 'r') as f:
        service_model_data = json.load(f)
    
    # Create a custom service model
    service_model = ServiceModel(service_model_data, 'datazone')
    return service_model

def create_workflows_mwaa_connection():
    """Test creating a WORKFLOWS_MWAA connection using custom service model"""
    
    # Load custom service model
    service_model = load_custom_datazone_model()
    
    # Create session and client
    session = boto3.Session()
    
    # Create client with custom service model
    client = session.client('datazone', region_name='us-west-2')
    
    # Replace the service model
    client._service_model = service_model
    
    # Test parameters
    domain_id = "dzd_4s3r2q1p0o9n8m7l6k5j4i"
    project_id = "5mrkpk3iwpwx0n"
    
    # Create unique connection name with timestamp
    timestamp = str(int(time.time()))
    connection_name = f"test-mwaa-connection-{timestamp}"
    
    try:
        # Create WORKFLOWS_MWAA connection
        response = client.create_connection(
            domainIdentifier=domain_id,
            projectIdentifier=project_id,
            name=connection_name,
            description="Test WORKFLOWS_MWAA connection with custom service model",
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
        
        print("✅ WORKFLOWS_MWAA connection created successfully!")
        print(f"Connection ID: {response['connectionId']}")
        print(f"Connection Name: {response['name']}")
        print(f"Connection Type: {response['connectionType']}")
        print(f"Status: {response['status']}")
        print(f"Domain ID: {response['domainId']}")
        print(f"Project ID: {response.get('projectId', 'N/A')}")
        
        return response['connectionId']
        
    except Exception as e:
        print(f"❌ Error creating WORKFLOWS_MWAA connection: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return None

if __name__ == "__main__":
    print("Testing WORKFLOWS_MWAA connection creation with custom DataZone service model...")
    print("=" * 80)
    
    connection_id = create_workflows_mwaa_connection()
    
    if connection_id:
        print(f"\n🎉 Successfully created WORKFLOWS_MWAA connection: {connection_id}")
    else:
        print("\n💥 Failed to create WORKFLOWS_MWAA connection")
