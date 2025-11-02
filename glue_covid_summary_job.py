import sys
import boto3
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import sum as spark_sum, count, avg

# Initialize GlueContext and SparkSession
args = getResolvedOptions(sys.argv, ['JOB_NAME'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

glue_client = boto3.client('glue')

print("Starting COVID summary job...")

# Create summary database if it doesn't exist
summary_db = "covid19_summary_db"
try:
    glue_client.create_database(DatabaseInput={'Name': summary_db})
    print(f"✓ Created database: {summary_db}")
except glue_client.exceptions.AlreadyExistsException:
    print(f"- Database {summary_db} already exists")

# Read data from the us_simplified table
print("Reading data from us_simplified table...")
datasource = glueContext.create_dynamic_frame.from_catalog(
    database="covid19_db",
    table_name="us_simplified"
)

df = datasource.toDF()
print(f"Read {df.count()} records from us_simplified table")

# Create summary by state
print("Creating summary by state...")
summary_df = df.groupBy("state").agg(
    spark_sum("cases").alias("total_cases"),
    spark_sum("deaths").alias("total_deaths"),
    avg("cases").alias("avg_daily_cases"),
    count("*").alias("days_reported")
).orderBy("total_cases", ascending=False)

print("Top 10 states by total cases:")
summary_df.show(10)

# Define S3 output path
s3_output_path = "s3://amazon-sagemaker-198737698272-us-east-1-4pg255jku47vdz/covid19-data/us_state_summary/"

# Write the DataFrame to S3 in Parquet format
print(f"Writing summary data to: {s3_output_path}")
summary_df.write \
    .format("parquet") \
    .mode("overwrite") \
    .save(s3_output_path)

print("✓ Data written to S3 successfully")

# Create Glue table for the summary data
print("Creating Glue table for summary data...")
try:
    glue_client.create_table(
        DatabaseName=summary_db,
        TableInput={
            'Name': 'us_state_summary',
            'StorageDescriptor': {
                'Columns': [
                    {'Name': 'state', 'Type': 'string'},
                    {'Name': 'total_cases', 'Type': 'bigint'},
                    {'Name': 'total_deaths', 'Type': 'bigint'},
                    {'Name': 'avg_daily_cases', 'Type': 'double'},
                    {'Name': 'days_reported', 'Type': 'bigint'}
                ],
                'Location': s3_output_path,
                'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
                'SerdeInfo': {
                    'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                }
            }
        }
    )
    print(f"✓ Created table: {summary_db}.us_state_summary")
except glue_client.exceptions.AlreadyExistsException:
    print(f"- Table us_state_summary already exists")

print("✓ COVID summary job completed successfully")

job.commit()
