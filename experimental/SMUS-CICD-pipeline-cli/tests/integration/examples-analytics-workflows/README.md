# Analytics Workflows Integration Tests

Integration tests for analytics workflows from `examples/analytic-workflow/`.

## Project Naming Convention

To enable parallel test execution, each analytics workflow test uses a unique test project:

- **Shared Dev Project**: `dev-marketing` (read-only, shared by all tests)
- **Reserved Projects**: `test-marketing`, `prod-marketing` (long-standing, not for CI/CD tests)
- **Test Projects** (created/deleted by tests):
  - `test-dashboard-quick` - Dashboard with Glue and QuickSight
  - `test-ml-training` - ML training workflow
  - `test-ml-deployment` - ML deployment workflow
  - `test-genai` - GenAI workflow
  - `test-notebooks` - Notebooks workflow

Each test creates its own project, allowing tests to run in parallel without conflicts.

## Structure

```
examples-analytics-workflows/
├── ml/
│   ├── ml_pipeline.yaml          # ML workflow pipeline config
│   └── test_ml_workflow.py       # ML workflow integration test
└── etl/
    ├── etl_pipeline.yaml         # ETL workflow pipeline config
    └── test_etl_workflow.py      # ETL workflow integration test
```

## Tests

### ML Workflow Test (`ml/`)
- **Pipeline**: `IntegrationTestMLWorkflow`
- **Workflow**: `ml_dev_workflow_v3`
- **Source**: `examples/analytic-workflow/ml/`
- **Tasks**: 1 notebook (training → MLflow → batch inference)
- **Runtime**: ~14.5 minutes

### ETL Workflow Test (`etl/`)
- **Pipeline**: `IntegrationTestETLWorkflow`
- **Workflow**: `s3_analytics_workflow_3`
- **Source**: `examples/analytic-workflow/etl/`
- **Tasks**: 2 Glue jobs (database discovery → data summary)
- **Runtime**: ~5-10 minutes

## Configuration

Both tests use the same projects (aligned with `basic_pipeline`):
- **dev**: `dev-marketing` (us-east-2)
- **test**: `test-marketing` (us-east-1, BETA_10282025_Domain)
- **Database**: `analytic_workflow_test_db`
- **Role**: `arn:aws:iam::*:role/SMUSCICDTestRole`

## Running Tests

Run individual tests:
```bash
pytest tests/integration/examples-analytics-workflows/ml/test_ml_workflow.py -v -s
pytest tests/integration/examples-analytics-workflows/etl/test_etl_workflow.py -v -s
```

Run all analytics tests:
```bash
pytest tests/integration/examples-analytics-workflows/ -v -s
```

## Test Pattern

Both tests follow the same 8-step pattern:
1. Describe with connections
2. Upload code to S3
3. Bundle
4. Deploy
5. Monitor
6. Run workflow
7. Monitor workflow status
8. Fetch workflow logs

## Key Features

- No code duplication (references `examples/` directly)
- Independent test execution
- Shared projects and database
- Production-ready validation
