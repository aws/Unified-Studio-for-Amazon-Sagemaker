# IAM-Based Domain Setup

Setup scripts for SMUS domains using IAM authentication.

## Setup Steps

1. **1-account-setup** - AWS account base configuration (VPC, IAM roles, GitHub OIDC)
2. **4-project-setup** - Create SMUS projects
3. **5-testing-infrastructure** - Deploy testing resources (MLflow, S3, test data)

## Usage

```bash
# Run all steps in order
cd 1-account-setup && ./deploy.sh
cd ../4-project-setup && ./deploy.sh
cd ../5-testing-infrastructure && ./deploy.sh
```

## Notes

- IAM-based domains do not require domain creation (step 2) or domain configuration (step 3)
- Projects are created directly without IDC integration
