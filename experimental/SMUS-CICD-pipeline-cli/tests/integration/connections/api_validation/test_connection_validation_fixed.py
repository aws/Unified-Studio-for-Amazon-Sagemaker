#!/usr/bin/env python3

import boto3
import time
import json

def test_connection_type(client, domain_id, env_id, conn_type, props, description=""):
    """Test creating a specific connection type"""
    
    timestamp = str(int(time.time()))
    connection_name = f"test-{conn_type.lower().replace('_', '-')}-{timestamp}"
    
    try:
        response = client.create_connection(
            domainIdentifier=domain_id,
            environmentIdentifier=env_id,
            name=connection_name,
            description=f"Test {conn_type} connection - {description}",
            props=props
        )
        
        print(f"✅ {conn_type}: SUCCESS - {response['connectionId']}")
        
        # Clean up immediately
        try:
            client.delete_connection(
                domainIdentifier=domain_id,
                identifier=response['connectionId']
            )
            print(f"   Cleaned up {response['connectionId']}")
        except Exception as cleanup_error:
            print(f"   Warning: Cleanup failed - {cleanup_error}")
        
        return True, response['connectionId']
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ {conn_type}: FAILED - {error_msg[:150]}...")
        return False, error_msg

def main():
    client = boto3.client('datazone', region_name='us-west-2')
    domain_id = "dzd_6je2k8b63qse07"
    env_id = "dsfuumu0am26jr"
    
    print("Testing DataZone connection types with corrected schemas...")
    print("=" * 80)
    
    # Start with simplest working cases
    test_cases = [
        # 1. S3 - Corrected schema
        ("S3", {
            "s3Properties": {
                "s3Uri": "s3://test-datazone-bucket/data/"
            }
        }, "Basic S3 URI"),
        
        # 2. IAM - Corrected schema  
        ("IAM", {
            "iamProperties": {
                "glueLineageSyncEnabled": False
            }
        }, "Basic IAM"),
        
        # 3. SPARK GLUE - Corrected minimal schema
        ("SPARK_GLUE", {
            "sparkGlueProperties": {
                "glueVersion": "4.0",
                "workerType": "G.1X",
                "numberOfWorkers": 2
            }
        }, "Minimal Spark Glue"),
        
        # 4. GLUE - Corrected schema
        ("GLUE", {
            "glueProperties": {
                "glueConnectionInput": {
                    "name": "test-glue-connection",
                    "connectionType": "JDBC",
                    "connectionProperties": {
                        "JDBC_CONNECTION_URL": "jdbc:mysql://test.amazonaws.com:3306/test"
                    }
                }
            }
        }, "Basic Glue JDBC"),
        
        # 5. HYPERPOD - Corrected schema
        ("HYPERPOD", {
            "hyperPodProperties": {
                "clusterName": "test-hyperpod-cluster"
            }
        }, "Basic HyperPod")
    ]
    
    results = {}
    
    for i, (conn_type, props, desc) in enumerate(test_cases):
        print(f"\n[{i+1}/{len(test_cases)}] Testing {conn_type}...")
        success, result = test_connection_type(client, domain_id, env_id, conn_type, props, desc)
        results[conn_type] = {"success": success, "result": result}
        
        # Rate limiting
        if i < len(test_cases) - 1:
            time.sleep(2)
    
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
        
        # Save results
        with open('working_connection_types.json', 'w') as f:
            json.dump({
                'working_types': working_types,
                'failed_types': failed_types,
                'test_results': results
            }, f, indent=2)
        print(f"📝 Results saved to working_connection_types.json")
    
    return results

if __name__ == "__main__":
    results = main()
