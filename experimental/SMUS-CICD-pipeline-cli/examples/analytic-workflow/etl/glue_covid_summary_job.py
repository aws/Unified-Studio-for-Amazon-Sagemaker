import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql.functions import max, min, avg, sum

# Get job parameters
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'DATABASE_NAME', 'TABLE_NAME'])

# Use parameters from workflow
database_name = args['DATABASE_NAME']
table_name = args['TABLE_NAME']

# Initialize Spark and Glue contexts
sc = SparkContext()
glueContext = GlueContext(sc)
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print(f"Analyzing COVID-19 worldwide aggregate data")

try:
    # Read the worldwide aggregate table
    df = glueContext.create_dynamic_frame.from_catalog(
        database=database_name,
        table_name=table_name
    ).toDF()
    
    print(f"Total records: {df.count()}")
    
    # Calculate summary statistics
    summary_df = df.agg(
        max('confirmed').alias('max_confirmed'),
        max('deaths').alias('max_deaths'),
        max('recovered').alias('max_recovered'),
        avg('increase_rate').alias('avg_increase_rate')
    )
    
    summary = summary_df.collect()[0]
    print(f"Max confirmed cases: {summary['max_confirmed']}")
    print(f"Max deaths: {summary['max_deaths']}")
    print(f"Max recovered: {summary['max_recovered']}")
    print(f"Average increase rate: {summary['avg_increase_rate']:.4f}")
    
    # Create catalog table with summary results
    from awsglue import DynamicFrame
    summary_dynamic_frame = DynamicFrame.fromDF(summary_df, glueContext, "summary_frame")
    glueContext.write_dynamic_frame.from_catalog(
        frame=summary_dynamic_frame,
        database=database_name,
        table_name="covid_summary_results"
    )
    
    print("COVID-19 analysis completed successfully")
    
except Exception as e:
    print(f"Error in COVID analysis: {str(e)}")
    raise
finally:
    job.commit()
