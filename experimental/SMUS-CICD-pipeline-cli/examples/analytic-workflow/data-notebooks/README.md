# Parallel Notebook Execution Example

This example demonstrates parallel execution of multiple notebooks using SageMaker Unified Studio CICD pipeline.

## Overview

- **9 example notebooks** covering various data processing and ML scenarios
- **Parallel execution** using Airflow with SageMakerNotebookOperator
- **Integration test** validates all notebooks complete successfully

## Notebooks

1. `00_basic_python_pandas.ipynb` - Basic Python and Pandas operations
2. `04_gdc_athena.ipynb` - Glue Data Catalog read/write with Athena
3. `05_customer_churn_spark.ipynb` - Customer churn analysis using Spark Connect
4. `06_purchase_analytics_duckdb.ipynb` - Purchase analytics with DuckDB
5. `08_genai_etl_pandas.ipynb` - GenAI ETL using Pandas
6. `09_city_temperature_spark.ipynb` - City temperature ETL with Spark
7. `10_time_series_chronos.ipynb` - Time series forecasting with Chronos
8. `11_movie_sales_dynamodb.ipynb` - Movie ticket sales with DynamoDB
9. `12_classification_mlflow.ipynb` - Classification example using MLFlow

## Usage

### Deploy Pipeline

```bash
# Deploy to test environment
python -m smus_cicd.cli deploy test --manifest examples/analytic-workflow/notebooks/manifest.yaml
```

### Run Workflow

```bash
# Execute all notebooks in parallel
python -m smus_cicd.cli run --workflow parallel_notebooks_workflow --targets test \
  --manifest examples/analytic-workflow/notebooks/manifest.yaml
```

### Run Tests

```bash
# Run integration test
pytest tests/integration/examples-analytics-workflows/notebooks/test_notebooks_workflow.py -v
```

## Architecture

- **Bundle Manifest**: `manifest.yaml` - Defines targets and bundle configuration
- **Workflow**: `workflows/parallel_notebooks_workflow.yaml` - Airflow DAG with 9 parallel tasks
- **Pipeline Tests**: `app_tests/test_notebooks_execution.py` - Validates execution success
- **Integration Test**: `tests/integration/.../test_notebooks_workflow.py` - End-to-end test

## Key Features

- **True Parallel Execution**: All 9 notebooks run simultaneously
- **No Dependencies**: Each notebook is independent
- **Native SMUS Operator**: Uses SageMakerNotebookOperator
- **Automatic Validation**: Workflow fails if any notebook fails
