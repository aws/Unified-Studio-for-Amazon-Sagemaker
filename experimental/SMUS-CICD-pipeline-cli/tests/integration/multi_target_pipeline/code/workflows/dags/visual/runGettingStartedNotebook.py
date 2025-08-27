from airflow import DAG
from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
from airflow.models.param import Param
from sagemaker_studio import Project
from workflows.airflow.providers.amazon.aws.operators.sagemaker_workflows import NotebookOperator
from datetime import datetime

project = Project()

with DAG(
    dag_id='runGettingStartedNotebook',
    description='',default_args={},
    schedule="@daily",
    is_paused_upon_creation=False,
    tags=[],
    catchup=False,
    start_date=datetime(2025, 8, 22, 0, 0, 0),
    end_date=datetime(2025, 8, 29, 0, 0, 0),) as dag:

    SageMakerNotebookOperator_1756079708986 = NotebookOperator(
        task_id='notebook-task',
        input_config={
            "input_path": 'getting_started.ipynb',
            "input_params": {"databaseName": "dev"}
        },
        output_config={"output_formats": ['NOTEBOOK']},
        poll_interval=5,
    )