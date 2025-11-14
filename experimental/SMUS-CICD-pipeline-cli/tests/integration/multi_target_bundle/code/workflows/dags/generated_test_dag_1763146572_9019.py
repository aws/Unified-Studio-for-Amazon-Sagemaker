"""
Generated test DAG for integration testing.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator

def generated_test_dag_1763146572_9019_task():
    """Generated task function."""
    print(f"Executing generated task: generated_test_dag_1763146572_9019")
    return "Generated task completed successfully"

default_args = {
    'owner': 'integration-test',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'generated_test_dag_1763146572_9019',
    default_args=default_args,
    description='Generated test DAG for integration testing',
    schedule_interval=None,
    catchup=False,
    tags=['integration-test', 'generated'],
)

task = PythonOperator(
    task_id='generated_test_dag_1763146572_9019_task',
    python_callable=generated_test_dag_1763146572_9019_task,
    dag=dag,
)
