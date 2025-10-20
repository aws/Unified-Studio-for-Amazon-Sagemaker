import sys
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

print("Starting COVID summary job...")

# Read data from the worldwide_aggregate table
print("Reading data from worldwide_aggregate table...")
datasource = glueContext.create_dynamic_frame.from_catalog(
    database="covid19_db",
    table_name="worldwide_aggregate"
)

# Convert to DataFrame for easier manipulation
df = datasource.toDF()
print(f"Read {df.count()} records from worldwide_aggregate table")

# Create summary statistics
print("Creating summary statistics...")
summary_df = df.agg(
    spark_sum("confirmed").alias("total_confirmed"),
    spark_sum("deaths").alias("total_deaths"),
    spark_sum("recovered").alias("total_recovered"),
    avg("confirmed").alias("avg_confirmed"),
    avg("deaths").alias("avg_deaths"),
    avg("recovered").alias("avg_recovered"),
    count("*").alias("record_count")
)

# Show the summary data
print("Summary statistics:")
summary_df.show()

# Define S3 output path
s3_output_path = "s3://amazon-datazone-v2-058264284947-us-east-1-285314902/covid19_db/covid_summary_results/"

# Write the DataFrame to S3 in Parquet format
print(f"Writing summary data to: {s3_output_path}")
summary_df.write \
    .format("parquet") \
    .mode("overwrite") \
    .save(s3_output_path)

print("✓ Data written to S3 successfully")
print("✓ COVID summary job completed successfully")

job.commit()
