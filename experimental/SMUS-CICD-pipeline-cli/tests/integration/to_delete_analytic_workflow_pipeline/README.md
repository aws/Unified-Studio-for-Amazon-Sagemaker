# Analytic Workflow Pipeline Integration Test

This integration test validates the deployment of the ML workflow example from `examples/analytic-workflow` using the SMUS CICD pipeline.

## Test Structure

- `analytic_workflow_pipeline.yaml` - CICD pipeline manifest that references the analytic-workflow example
- `test_analytic_workflow_pipeline.py` - Integration test implementation
- `pipeline_tests/` - Directory for pipeline-specific tests

## What This Test Does

1. **Bundle Creation**: Packages the ML workflow from `examples/analytic-workflow`
2. **Project Setup**: Auto-creates `analytic-workflow-test` project in `cicd-test-domain`
3. **Deployment**: Deploys the ML workflow bundle to the test environment
4. **Validation**: Verifies the deployment was successful

## Bundle Sources

The test bundles the following from `examples/analytic-workflow`:
- `workflows/` - ML workflow definitions (Airflow DAGs)
- `scripts/` - ML training and orchestration scripts

## Target Environments

- **Dev**: Uses existing `dev-marketing` project
- **Test**: Creates new `analytic-workflow-test` project with ML capabilities

## Running the Test

```bash
cd experimental/SMUS-CICD-pipeline-cli
pytest tests/integration/analytic_workflow_pipeline/test_analytic_workflow_pipeline.py -v -s
```

## Expected Outcomes

- ✅ Bundle creation with ML workflow components
- ✅ Test project creation with Lakehouse Database configuration
- ✅ Successful deployment of ML workflows to test environment
- ✅ Validation that the ML pipeline is ready for execution
