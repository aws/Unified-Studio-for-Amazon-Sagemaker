#!/usr/bin/env python3

import boto3
import time
import json

def test_connection_type(client, domain_id, env_id, conn_type, props, description=""):
    """Test creating a specific connection type"""
    
    timestamp = str(int(time.time()))
    connection_name = f"test-{conn_type.lower()}-{timestamp}"
    
    try:
        response = client.create_connection(
            domainIdentifier=domain_id,
            environmentIdentifier=env_id,
            name=connection_name,
            description=f"Test {conn_type} connection - {description}",
            props=props
        )
        
        print(f"✅ {conn_type}: SUCCESS - {response['connectionId']}")
        return True, response['connectionId']
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ {conn_type}: FAILED - {error_msg[:100]}...")
        return False, error_msg

def main():
    client = boto3.client('datazone', region_name='us-east-1')
    domain_id = "dzd_6je2k8b63qse07"
    env_id = "dtadp6zmf87b53"  # Real environment ID
    
    print("Testing all available DataZone connection types...")
    print("=" * 80)
    
    # Test each connection type with minimal valid properties
    test_cases = [
        # 1. SPARK GLUE - We know this works
        ("SPARK_GLUE", {
            "sparkGlueProperties": {
                "glueVersion": "5.0",
                "workerType": "G.1X",
                "numberOfWorkers": 2,
                "timeout": 60
            }
        }, "Minimal Spark Glue"),
        
        # 2. ATHENA
        ("ATHENA", {
            "athenaProperties": {
                "workGroup": "primary"
            }
        }, "Basic Athena"),
        
        # 3. GLUE
        ("GLUE", {
            "glueProperties": {
                "catalogId": "123456789012"
            }
        }, "Basic Glue Catalog"),
        
        # 4. REDSHIFT
        ("REDSHIFT", {
            "redshiftProperties": {
                "clusterIdentifier": "test-cluster",
                "database": "dev"
            }
        }, "Basic Redshift"),
        
        # 5. S3
        ("S3", {
            "s3Properties": {
                "bucket": "test-bucket"
            }
        }, "Basic S3"),
        
        # 6. SPARK EMR
        ("SPARK_EMR", {
            "sparkEmrProperties": {
                "clusterId": "j-1234567890123"
            }
        }, "Basic Spark EMR"),
        
        # 7. IAM
        ("IAM", {
            "iamProperties": {
                "roleArn": "arn:aws:iam::123456789012:role/TestRole"
            }
        }, "Basic IAM"),
        
        # 8. HYPERPOD
        ("HYPERPOD", {
            "hyperPodProperties": {
                "clusterName": "test-cluster"
            }
        }, "Basic HyperPod"),
        
        # 9. MLFLOW
        ("MLFLOW", {
            "mlflowProperties": {
                "trackingServerName": "wine-classification-mlflow-v2",
                "trackingServerArn": "arn:aws:sagemaker:us-east-1:058264284947:mlflow-tracking-server/wine-classification-mlflow-v2"
            }
        }, "Basic MLflow")
    ]
    
    results = {}
    
    for conn_type, props, desc in test_cases:
        success, result = test_connection_type(client, domain_id, env_id, conn_type, props, desc)
        results[conn_type] = {"success": success, "result": result}
        time.sleep(1)  # Rate limiting
    
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    
    working_types = []
    failed_types = []
    
    for conn_type, result in results.items():
        if result["success"]:
            working_types.append(conn_type)
            print(f"✅ {conn_type}: WORKING")
        else:
            failed_types.append(conn_type)
            print(f"❌ {conn_type}: FAILED")
    
    print(f"\nWorking connection types: {len(working_types)}")
    print(f"Failed connection types: {len(failed_types)}")
    
    if working_types:
        print(f"\n🎉 Confirmed working types: {', '.join(working_types)}")
    
    return results

if __name__ == "__main__":
    results = main()
