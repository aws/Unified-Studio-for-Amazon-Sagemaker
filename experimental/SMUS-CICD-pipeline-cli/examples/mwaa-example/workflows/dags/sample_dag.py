"""
MWAA Marketing Pipeline DAG
Traditional Airflow DAG for MWAA environment
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.amazon.aws.operators.s3 import S3ListOperator
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'marketing-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'marketing_mwaa_pipeline',
    default_args=default_args,
    description='Marketing data processing pipeline for MWAA',
    schedule_interval='0 6 * * *',  # Daily at 6 AM
    catchup=False,
    tags=['marketing', 'mwaa', 'demo']
)

def process_marketing_data(**context):
    """Process marketing data"""
    print("Processing marketing data in MWAA environment")
    print(f"Execution date: {context['ds']}")
    return "Marketing data processed successfully"

# List marketing data files
list_marketing_files = S3ListOperator(
    task_id='list_marketing_files',
    bucket='marketing-data-bucket',
    prefix='raw-data/',
    dag=dag
)

# Process marketing data
process_data = PythonOperator(
    task_id='process_marketing_data',
    python_callable=process_marketing_data,
    dag=dag
)

# Set task dependencies
list_marketing_files >> process_data
