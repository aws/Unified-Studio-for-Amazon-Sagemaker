import sys
import boto3
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import sum as spark_sum, count, avg, col
from pyspark.sql.types import LongType

# Initialize GlueContext and SparkSession
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'S3_DATABASE_PATH', 'BUCKET_NAME'])
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

# Read CSV directly using Spark to avoid SerDe issues
bucket = args['BUCKET_NAME']
csv_path = f"s3://{bucket}/shared/repos/data/data/time-series-19-covid-combined.csv"
print(f"Reading CSV directly from: {csv_path}")

df = spark.read.format("csv") \
    .option("header", "true") \
    .option("inferSchema", "true") \
    .load(csv_path)

# Rename columns to simpler names
df = df.withColumnRenamed("Country/Region", "country") \
       .withColumnRenamed("Province/State", "province") \
       .withColumnRenamed("Date", "date") \
       .withColumnRenamed("Confirmed", "confirmed") \
       .withColumnRenamed("Recovered", "recovered") \
       .withColumnRenamed("Deaths", "deaths")

print(f"Read {df.count()} records from CSV")

# Cast numeric columns to ensure they're the right type
# Create summary by country
print("Creating summary by country...")
summary_df = df.groupBy("country").agg(
    spark_sum("confirmed").alias("total_confirmed"),
    spark_sum("deaths").alias("total_deaths"),
    avg("confirmed").alias("avg_daily_confirmed"),
    count("*").alias("days_reported")
).orderBy("total_confirmed", ascending=False)

print("Top 10 countries by total cases:")
summary_df.show(10)

# Define S3 output path from parameters
s3_output_path = args['S3_DATABASE_PATH']

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
                    {'Name': 'country', 'Type': 'string'},
                    {'Name': 'total_confirmed', 'Type': 'bigint'},
                    {'Name': 'total_deaths', 'Type': 'bigint'},
                    {'Name': 'avg_daily_confirmed', 'Type': 'double'},
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
