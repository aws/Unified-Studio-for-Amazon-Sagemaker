import sys
import boto3
from awsglue.utils import getResolvedOptions

# Get job parameters
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'BUCKET_NAME', 'REGION_NAME'])

# Initialize AWS clients
glue_client = boto3.client('glue', region_name=args['REGION_NAME'])

bucket = args['BUCKET_NAME']
# Git repo cloned to 'repos/', CSV files are in repo's 'data/' subdirectory
s3_location = f's3://{bucket}/shared/repos/data/'

print(f"Setting up COVID-19 database and table")
print(f"Data location: {s3_location}")

# Create covid19_db database
db_name = "covid19_db"
try:
    glue_client.create_database(DatabaseInput={'Name': db_name})
    print(f"✓ Created database: {db_name}")
except glue_client.exceptions.AlreadyExistsException:
    print(f"- Database {db_name} already exists")

# Create us_simplified table using the actual git repo CSV schema
print("Creating us_simplified table...")
try:
    # Try to delete existing table first
    try:
        glue_client.delete_table(DatabaseName=db_name, Name='us_simplified')
        print(f"- Deleted existing table: {db_name}.us_simplified")
    except glue_client.exceptions.EntityNotFoundException:
        pass
    
    glue_client.create_table(
        DatabaseName=db_name,
        TableInput={
            'Name': 'us_simplified',
            'StorageDescriptor': {
                'Columns': [
                    {'Name': 'date', 'Type': 'string'},
                    {'Name': 'country', 'Type': 'string'},
                    {'Name': 'province', 'Type': 'string'},
                    {'Name': 'confirmed', 'Type': 'bigint'},
                    {'Name': 'recovered', 'Type': 'bigint'},
                    {'Name': 'deaths', 'Type': 'bigint'}
                ],
                'Location': s3_location,
                'InputFormat': 'org.apache.hadoop.mapred.TextInputFormat',
                'OutputFormat': 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat',
                'SerdeInfo': {
                    'SerializationLibrary': 'org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe',
                    'Parameters': {
                        'field.delim': ',',
                        'skip.header.line.count': '1'
                    }
                }
            }
        }
    )
    print(f"✓ Created table: {db_name}.us_simplified")
except glue_client.exceptions.AlreadyExistsException:
    print(f"- Table us_simplified already exists")

print("✓ COVID-19 database setup completed successfully")
