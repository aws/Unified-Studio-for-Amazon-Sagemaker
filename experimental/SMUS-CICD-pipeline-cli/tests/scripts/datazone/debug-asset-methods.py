#!/usr/bin/env python3
"""
Debug available DataZone asset methods.
"""

import boto3


def debug_asset_methods():
    datazone = boto3.client("datazone", region_name="us-east-1")

    # Get all methods that contain 'asset'
    asset_methods = [method for method in dir(datazone) if "asset" in method.lower()]

    print("Available asset methods:")
    for method in sorted(asset_methods):
        print(f"  - {method}")


if __name__ == "__main__":
    debug_asset_methods()
