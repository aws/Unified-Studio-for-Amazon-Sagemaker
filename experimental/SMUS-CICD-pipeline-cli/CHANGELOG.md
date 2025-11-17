# Changelog

All notable changes to the SMUS CI/CD Pipeline CLI will be documented in this file.

## [Unreleased]

### Added
- **Event Initialization**: Emit custom EventBridge events on deployment to trigger workflows
  - Support for custom event buses
  - Variable resolution in event details (${application.name}, ${stage.name}, etc.)
  - Automatic workflow triggering via EventBridge rules
  - See [docs/bootstrap-actions.md](docs/bootstrap-actions.md) for details

- **QuickSight Dashboard Deployment**: Export dashboards from dev and deploy to test/prod
  - Export dashboards with dependencies (datasets, data sources)
  - Import with override parameters (resource ID prefixes, names)
  - Automatic permission grants to users/groups
  - SPICE ingestion triggering
  - See [docs/quicksight-deployment.md](docs/quicksight-deployment.md) for details

- **Workflow Connection Type Detection**: Monitor command now correctly identifies serverless Airflow vs MWAA workflows
  - Uses connection name pattern matching as workaround for DataZone API limitation
  - Properly routes to serverless Airflow or MWAA health checks

### Changed
- **Manifest Schema**: Updated `initialization` to `bootstrap.actions[]` structure
  - Old format: `initialization: [{type, eventSource, ...}]`
  - New format: `bootstrap.actions: [{type, eventSource, ...}]`
  - All 15+ example manifests updated to new structure
  - See [docs/manifest-schema.md](docs/manifest-schema.md) for migration guide

- **Workflow Configuration**: Changed from `{workflowName, engine}` to `{workflowName, connectionName}`
  - Aligns with DataZone connection model
  - Supports multiple workflow types (serverless Airflow, MWAA)

### Fixed
- Deploy command now correctly detects workflows in `manifest.content.workflows`
- Workflow dict access fixed (use `workflow.get('workflowName')` instead of `workflow.workflow_name`)
- Monitor command properly distinguishes serverless Airflow from MWAA connections
- Connection update logic now deletes and recreates to ensure properties stay in sync

### Documentation
- Added [docs/bootstrap-actions.md](docs/bootstrap-actions.md) - Event initialization guide
- Added [docs/quicksight-deployment.md](docs/quicksight-deployment.md) - QuickSight deployment guide
- Updated [docs/manifest-schema.md](docs/manifest-schema.md) - New bootstrap and QuickSight sections
- Updated [README.md](README.md) - Added event and QuickSight features

## [0.1.0] - Initial Release

### Added
- Core CLI commands: bundle, deploy, monitor, test, describe
- Manifest-based application definition
- Multi-environment deployment (dev, test, prod)
- Serverless Airflow workflow deployment
- Storage deployment (S3, code, notebooks)
- Git repository integration
- Automated testing framework
- Integration with SageMaker Unified Studio projects
