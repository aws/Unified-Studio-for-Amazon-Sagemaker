#!/usr/bin/env python3

import boto3
import time
import json
from typing import Dict, List, Tuple, Optional

class DataZoneConnectionValidator:
    """Validates DataZone connection types against the actual API"""
    
    def __init__(self, domain_id: str, environment_id: str, region: str = 'us-east-1'):
        self.client = boto3.client('datazone', region_name=region)
        self.domain_id = domain_id
        self.environment_id = environment_id
        self.results = {}
    
    def test_connection_type(self, conn_type: str, props: Dict, description: str = "") -> Tuple[bool, str]:
        """Test creating a specific connection type"""
        
        timestamp = str(int(time.time()))
        connection_name = f"test-{conn_type.lower().replace('_', '-')}-{timestamp}"
        
        try:
            response = self.client.create_connection(
                domainIdentifier=self.domain_id,
                environmentIdentifier=self.environment_id,
                name=connection_name,
                description=f"Test {conn_type} connection - {description}",
                props=props
            )
            
            connection_id = response['connectionId']
            print(f"✅ {conn_type}: SUCCESS - {connection_id}")
            
            # Clean up immediately
            try:
                self.client.delete_connection(
                    domainIdentifier=self.domain_id,
                    identifier=connection_id
                )
                print(f"   Cleaned up {connection_id}")
            except Exception as cleanup_error:
                print(f"   Warning: Cleanup failed - {cleanup_error}")
            
            return True, connection_id
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ {conn_type}: FAILED - {error_msg[:150]}...")
            return False, error_msg
    
    def get_test_cases(self) -> List[Tuple[str, Dict, str]]:
        """Get all connection type test cases with corrected schemas"""
        
        return [
            # 1. S3 - Simple object storage
            ("S3", {
                "s3Properties": {
                    "s3Uri": "s3://test-datazone-bucket/data/"
                }
            }, "Basic S3 URI"),
            
            # 2. IAM - Identity and access management
            ("IAM", {
                "iamProperties": {
                    "glueLineageSyncEnabled": False
                }
            }, "Basic IAM"),
            
            # 3. SPARK GLUE - Confirmed working type
            ("SPARK_GLUE", {
                "sparkGlueProperties": {
                    "glueVersion": "4.0",
                    "workerType": "G.1X",
                    "numberOfWorkers": 2
                }
            }, "Minimal Spark Glue"),
            
            # 4. ATHENA - SQL query engine
            ("ATHENA", {
                "athenaProperties": {
                    "workgroupName": "primary"
                }
            }, "Basic Athena"),
            
            # 5. GLUE - Data catalog
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
            
            # 6. REDSHIFT - Data warehouse
            ("REDSHIFT", {
                "redshiftProperties": {
                    "storage": {
                        "clusterName": "test-cluster"
                    },
                    "databaseName": "dev",
                    "host": "test-cluster.abc123.us-west-2.redshift.amazonaws.com",
                    "port": 5439
                }
            }, "Basic Redshift"),
            
            # 7. SPARK EMR - Elastic MapReduce
            ("SPARK_EMR", {
                "sparkEmrProperties": {
                    "computeArn": "arn:aws:emr-serverless:us-west-2:123456789012:/applications/00abc123def456",
                    "runtimeRole": "arn:aws:iam::123456789012:role/EMRServerlessExecutionRole"
                }
            }, "Basic Spark EMR"),
            
            # 8. HYPERPOD - ML training clusters
            ("HYPERPOD", {
                "hyperPodProperties": {
                    "clusterName": "test-hyperpod-cluster"
                }
            }, "Basic HyperPod")
        ]
    
    def validate_all_connection_types(self, rate_limit_seconds: int = 2) -> Dict:
        """Validate all connection types with rate limiting"""
        
        print("Testing DataZone connection types...")
        print(f"Domain: {self.domain_id}")
        print(f"Environment: {self.environment_id}")
        print("=" * 80)
        
        test_cases = self.get_test_cases()
        
        for i, (conn_type, props, desc) in enumerate(test_cases):
            print(f"\n[{i+1}/{len(test_cases)}] Testing {conn_type}...")
            success, result = self.test_connection_type(conn_type, props, desc)
            self.results[conn_type] = {"success": success, "result": result}
            
            # Rate limiting
            if i < len(test_cases) - 1:
                time.sleep(rate_limit_seconds)
        
        return self.results
    
    def generate_summary(self) -> Dict:
        """Generate summary of test results"""
        
        working_types = []
        failed_types = []
        
        for conn_type, result in self.results.items():
            if result["success"]:
                working_types.append(conn_type)
            else:
                failed_types.append(conn_type)
        
        summary = {
            'working_types': working_types,
            'failed_types': failed_types,
            'total_tested': len(self.results),
            'success_rate': len(working_types) / len(self.results) if self.results else 0,
            'test_results': self.results
        }
        
        print("\n" + "=" * 80)
        print("SUMMARY:")
        print("=" * 80)
        
        for conn_type in working_types:
            print(f"✅ {conn_type}: WORKING")
        
        for conn_type in failed_types:
            print(f"❌ {conn_type}: FAILED")
        
        print(f"\nWorking connection types: {len(working_types)}")
        print(f"Failed connection types: {len(failed_types)}")
        print(f"Success rate: {summary['success_rate']:.1%}")
        
        if working_types:
            print(f"\n🎉 Confirmed working types: {', '.join(working_types)}")
        
        return summary
    
    def save_results(self, filename: str = 'connection_validation_results.json'):
        """Save results to JSON file"""
        
        summary = self.generate_summary()
        
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📝 Results saved to {filename}")
        return filename

def main():
    """Main function - update with your DataZone domain and environment IDs"""
    
    # TODO: Update these with your actual DataZone domain and environment IDs
    DOMAIN_ID = "dzd_6je2k8b63qse07"
    ENVIRONMENT_ID = "dsfuumu0am26jr"
    
    if "dzd_6je2k8b63qse07" != DOMAIN_ID:
        print("❌ Please update DOMAIN_ID and ENVIRONMENT_ID in the script")
        print("   Run find_resources.py first to get your DataZone resource IDs")
        return
    
    validator = DataZoneConnectionValidator(DOMAIN_ID, ENVIRONMENT_ID)
    validator.validate_all_connection_types()
    validator.save_results()

if __name__ == "__main__":
    main()
