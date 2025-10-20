import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

# Initialize GlueContext and SparkSession
args = getResolvedOptions(sys.argv, ['JOB_NAME'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# List tables in the covid19_db database
tables = glueContext.get_catalog_schema_as_spark_schema(database="covid19_db")
print("Available tables in covid19_db:")
for table in glueContext.get_catalog_schema_as_spark_schema(database="covid19_db"):
    print(f"- {table}")

# Read and display sample data from worldwide_aggregate table
datasource = glueContext.create_dynamic_frame.from_catalog(
    database="covid19_db",
    table_name="worldwide_aggregate"
)

# Convert to DataFrame and show sample
df = datasource.toDF()
print(f"Total records in worldwide_aggregate: {df.count()}")
print("Sample data:")
df.show(5)

job.commit()
