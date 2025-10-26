# SMUS CLI Test Scripts

This directory contains scripts and utilities for SMUS (SageMaker Unified Studio) integration testing.

## 📁 Directory Structure

```
scripts/
├── setup/                          # 🆕 Organized setup scripts (USE THIS!)
│   ├── README.md                   # Comprehensive setup guide
│   ├── deploy-all.sh               # Deploy all stages
│   ├── 1-account-setup/            # Stage 1: OIDC, VPC
│   ├── 2-domain-creation/          # Stage 2: Create domain
│   ├── 3-domain-configuration/     # Stage 3: Blueprints, profiles
│   ├── 4-project-setup/            # Stage 4: Projects, memberships
│   └── 5-testing-infrastructure/   # Stage 5: MLflow, testing resources
├── datazone/                       # DataZone utilities
│   ├── setup-covid-data.py
│   ├── publish-covid-assets.py
│   └── ...
├── config.yaml                     # Configuration file
├── deploy-*.sh                     # Legacy individual scripts (still work)
└── *.yaml                          # CloudFormation templates
```

## 🚀 Quick Start

### For New Account Setup

Use the organized setup directory:

```bash
cd setup
./deploy-all.sh
```

See [setup/README.md](setup/README.md) for detailed documentation.

### For Individual Components

Legacy scripts still work for individual deployments:

```bash
./deploy-vpc.sh              # Deploy VPC
./deploy-domain.sh           # Deploy domain
./deploy-shared-resources.sh # Deploy MLflow and testing resources
```

## 📋 Setup Stages

The new organized structure provides 5 deployment stages:

1. **Account Setup** - Minimal requirements (OIDC, VPC)
2. **Domain Creation** - Create SMUS domain
3. **Domain Configuration** - Blueprints, profiles, permissions
4. **Project Setup** - Dev project and memberships
5. **Testing Infrastructure** - MLflow, databases, Lake Formation

Each stage can be run independently or all together.

## 🔧 Configuration

All scripts use `config.yaml`:

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
```

## 📚 Documentation

- **[setup/README.md](setup/README.md)** - Complete setup guide with scenarios
- **[setup/5-testing-infrastructure/README.md](setup/5-testing-infrastructure/README.md)** - Testing resources details
- **[../../development.md](../../development.md)** - Development and testing guide

## 🧪 DataZone Utilities

The `datazone/` directory contains utilities for:
- Setting up COVID-19 test data
- Publishing DataZone assets
- Managing data sources
- Creating cross-project subscriptions

## 🔄 Migration from Old Structure

If you were using the old scripts:

| Old Script | New Location |
|------------|--------------|
| `deploy-all.sh` | `setup/deploy-all.sh` |
| `deploy-vpc.sh` | `setup/1-account-setup/` |
| `deploy-domain.sh` | `setup/2-domain-creation/` |
| `deploy-blueprints-profiles.sh` | `setup/3-domain-configuration/` |
| `deploy-projects.sh` | `setup/4-project-setup/` |
| `deploy-shared-resources.sh` | `setup/5-testing-infrastructure/` |

Old scripts still work but use the new organized structure for better clarity.

## Prerequisites

- AWS CLI configured with appropriate permissions
- AWS Identity Center (IDC) enabled
- `yq` YAML processor installed: `brew install yq`

## For Complete Setup Instructions

See **[setup/README.md](setup/README.md)** for:
- Stage-by-stage deployment guide
- Common deployment scenarios
- Multi-region configuration
- Troubleshooting
- Resource outputs and usage
