# Stage 4: Project Setup

Creates dev project and configures project memberships.

## What Gets Deployed

1. **Dev Project** - Development project in SMUS domain
2. **Project Memberships** - User assignments with appropriate roles

## Usage

```bash
./deploy.sh [path/to/config.yaml]
```

## Prerequisites

- Stage 3 completed (blueprints and profiles configured)
- Domain ID available
- Admin user configured in AWS Identity Center

## CloudFormation Stack Created

- `dev-project` - Development project

## Project Roles Configured

- PROJECT_OWNER - Full project access
- PROJECT_CONTRIBUTOR - Can create and manage resources
- PROJECT_VIEWER - Read-only access

## Next Steps

Run Stage 5 to deploy testing infrastructure (MLflow, test data, etc.).

## Note

Test and prod projects are created automatically by the CLI when needed:
- `smus-cli initialize test`
- `smus-cli initialize prod`
