# Account Pool Factory for SageMaker Unified Studio

An automated account provisioning and management system for SageMaker Unified Studio (DataZone) that maintains a pool of pre-configured AWS accounts ready for project assignment.

## Quick Start

### 1. Configure Environment

```bash
cd experimental/AccountPoolFactory

# Copy the template
cp config.yaml.template config.yaml

# Edit config.yaml with your values
# Required: aws.region, aws.account_id, datazone.domain_id
```

### 2. Configure AWS Credentials

Choose one method:
```bash
# Option 1: AWS CLI
aws configure

# Option 2: AWS SSO
aws sso login --profile your-profile

# Option 3: Isengard (Amazon internal)
eval $(isengardcli creds YOUR_PROFILE --role Admin)
```

### 3. Follow Testing Guide

See [docs/TestingGuide.md](docs/TestingGuide.md) for step-by-step testing instructions.

## Documentation

- **[docs/TestingGuide.md](docs/TestingGuide.md)** - Complete testing manual with step-by-step instructions
- **[docs/GettingStarted.md](docs/GettingStarted.md)** - Quick start guide for new users
- **[docs/ProjectStructure.md](docs/ProjectStructure.md)** - Project organization and directory structure
- **[specs/requirements.md](specs/requirements.md)** - Functional requirements and architecture
- **[specs/design.md](specs/design.md)** - Technical design document
- **[specs/tasks.md](specs/tasks.md)** - Implementation task breakdown

## Overview

The Account Pool Factory automatically provisions and manages a pool of AWS accounts that can be instantly assigned to new DataZone projects. It integrates with AWS Control Tower Account Factory for account creation and uses a custom Lambda function to provide accounts to DataZone through the custom account pool handler.

## Architecture

The solution operates across three types of AWS accounts:

1. **Organization Admin Account**: Contains AWS Control Tower Account Factory
2. **Domain Account**: Hosts the DataZone domain, account pool, and management Lambda functions
3. **Project Accounts**: Pre-configured accounts in the pool, ready for project assignment

## Project Structure

```
AccountPoolFactory/
├── README.md                          # This file
├── docs/                              # Documentation
│   ├── architecture.md                # Architecture diagrams and details
│   ├── deployment-guide.md            # Deployment instructions
│   ├── configuration-guide.md         # Configuration parameters
│   └── troubleshooting.md             # Common issues and solutions
├── specs/                             # Requirements and design specs
│   ├── requirements.md                # Functional and non-functional requirements
│   ├── design.md                      # Technical design document
│   └── tasks.md                       # Implementation task list
├── templates/                         # Infrastructure as Code templates
│   ├── cloudformation/                # CloudFormation templates (default)
│   │   ├── 01-org-admin/              # CF1: Org Admin account setup
│   │   ├── 02-domain-account/         # CF2: Domain account setup
│   │   └── 03-project-account/        # CF3: Project account setup
│   ├── cdk/                           # AWS CDK (future)
│   └── terraform/                     # Terraform (future)
├── src/                               # Lambda function source code
│   ├── account-provider/              # DataZone custom account provider Lambda
│   ├── pool-manager/                  # Pool management and replenishment Lambda
│   ├── account-creator/               # Control Tower account creation trigger Lambda
│   ├── setup-orchestrator/            # Account setup orchestration Lambda
│   └── shared/                        # Shared utilities and libraries
├── tests/                             # Test suites
│   ├── unit/                          # Unit tests
│   ├── integration/                   # Integration tests
│   └── fixtures/                      # Test data and fixtures
├── examples/                          # Example configurations
│   ├── minimal/                       # Minimal working configuration
│   ├── production/                    # Production-ready configuration
│   └── custom/                        # Custom blueprint configurations
└── scripts/                           # Utility scripts
    ├── deploy.sh                      # Deployment automation
    ├── validate.sh                    # Configuration validation
    └── cleanup.sh                     # Resource cleanup

```

## Quick Start

See [docs/deployment-guide.md](docs/deployment-guide.md) for detailed deployment instructions.

## Configuration

All operational parameters are configurable. See [docs/configuration-guide.md](docs/configuration-guide.md) for details.

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Deployment Guide](docs/deployment-guide.md)
- [Configuration Guide](docs/configuration-guide.md)
- [Troubleshooting](docs/troubleshooting.md)

## Requirements

- AWS Control Tower enabled in the organization
- DataZone domain created
- Appropriate IAM permissions for deployment
- Python 3.12+ (for Lambda functions)

## License

See LICENSE file for details.
