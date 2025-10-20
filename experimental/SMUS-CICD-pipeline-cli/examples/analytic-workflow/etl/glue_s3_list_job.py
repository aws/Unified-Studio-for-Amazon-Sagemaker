import sys
import boto3
from awsglue.utils import getResolvedOptions

# Get job parameters
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'BUCKET_NAME', 'REGION_NAME'])

# Initialize AWS clients
s3_client = boto3.client('s3', region_name=args['REGION_NAME'])

# us_simplified table S3 location
bucket = args['BUCKET_NAME']
prefix = 'covid19-data/us_simplified/'
s3_location = f's3://{bucket}/{prefix}'

print(f"Listing files in us_simplified table location: {s3_location}")

try:
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    
    if 'Contents' in response:
        print(f"Found {len(response['Contents'])} files:")
        for obj in response['Contents']:
            print(f"  {obj['Key']} ({obj['Size']} bytes)")
    else:
        print("No files found")
        
except Exception as e:
    print(f"Error listing S3 files: {str(e)}")
    raise

print("S3 file listing completed")
