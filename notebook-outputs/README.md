# Data Notebooks Workflow Execution Results

## Workflow Run: 19596863465
**Date**: 2025-11-22 14:28 EST  
**Status**: FAILED  
**Target**: test-marketing

---

## Execution Summary

| # | Notebook | Status | Execution ID |
|---|----------|--------|--------------|
| 00 | basic_python_pandas | ✅ COMPLETED | 1611a538-2328-44b6-a246-757923f86ad7 |
| 04 | gdc_athena | ❌ FAILED | 276e4932-e3e3-4b9a-927f-a49451ec3d74 |
| 05 | customer_churn_spark | ❌ FAILED | 7a70255a-c595-42ec-a40a-c99e763aee7e |
| 06 | purchase_analytics_duckdb | ❌ FAILED | 380a6120-4689-47e7-8452-535c3a715fa4 |
| 08 | genai_etl_pandas | ❌ FAILED | 4715d103-1359-4a6b-accf-2dd7ef2d03ce |
| 09 | city_temperature_spark | ❌ FAILED | 0badc75d-acd1-4d35-ba5b-4df50ec27c28 |
| 10 | time_series_chronos | ❌ FAILED | 44afeeae-e733-4e89-872a-1c3562ba3baa |
| 11 | movie_sales_dynamodb | ❌ FAILED | 3a1a76c9-ee21-4a63-8d03-1c6997d280c0 |
| 12 | classification_mlflow | ❌ FAILED | a44441f0-9bf9-43af-ac82-d231dc522ef9 |

**Results**: 1/9 notebooks completed (11% success rate)

---

## Failure Analysis

### Common Error Pattern
All failed notebooks encountered the same error:

```
AlgorithmError: [SM-111] Error with executing notebook
[root] ERROR | Cannot detect dual stack: [Errno 2] No such file or directory: 
'/opt/ml/metadata/resource-metadata.json'
```

### Root Cause
Missing metadata file in SageMaker notebook execution environment:
- File: `/opt/ml/metadata/resource-metadata.json`
- Impact: Notebooks fail at initialization before executing any cells
- Scope: Affects all notebooks except simple pandas (no special dependencies)

### Why notebook_00_pandas Succeeded
- Simple pandas operations only
- No Spark, Athena, DuckDB, GenAI, or other advanced dependencies
- Doesn't require the missing metadata file

### Why Others Failed
All failed notebooks use advanced features:
- **04_athena**: AWS Glue Data Catalog / Athena queries
- **05_spark**: Spark for customer churn analysis
- **06_duckdb**: DuckDB for purchase analytics
- **08_genai**: GenAI/Bedrock integration
- **09_temperature**: Spark for temperature data
- **10_chronos**: Time series forecasting
- **11_dynamodb**: DynamoDB integration
- **12_mlflow**: MLflow tracking

---

## Source Notebooks Location
`experimental/SMUS-CICD-pipeline-cli/examples/analytic-workflow/data-notebooks/notebooks/`

## Execution Info
Full execution details saved in: `notebook-execution-info.json`

---

## Next Steps

1. **Investigate environment setup**: Why is `resource-metadata.json` missing?
2. **Check IAM permissions**: Verify notebook execution role has required permissions
3. **Review bootstrap process**: Ensure metadata file is created during initialization
4. **Test manually**: Run a single failed notebook to isolate the issue
5. **Compare environments**: Check what's different between simple pandas vs. advanced notebooks
