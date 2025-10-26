# SMUS Integration Testing Setup

Modular setup scripts for SMUS (SageMaker Unified Studio) integration testing and GitHub workflows.

## 📁 Directory Structure

```
setup/
├── deploy-all.sh                    # Master script - runs all stages
├── README.md                        # This file
│
├── 1-account-setup/
│   ├── deploy.sh                    # Single script for this stage
│   ├── README.md                    # Stage documentation
│   ├── github-oidc-role.yaml
│   └── vpc-template.yaml
│
├── 2-domain-creation/
│   ├── deploy.sh
│   ├── README.md
│   └── sagemaker-domain.yaml
│
├── 3-domain-configuration/
│   ├── deploy.sh
│   ├── README.md
│   └── blueprints-profiles.yaml
│
├── 4-project-setup/
│   ├── deploy.sh
│   ├── README.md
│   └── create_project.yaml
│
└── 5-testing-infrastructure/
    ├── deploy.sh
    ├── README.md
    ├── shared-resources-template.yaml
    └── [COVID test data scripts]
```

## 🚀 Quick Start

### Full Deployment

Deploy all stages in sequence:

```bash
./deploy-all.sh [path/to/config.yaml]
```

### Individual Stage Deployment

Each stage is independent and can be run separately:

```bash
cd 1-account-setup && ./deploy.sh [config.yaml]
cd 2-domain-creation && ./deploy.sh [config.yaml]
cd 3-domain-configuration && ./deploy.sh [config.yaml]
cd 4-project-setup && ./deploy.sh [config.yaml]
cd 5-testing-infrastructure && ./deploy.sh [config.yaml]
```

## 📋 Deployment Stages

### Stage 1: Account Minimal Setup
**What:** GitHub OIDC role, VPC infrastructure  
**When:** First-time account setup  
**Outputs:** VPC ID, subnets, GitHub role ARN  
**Docs:** [1-account-setup/README.md](1-account-setup/README.md)

### Stage 2: Domain Creation
**What:** SageMaker Unified Studio domain  
**When:** After Stage 1, or skip if domain exists  
**Outputs:** Domain ID, domain ARN, portal URL  
**Docs:** [2-domain-creation/README.md](2-domain-creation/README.md)

### Stage 3: Domain Configuration
**What:** Environment blueprints, project profiles  
**When:** After domain exists (Stage 2 or manual)  
**Outputs:** Enabled blueprints list  
**Docs:** [3-domain-configuration/README.md](3-domain-configuration/README.md)

### Stage 4: Project Setup
**What:** Dev project, project memberships  
**When:** After Stage 3  
**Outputs:** Project ID, membership details  
**Docs:** [4-project-setup/README.md](4-project-setup/README.md)

### Stage 5: Testing Infrastructure
**What:** MLflow server, SageMaker role, test data  
**When:** Anytime (independent of other stages)  
**Outputs:** MLflow ARN, role ARN, S3 bucket  
**Docs:** [5-testing-infrastructure/README.md](5-testing-infrastructure/README.md)

## 🔧 Configuration

### config.yaml Structure

```yaml
account_id: "123456789012"
regions:
  primary:
    name: us-east-1
    enabled: true
  secondary:
    name: us-west-2
    enabled: false

domain:
  name: smus-integration-domain
  admin_user: admin@example.com

github:
  org: your-org
  repo: your-repo
```

## 🎯 Common Scenarios

### Scenario 1: Fresh Account Setup
```bash
./deploy-all.sh
```

### Scenario 2: Domain Created Manually
```bash
cd 1-account-setup && ./deploy.sh
cd ../3-domain-configuration && ./deploy.sh
cd ../4-project-setup && ./deploy.sh
cd ../5-testing-infrastructure && ./deploy.sh
```

### Scenario 3: Only Testing Infrastructure
```bash
cd 5-testing-infrastructure
./deploy.sh
```

### Scenario 4: Update Domain Configuration
```bash
cd 3-domain-configuration
./deploy.sh
```

### Scenario 5: Multi-Region Deployment
Enable regions in config.yaml, then run stages. Each stage deploys to all enabled regions.

## 📊 Resource Outputs

After deployment, resource information is saved to `/tmp/`:

| File | Content | Stage |
|------|---------|-------|
| `vpc_id_<region>.txt` | VPC ID | 1 |
| `subnets_<region>.txt` | Subnet IDs | 1 |
| `azs_<region>.txt` | Availability zones | 1 |
| `mlflow_arn_<region>.txt` | MLflow ARN | 5 |
| `sagemaker_role_arn_<region>.txt` | Execution role ARN | 5 |
| `mlflow_bucket_<region>.txt` | S3 bucket name | 5 |

### Using Outputs in Tests

```python
# Read outputs
with open('/tmp/mlflow_arn_us-east-1.txt') as f:
    MLFLOW_ARN = f.read().strip()

# Use in tests
mlflow.set_tracking_uri(f"aws://{MLFLOW_ARN}")
```

## 🔄 Stage Independence

Each stage is designed to be independent:

- **Stage 1** requires only AWS credentials
- **Stage 2** requires VPC from Stage 1 (or existing VPC)
- **Stage 3** requires domain (from Stage 2 or manual)
- **Stage 4** requires domain configuration from Stage 3
- **Stage 5** is completely independent - can run anytime

Pass information between stages using:
1. CloudFormation outputs (automatic)
2. `/tmp/` files (for cross-stage reference)
3. Config file parameters

## 🔍 Troubleshooting

### Stack in ROLLBACK_COMPLETE
Scripts automatically detect and delete failed stacks before redeploying.

### VPC Already Exists
Stage 1 checks for existing VPCs with tag `CreatedForUseWithSageMakerUnifiedStudio=true` and reuses them.

### Domain Already Exists
Skip Stage 2 and run Stage 3 to configure existing domain.

### Permission Errors
Ensure AWS credentials have:
- CloudFormation full access
- IAM role creation
- SageMaker full access
- DataZone full access
- S3 full access

## 🧪 Integration Testing

After setup:

```python
# tests/integration/config.py
MLFLOW_TRACKING_SERVER_ARN = "arn:aws:sagemaker:us-east-1:123456789012:mlflow-tracking-server/smus-integration-mlflow"
SAGEMAKER_EXECUTION_ROLE_ARN = "arn:aws:iam::123456789012:role/service-role/AmazonSageMaker-ExecutionRole-..."
```

## 🔄 GitHub Workflows

Use OIDC role from Stage 1:

```yaml
permissions:
  id-token: write
  contents: read

jobs:
  test:
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsRole
          aws-region: us-east-1
```

## 🗑️ Cleanup

Delete stacks in reverse order:

```bash
aws cloudformation delete-stack --stack-name smus-shared-resources --region us-east-1
aws cloudformation delete-stack --stack-name dev-project --region us-east-1
aws cloudformation delete-stack --stack-name blueprints-profiles --region us-east-1
aws cloudformation delete-stack --stack-name sagemaker-unified-studio-domain --region us-east-1
aws cloudformation delete-stack --stack-name sagemaker-unified-studio-vpc --region us-east-1
aws cloudformation delete-stack --stack-name smus-cli-github-integration --region us-east-1
```

## 📚 Additional Resources

- [SMUS Administrator Guide](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/adminguide/)
- [SMUS User Guide](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/)
- [MLflow on SageMaker](https://docs.aws.amazon.com/sagemaker/latest/dg/mlflow.html)
