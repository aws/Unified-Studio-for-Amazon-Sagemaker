#!/usr/bin/env python3
"""
Test script to check MWAA DAG detection and details in test environment.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smus_cicd.helpers import mwaa

def test_dag_details(mwaa_env_name, dag_names, region='us-east-1'):
    """Test detailed DAG information retrieval."""
    print(f"🔍 Testing DAG Details in: {mwaa_env_name}")
    print(f"📍 Region: {region}")
    print("-" * 60)
    
    for dag_name in dag_names:
        print(f"\n📋 Testing DAG: {dag_name}")
        try:
            details = mwaa.get_dag_details(mwaa_env_name, dag_name, region)
            
            print(f"  Raw details: {details}")
            
            if details.get('error'):
                print(f"  ❌ Error: {details['error']}")
            else:
                print(f"  📅 Schedule: {details.get('schedule_interval', 'Unknown')}")
                print(f"  ⏸️  Paused: {details.get('is_paused', 'Unknown')}")
                print(f"  🔄 Active: {details.get('active', 'Unknown')}")
                print(f"  📊 Last Run: {details.get('last_run_state', 'Unknown')}")
                print(f"  ✅ Success Runs: {details.get('successful_runs', 0)}")
                print(f"  ❌ Failed Runs: {details.get('failed_runs', 0)}")
                
        except Exception as e:
            print(f"  💥 Exception: {e}")
            import traceback
            traceback.print_exc()

def list_all_dags(mwaa_env_name, region='us-east-1'):
    """List all DAGs in MWAA environment using the correct helper."""
    print(f"🔍 Checking MWAA Environment: {mwaa_env_name}")
    print(f"📍 Region: {region}")
    print("-" * 60)
    
    try:
        # Use the correct MWAA helper function
        dag_names = mwaa.list_dags(mwaa_env_name, region)
        
        print(f"📋 Found {len(dag_names)} DAGs:")
        print()
        
        if not dag_names:
            print("❌ No DAGs found in environment")
            return []
        
        for i, dag_name in enumerate(dag_names, 1):
            # Status indicators based on DAG type
            if dag_name.startswith('generated_test_dag_'):
                status_icon = "🧪"
                dag_type = "GENERATED TEST DAG"
            elif dag_name in ['test_dag', 'sample_dag', 'test_dag_not_mentioned']:
                status_icon = "📝"
                dag_type = "MANIFEST DAG"
            else:
                status_icon = "📄"
                dag_type = "OTHER DAG"
            
            print(f"{i:2d}. {status_icon} {dag_name}")
            print(f"     Type: {dag_type}")
            print()
        
        return dag_names
        
    except Exception as e:
        print(f"❌ Error listing DAGs: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    # Test environment details
    test_mwaa_env = "DataZoneMWAAEnv-<domain-id>-<test-project-id>-dev"
    region = "us-east-1"
    
    print("🧪 MWAA DAG Detection and Details Test")
    print("=" * 60)
    print()
    
    # List all DAGs
    all_dags = list_all_dags(test_mwaa_env, region)
    
    if all_dags:
        print()
        print("=" * 60)
        print("🔍 Testing DAG Details")
        print("=" * 60)
        
        # Test details for a few DAGs
        test_dags = ['test_dag', 'sample_dag']
        if any(dag.startswith('generated_test_dag_') for dag in all_dags):
            test_dags.append(next(dag for dag in all_dags if dag.startswith('generated_test_dag_')))
        
        test_dag_details(test_mwaa_env, test_dags, region)
    
    print()
    print("=" * 60)
    print("🏁 Test Complete")
