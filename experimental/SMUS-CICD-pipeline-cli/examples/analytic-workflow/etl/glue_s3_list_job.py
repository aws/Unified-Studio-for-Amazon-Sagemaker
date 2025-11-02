import sys
import boto3
from awsglue.utils import getResolvedOptions

# Get job parameters
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'BUCKET_NAME', 'REGION_NAME'])

# Initialize AWS clients
s3_client = boto3.client('s3', region_name=args['REGION_NAME'])
glue_client = boto3.client('glue', region_name=args['REGION_NAME'])

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

# Create covid19_db database if it doesn't exist
db_name = "covid19_db"
try:
    glue_client.create_database(DatabaseInput={'Name': db_name})
    print(f"✓ Created database: {db_name}")
except glue_client.exceptions.AlreadyExistsException:
    print(f"- Database {db_name} already exists")

# Create us_simplified table
print("Creating us_simplified table...")
try:
    glue_client.create_table(
        DatabaseName=db_name,
        TableInput={
            'Name': 'us_simplified',
            'StorageDescriptor': {
                'Columns': [
                    {'Name': 'date', 'Type': 'string'},
                    {'Name': 'admin2', 'Type': 'string'},
                    {'Name': 'state', 'Type': 'string'},
                    {'Name': 'confirmed', 'Type': 'string'},
                    {'Name': 'deaths', 'Type': 'string'},
                    {'Name': 'country', 'Type': 'string'}
                ],
                'Location': s3_location,
                'InputFormat': 'org.apache.hadoop.mapred.TextInputFormat',
                'OutputFormat': 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat',
                'SerdeInfo': {
                    'SerializationLibrary': 'org.apache.hadoop.hive.serde2.OpenCSVSerde',
                    'Parameters': {
                        'separatorChar': ',',
                        'skip.header.line.count': '1'
                    }
                }
            }
        }
    )
    print(f"✓ Created table: {db_name}.us_simplified")
except glue_client.exceptions.AlreadyExistsException:
    print(f"- Table us_simplified already exists")

print("✓ Discovery job completed successfully")
