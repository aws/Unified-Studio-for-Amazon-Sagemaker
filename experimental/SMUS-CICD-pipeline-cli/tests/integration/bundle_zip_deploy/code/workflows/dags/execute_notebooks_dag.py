from airflow import DAG
from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
from airflow.models.param import Param
from airflow.models import Variable
from sagemaker_studio import Project
from workflows.airflow.providers.amazon.aws.operators.sagemaker_workflows import (
    NotebookOperator,
)
from datetime import datetime

project = Project()
STAGE = Variable.get("STAGE", default_var="DEV")

# Get the storage connection details
storage_conn = project.get_connection("default.s3_shared")
notebook_base_path = f"{storage_conn.get_uri()}/src"

with DAG(
    dag_id="execute_notebooks_dag",
    description="Execute both test notebooks in parallel",
    default_args={},
    # schedule="@daily",
    is_paused_upon_creation=False,
    tags=["notebooks", "parallel-execution"],
    catchup=False,
    start_date=datetime(2025, 9, 11, 0, 0, 0),
) as dag:

    # execute_test_notebook1 = NotebookOperator(
    #     task_id='execute-test-notebook1',
    #     input_config={
    #         "input_path": f'{notebook_base_path}/test-notebook1.ipynb',
    #         "input_params": {"environment": "test"}
    #     },
    #     output_config={"output_formats": ['NOTEBOOK']},
    #     poll_interval=5,
    # )

    execute_covid_analysis = NotebookOperator(
        task_id="execute-covid-analysis",
        input_config={
            "input_path": f"{notebook_base_path}/covid_analysis.ipynb",
            "input_params": {"STAGE": STAGE, "expected_table_rows": "8"},
        },
        output_config={"output_formats": ["NOTEBOOK"]},
        poll_interval=5,
    )

    # Execute notebook
    execute_covid_analysis
