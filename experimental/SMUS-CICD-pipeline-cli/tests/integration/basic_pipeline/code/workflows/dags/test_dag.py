from airflow.decorators import dag
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "airflow",
}


@dag(default_args=default_args, tags=["test"])
def test_dag():
    def sample_task():
        _task = BashOperator(
            task_id="hello_world", bash_command="echo 'hello world from Amir!'"
        )
        return _task

    task = sample_task()


test_dag = test_dag()
