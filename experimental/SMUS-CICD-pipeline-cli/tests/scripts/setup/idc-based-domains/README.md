# IDC-Based Domain Setup

Setup scripts for SMUS domains using AWS IAM Identity Center (IDC) authentication.

## Setup Steps

1. **1-account-setup** - AWS account base configuration (VPC, IAM roles, GitHub OIDC)
2. **2-domain-creation** - Create SageMaker Unified Studio domain
3. **3-domain-configuration** - Configure domain blueprints and profiles
4. **4-project-setup** - Create SMUS projects
5. **5-testing-infrastructure** - Deploy testing resources (MLflow, S3, test data)

## Usage

```bash
# Run all steps in order
cd 1-account-setup && ./deploy.sh
cd ../2-domain-creation && ./deploy.sh
cd ../3-domain-configuration && ./deploy.sh
cd ../4-project-setup && ./deploy.sh
cd ../5-testing-infrastructure && ./deploy.sh
```

## Notes

- IDC-based domains require all 5 steps
- Domain must be created and configured before projects
- Requires AWS IAM Identity Center to be set up in the account
