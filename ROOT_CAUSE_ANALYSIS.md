# Root Cause Analysis: "multiple values for keyword argument 'Arguments'" Error

## Problem
Task 2 (`covid_data_summary`) fails with:
```
TypeError: botocore.client.ClientCreator._create_api_method.<locals>._api_call() got multiple values for keyword argument 'Arguments'
```

## Root Cause
The workflow YAML configuration has BOTH:
1. `script_args` at the task level
2. `Command.ScriptLocation` in `create_job_kwargs`

This causes the Airflow GlueJobOperator to pass the `Arguments` parameter TWICE to boto3's `start_job_run()` method:
- Once from `script_args` (converted to `Arguments`)
- Once from `create_job_kwargs.Command` (which may internally set `Arguments`)

## Evidence
From CloudWatch logs (2025-11-01T21:13:53):
```json
{
  "level": "error",
  "event": "Failed to run aws glue job, error: botocore.client.ClientCreator._create_api_method.<locals>._api_call() got multiple values for keyword argument 'Arguments'",
  "logger": "airflow.providers.amazon.aws.hooks.glue.GlueJobHook"
}
```

Error occurs at:
- File: `/usr/local/airflow/.local/lib/python3.12/site-packages/airflow/providers/amazon/aws/hooks/glue.py`
- Line: 247
- Method: `initialize_job`

## Why Task 1 Works But Task 2 Fails
Both tasks have IDENTICAL YAML structure, but the error only occurs for task 2. This suggests:
- A bug in the Airflow Serverless YAML parser that handles certain task/job names differently
- Possible caching or state issue in the Airflow operator
- Race condition or ordering issue in how parameters are processed

## Solution
Remove the `Command` section from `create_job_kwargs` since `script_location` already provides the script path:

```yaml
create_job_kwargs:
  GlueVersion: '4.0'
  MaxRetries: 0
  Timeout: 60
  # REMOVE THIS:
  # Command:
  #   Name: 'glueetl'
  #   PythonVersion: '3'
  #   ScriptLocation: '{proj.connection.default.s3_shared.s3Uri}etl/bundle/glue_print_params.py'
```

The `script_location` parameter at the task level is sufficient for the GlueJobOperator to create the job with the correct script.

## Alternative Solutions
1. Remove `script_args` and pass arguments via `create_job_kwargs.DefaultArguments`
2. Use only `create_job_kwargs.Command` and remove `script_location`
3. Rename the task/job to avoid whatever triggers the parser bug

## Next Steps
1. Test the fix by redeploying with `Command` section removed
2. If successful, update all workflow templates
3. Report bug to SMUS CICD CLI team or Airflow Serverless team
