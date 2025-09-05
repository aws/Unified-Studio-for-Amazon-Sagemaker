#!/usr/bin/env python3
"""
Debug available DataZone publish/listing methods.
"""

import boto3

def debug_publish_methods():
    datazone = boto3.client('datazone', region_name='us-east-1')
    
    # Get all methods that contain 'publish', 'listing', or 'catalog'
    publish_methods = [method for method in dir(datazone) if any(word in method.lower() for word in ['publish', 'listing', 'catalog'])]
    
    print("Available publish/listing methods:")
    for method in sorted(publish_methods):
        print(f"  - {method}")

if __name__ == "__main__":
    debug_publish_methods()
