#!/usr/bin/env python3
"""
Integration test for all confirmed working DataZone connection types.
Tests: S3, IAM, SPARK_GLUE, ATHENA, REDSHIFT, SPARK_EMR, MLFLOW, WORKFLOWS_MWAA, WORKFLOWS_SERVERLESS
"""

import boto3
import time

DOMAIN_ID = "dzd_6je2k8b63qse07"
ENV_ID = "dtadp6zmf87b53"
REGION = "us-east-1"

def test_connection(client, name, props, description=""):
    """Create, verify, and cleanup a connection"""
    try:
        response = client.create_connection(
            domainIdentifier=DOMAIN_ID,
            environmentIdentifier=ENV_ID,
            name=name,
            description=description,
            props=props
        )
        
        conn_id = response['connectionId']
        print(f"  ✅ Created: {conn_id}")
        
        # Verify connection exists
        detail = client.get_connection(
            domainIdentifier=DOMAIN_ID,
            identifier=conn_id
        )
        print(f"  ✅ Verified: {detail['type']}")
        
        # Cleanup
        client.delete_connection(
            domainIdentifier=DOMAIN_ID,
            identifier=conn_id
        )
        print(f"  ✅ Cleaned up")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Failed: {str(e)[:100]}")
        return False

def main():
    client = boto3.client('datazone', region_name=REGION)
    timestamp = int(time.time())
    
    print("=" * 80)
    print("Testing All 8 Working DataZone Connection Types")
    print("=" * 80)
    
    results = {}
    
    # 1. S3
    print("\n1. Testing S3 Connection...")
    results['S3'] = test_connection(
        client,
        f"test-s3-{timestamp}",
        {"s3Properties": {"s3Uri": "s3://test-bucket/data/"}},
        "Test S3 connection"
    )
    time.sleep(1)
    
    # 2. IAM
    print("\n2. Testing IAM Connection...")
    results['IAM'] = test_connection(
        client,
        f"test-iam-{timestamp}",
        {"iamProperties": {"glueLineageSyncEnabled": False}},
        "Test IAM connection"
    )
    time.sleep(1)
    
    # 3. SPARK_GLUE
    print("\n3. Testing SPARK_GLUE Connection...")
    results['SPARK_GLUE'] = test_connection(
        client,
        f"test-spark-glue-{timestamp}",
        {
            "sparkGlueProperties": {
                "glueVersion": "4.0",
                "workerType": "G.1X",
                "numberOfWorkers": 2
            }
        },
        "Test Spark Glue connection"
    )
    time.sleep(1)
    
    # 4. ATHENA
    print("\n4. Testing ATHENA Connection...")
    results['ATHENA'] = test_connection(
        client,
        f"test-athena-{timestamp}",
        {"athenaProperties": {"workgroupName": "workgroup-buxme33txzr413-dtadp6zmf87b53"}},
        "Test Athena connection"
    )
    time.sleep(1)
    
    # 5. REDSHIFT
    print("\n5. Testing REDSHIFT Connection...")
    results['REDSHIFT'] = test_connection(
        client,
        f"test-redshift-{timestamp}",
        {
            "redshiftProperties": {
                "storage": {"clusterName": "test-cluster"},
                "databaseName": "dev",
                "host": "test-cluster.abc123.us-east-1.redshift.amazonaws.com",
                "port": 5439
            }
        },
        "Test Redshift connection"
    )
    time.sleep(1)
    
    # 6. SPARK_EMR
    print("\n6. Testing SPARK_EMR Connection...")
    results['SPARK_EMR'] = test_connection(
        client,
        f"test-spark-emr-{timestamp}",
        {
            "sparkEmrProperties": {
                "computeArn": "arn:aws:emr-serverless:us-east-1:123456789012:/applications/00abc123def456",
                "runtimeRole": "arn:aws:iam::123456789012:role/EMRServerlessExecutionRole"
            }
        },
        "Test Spark EMR connection"
    )
    time.sleep(1)
    
    # 7. MLFLOW
    print("\n7. Testing MLFLOW Connection...")
    results['MLFLOW'] = test_connection(
        client,
        f"test-mlflow-{timestamp}",
        {
            "mlflowProperties": {
                "trackingServerName": "wine-classification-mlflow-v2",
                "trackingServerArn": "arn:aws:sagemaker:us-east-1:058264284947:mlflow-tracking-server/wine-classification-mlflow-v2"
            }
        },
        "Test MLflow connection"
    )
    time.sleep(1)
    
    # 8. WORKFLOWS_MWAA
    print("\n8. Testing WORKFLOWS_MWAA Connection...")
    results['WORKFLOWS_MWAA'] = test_connection(
        client,
        f"test-mwaa-{timestamp}",
        {
            "workflowsMwaaProperties": {
                "mwaaEnvironmentName": "DataZoneMWAAEnv-dzd_6je2k8b63qse07-4kc6456xevd0h3-dev"
            }
        },
        "Test MWAA connection"
    )
    
    time.sleep(1)
    
    # 9. WORKFLOWS_SERVERLESS
    print("\n9. Testing WORKFLOWS_SERVERLESS Connection...")
    results['WORKFLOWS_SERVERLESS'] = test_connection(
        client,
        f"test-serverless-{timestamp}",
        {"workflowsServerlessProperties": {}},
        "Test serverless workflows connection"
    )
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for conn_type, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {conn_type}")
    
    print(f"\nResults: {passed}/{total} connection types working ({passed*100//total}%)")
    
    if passed == total:
        print("\n🎉 All connection types working!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} connection type(s) failed")
        return 1

if __name__ == "__main__":
    exit(main())
