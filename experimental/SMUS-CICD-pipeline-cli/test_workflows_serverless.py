#!/usr/bin/env python3
"""Quick test for WORKFLOWS_SERVERLESS connection type."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from smus_cicd.helpers.connection_creator import ConnectionCreator

# Test configuration
DOMAIN_ID = "dzd_6je2k8b63qse07"
ENVIRONMENT_ID = "dtadp6zmf87b53"
REGION = "us-east-1"

def test_workflows_serverless():
    """Test creating WORKFLOWS_SERVERLESS connection."""
    print("Testing WORKFLOWS_SERVERLESS connection...")
    
    creator = ConnectionCreator(DOMAIN_ID, REGION)
    
    try:
        # Create connection
        conn_id = creator.create_connection(
            environment_id=ENVIRONMENT_ID,
            name=f"test-serverless-workflows",
            connection_type="WORKFLOWS_SERVERLESS",
            description="Test serverless workflows connection"
        )
        
        print(f"✅ Created connection: {conn_id}")
        
        # Cleanup
        creator.client.delete_connection(
            domainIdentifier=DOMAIN_ID,
            identifier=conn_id
        )
        print(f"✅ Cleaned up connection: {conn_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_workflows_serverless()
    sys.exit(0 if success else 1)
