"""Unit tests for Airflow output parser."""

import pytest
from smus_cicd.helpers.airflow_parser import (
    parse_dags_list,
    parse_tasks_list,
    parse_version,
    parse_dag_state,
    parse_airflow_output,
)


class TestAirflowParser:
    """Test cases for Airflow output parsing."""

    def test_parse_dags_list(self):
        """Test parsing dags list output."""
        stdout = """dag_id                             | fileloc                                                       | owners           | is_paused
===================================+===============================================================+==================+==========
generated_test_dag_1755976838_2112 | /usr/local/airflow/dags/generated_test_dag_1755976838_2112.py | integration-test | False    
sample_dag                         | /usr/local/airflow/dags/sample_dag.py                         | airflow          | True     
test_dag                           | /usr/local/airflow/dags/test_dag.py                           | airflow          | False    
"""

        result = parse_dags_list(stdout)

        assert len(result) == 3
        assert result[0]["dag_id"] == "generated_test_dag_1755976838_2112"
        assert result[0]["owners"] == "integration-test"
        assert result[0]["is_paused"] is False

        assert result[1]["dag_id"] == "sample_dag"
        assert result[1]["is_paused"] is True

        assert result[2]["dag_id"] == "test_dag"
        assert result[2]["is_paused"] is False

    def test_parse_tasks_list(self):
        """Test parsing tasks list output."""
        stdout = """hello_world
task_1
task_2
"""

        result = parse_tasks_list(stdout)

        assert result == ["hello_world", "task_1", "task_2"]

    def test_parse_version(self):
        """Test parsing version output."""
        stdout = "2.10.1\n"

        result = parse_version(stdout)

        assert result == {"version": "2.10.1"}

    def test_parse_dag_state(self):
        """Test parsing dag state output."""
        stdout = "running\n"

        result = parse_dag_state(stdout)

        assert result == {"state": "running"}

    def test_parse_airflow_output_dags_list(self):
        """Test parsing complete airflow output for dags list."""
        command = "dags list"
        stdout = """dag_id     | fileloc        | owners  | is_paused
===========+================+=========+==========
test_dag   | /test_dag.py   | airflow | False    
"""
        stderr = "Some warning"

        result = parse_airflow_output(command, stdout, stderr)

        assert result["command"] == "dags list"
        assert result["raw_stdout"] == stdout
        assert result["raw_stderr"] == stderr
        assert len(result["dags"]) == 1
        assert result["dags"][0]["dag_id"] == "test_dag"

    def test_parse_airflow_output_version(self):
        """Test parsing complete airflow output for version."""
        command = "version"
        stdout = "2.10.1"
        stderr = ""

        result = parse_airflow_output(command, stdout, stderr)

        assert result["command"] == "version"
        assert result["version"] == "2.10.1"

    def test_parse_airflow_output_unknown_command(self):
        """Test parsing unknown command output."""
        command = "unknown command"
        stdout = "some output"
        stderr = ""

        result = parse_airflow_output(command, stdout, stderr)

        assert result["command"] == "unknown command"
        assert result["output"] == "some output"

    def test_parse_dags_list_empty(self):
        """Test parsing empty dags list."""
        stdout = """dag_id | fileloc | owners | is_paused
=======+=========+========+==========
"""

        result = parse_dags_list(stdout)

        assert result == []

    def test_parse_tasks_list_empty(self):
        """Test parsing empty tasks list."""
        stdout = ""

        result = parse_tasks_list(stdout)

        assert result == []
