# Q CLI Conversation Examples

This document shows realistic conversations between users and Q CLI using the SMUS MCP integration.

## Scenario 1: Create CICD for AWS Glue Job

### Conversation Flow

**User:** I want to create CICD for my Glue job in this project

**Q:** I can help you create a CICD pipeline for your Glue job. Let me search for relevant templates.

*[Q calls: query_smus_kb("glue etl pipeline")]*

**Q:** I found ETL pipeline templates that work well with Glue jobs. These pipelines support:
- Multiple environments (dev, test, prod)
- Automated deployments
- Workflow orchestration with Airflow

Would you like me to generate a bundle manifest for you?

**User:** Yes, please. I need dev, test, and prod environments.

**Q:** Perfect! I'll create an ETL pipeline with those three environments.

*[Q calls: get_pipeline_example("etl")]*

**Q:** Here's your `manifest.yaml`:

```yaml
bundleName: ETLBundle

stages:
  dev:
    stage: DEV
    default: true
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION}
    project:
      name: dev-project
    deployment_configuration:
      storage:
        - name: glue-scripts
          connectionName: default.s3_shared
          targetDirectory: glue/scripts

  test:
    stage: TEST
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION}
    project:
      name: test-project
    bootstrap:
      project:
        create: true

  prod:
    stage: PROD
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION}
    project:
      name: prod-project

bundle:
  storage:
    - name: glue-scripts
      connectionName: default.s3_shared
      include: ['glue/**/*.py']
      exclude: ['**/__pycache__/', '**/*.pyc']

activation:
  workflows:
    - workflowName: deploy_glue_jobs
      connectionName: project.workflow_serverless
      engine: airflow-serverless
    triggerPostDeployment: true
```

This pipeline will:
1. Bundle your Glue scripts from the `glue/` directory
2. Deploy to dev, test, and prod environments
3. Trigger an Airflow workflow after deployment

**User:** Great! Can you also generate GitHub Actions workflow for this?

**Q:** Absolutely! Let me find the GitHub Actions integration documentation.

*[Q calls: query_smus_kb("github actions workflow")]*

**Q:** Here's a GitHub Actions workflow for your pipeline:

```yaml
# .github/workflows/deploy.yml
name: Deploy SMUS Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SMUS CLI
        run: pip install smus-cicd-cli
      
      - name: Deploy to Dev
        if: github.ref == 'refs/heads/main'
        run: smus-cli deploy -p manifest.yaml -t dev
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
      
      - name: Deploy to Test
        if: github.ref == 'refs/heads/main'
        run: smus-cli deploy -p manifest.yaml -t test
      
      - name: Deploy to Prod (Manual Approval)
        if: github.event_name == 'workflow_dispatch'
        run: smus-cli deploy -p manifest.yaml -t prod
```

This workflow will:
- Deploy to dev and test automatically on main branch
- Require manual trigger for prod deployment
- Use GitHub secrets for AWS credentials

**User:** Perfect! This is exactly what I needed.

---

## Scenario 2: Deploy Jupyter Notebooks

### Conversation Flow

**User:** I need to deploy Jupyter notebooks to dev and prod environments

**Q:** I can help you set up a notebook deployment pipeline. Let me get you a template.

*[Q calls: get_pipeline_example("notebooks")]*

**Q:** Here's a notebook deployment pipeline:

```yaml
bundleName: NotebookBundle

stages:
  dev:
    stage: DEV
    default: true
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION}
    project:
      name: dev-notebooks
    deployment_configuration:
      storage:
        - name: notebooks
          connectionName: default.s3_shared
          targetDirectory: notebooks

  prod:
    stage: PROD
    domain:
      name: ${DOMAIN_NAME}
      region: ${AWS_REGION}
    project:
      name: prod-notebooks

bundle:
  storage:
    - name: notebooks
      connectionName: default.s3_shared
      include: ['notebooks/*.ipynb']
      exclude: ['.ipynb_checkpoints/']
```

**User:** How do I configure S3 storage for the notebooks?

**Q:** The pipeline uses S3 storage through connections. Here's what you need to know:

*[Q calls: query_smus_kb("s3 storage bundle")]*

The `bundle.storage` section defines what gets bundled:
- `include`: Patterns for files to include (e.g., `notebooks/*.ipynb`)
- `exclude`: Patterns to exclude (e.g., `.ipynb_checkpoints/`)

The `deployment_configuration.storage` section defines where files are deployed:
- `connectionName`: S3 connection (e.g., `default.s3_shared`)
- `targetDirectory`: Destination path in S3

Your notebooks will be:
1. Bundled from local `notebooks/` directory
2. Uploaded to S3 via the connection
3. Available in the target project's storage

**User:** Thanks! That makes sense.

---

## Scenario 3: Validate Existing Pipeline

### Conversation Flow

**User:** Can you validate my manifest.yaml file?

**Q:** I can validate your pipeline against the official schema. Please share your manifest.yaml content.

**User:** [Pastes manifest.yaml content]

**Q:** Let me validate that for you.

*[Q calls: validate_pipeline(yaml_content)]*

**Q:** ✅ Pipeline is valid!

**Pipeline Details:**
- Pipeline: MyDataPipeline
- Targets: dev, test, prod
- Bundle sections: 2
- Workflows: 1

Validated against pipeline-manifest-schema.yaml

Your pipeline looks good! All required fields are present and properly formatted.

---

## Scenario 4: Troubleshoot Pipeline Error

### Conversation Flow

**User:** My pipeline validation is failing with an error about missing 'stage' field

**Q:** Let me help you fix that. The `stage` field is required for each target. Let me search for the correct format.

*[Q calls: query_smus_kb("target stage required")]*

**Q:** Each target must have a `stage` field with one of these values:
- DEV
- TEST
- PROD

Here's the correct format:

```yaml
stages:
  dev:
    stage: DEV  # Required!
    domain:
      name: ${DOMAIN_NAME}
```

Make sure all your targets have the `stage` field set.

**User:** Thanks! I'll add that.

---

## Scenario 5: Add Monitoring to Pipeline

### Conversation Flow

**User:** How do I add CloudWatch monitoring to my pipeline?

**Q:** Let me search for monitoring configuration options.

*[Q calls: query_smus_kb("monitoring cloudwatch")]*

**Q:** You can add monitoring to your pipeline using the `monitoring` section:

```yaml
stages:
  prod:
    stage: PROD
    monitoring:
      enabled: true
      alarms:
        - name: WorkflowFailures
          metric: WorkflowExecutionsFailed
          threshold: 1
          evaluationPeriods: 1
```

This will:
- Enable CloudWatch monitoring for the target
- Create alarms for workflow failures
- Send notifications when thresholds are exceeded

Would you like me to show you more monitoring options?

**User:** Yes, what other metrics can I monitor?

**Q:** Common metrics include:
- `WorkflowExecutionsFailed` - Failed workflow runs
- `WorkflowExecutionTime` - Execution duration
- `DeploymentFailures` - Failed deployments
- `BundleSize` - Size of deployed bundles

You can configure alarms for any of these metrics.

---

## Testing These Scenarios

These conversation examples are also available as automated tests in:
- `tests/integration/scenarios/*.yaml` - Scenario definitions
- `tests/integration/test_qcli_conversations.py` - Test runner

Run tests with:
```bash
pytest tests/integration/test_qcli_conversations.py -v
```
