"""Test DAG for integration testing."""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'smus-cli',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'test_dag',
    default_args=default_args,
    description='Test DAG for SMUS CLI integration tests',
    schedule_interval=None,
    catchup=False,
    tags=['test', 'smus-cli'],
)

def test_task():
    """Simple test task."""
    print("Test task executed successfully!")
    return "success"

test_operator = PythonOperator(
    task_id='test_task',
    python_callable=test_task,
    dag=dag,
)
