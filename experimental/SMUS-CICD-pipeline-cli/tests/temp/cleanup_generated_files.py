#!/usr/bin/env python3
# TODO: Replace {account_id} placeholders with test_config.get_account_id()
import boto3
import re

def delete_generated_files():
    s3 = boto3.client('s3')
    bucket = 'datazone-{account_id}-us-east-1-cicd-test-domain'
    prefix = ''
    pattern = re.compile(r'generated_test_dag_\d+_\d+\.(py|cpython.*\.pyc)$')
    
    paginator = s3.get_paginator('list_objects_v2')
    
    total_deleted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if 'Contents' not in page:
            continue
            
        delete_keys = []
        for obj in page['Contents']:
            # Check if the filename (not full path) matches the pattern
            filename = obj['Key'].split('/')[-1]
            if pattern.search(filename):
                delete_keys.append({'Key': obj['Key']})
                print(f"Marking for deletion: {obj['Key']}")
        
        if delete_keys:
            s3.delete_objects(
                Bucket=bucket,
                Delete={'Objects': delete_keys}
            )
            print(f"Deleted {len(delete_keys)} files")
            total_deleted += len(delete_keys)
    
    print(f"Total files deleted: {total_deleted}")

if __name__ == "__main__":
    delete_generated_files()
    print("Cleanup completed")
