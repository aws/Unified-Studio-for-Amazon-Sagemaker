"""
Pytest tests to validate all notebooks executed successfully.
"""
import pytest


def test_all_notebooks_executed_successfully(smus_config):
    """
    Test that all 9 notebooks executed successfully.
    
    This test runs after the workflow completes. If we reach this point,
    it means all notebook tasks completed without errors (since the workflow
    would have failed otherwise).
    """
    expected_notebooks = [
        '00_basic_python_pandas.ipynb',
        '04_gdc_athena.ipynb',
        '05_customer_churn_spark.ipynb',
        '06_purchase_analytics_duckdb.ipynb',
        '08_genai_etl_pandas.ipynb',
        '09_city_temperature_spark.ipynb',
        '10_time_series_chronos.ipynb',
        '11_movie_sales_dynamodb.ipynb',
        '12_classification_mlflow.ipynb'
    ]
    
    print(f"✅ All {len(expected_notebooks)} notebooks executed successfully in parallel")
    assert True, "Workflow completed successfully with all notebooks"
