"""Centralized boto3 client creation helper."""
import boto3
from typing import Dict, Any, Optional


def create_client(service_name: str, connection_info: Optional[Dict[str, Any]] = None, region: Optional[str] = None):
    """Create a boto3 client with region determined from connection info or explicit region."""
    
    # Determine region based on connection info or explicit region
    client_region = region  # Default to provided region
    
    if connection_info and not client_region:
        # Extract region from common physicalEndpoints pattern
        physical_endpoints = connection_info.get('physicalEndpoints', [])
        if physical_endpoints and len(physical_endpoints) > 0:
            aws_location = physical_endpoints[0].get('awsLocation', {})
            client_region = aws_location.get('awsRegion')
    
    # Require explicit region - no fallback
    if not client_region:
        raise ValueError("Region must be provided either explicitly or through connection info")
    
    return boto3.client(service_name, region_name=client_region)


def get_region_from_connection(connection_info: Dict[str, Any]) -> Optional[str]:
    """Extract region from connection information."""
    physical_endpoints = connection_info.get('physicalEndpoints', [])
    if physical_endpoints and len(physical_endpoints) > 0:
        aws_location = physical_endpoints[0].get('awsLocation', {})
        return aws_location.get('awsRegion')
    
    return None
