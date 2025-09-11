# SMUS CLI Deployment Scripts

This directory contains deployment scripts for setting up the AWS infrastructure required by the SMUS CLI.

## Quick Start

Deploy all infrastructure in the correct order:

```bash
./deploy-all.sh [config-file]
```

## Individual Scripts

- `deploy-github-integration.sh` - GitHub OIDC integration for CI/CD
- `deploy-vpc.sh` - Multi-region VPC infrastructure  
- `deploy-domain.sh` - DataZone domain and IAM roles
- `deploy-blueprints-profiles.sh` - Environment blueprints and profiles
- `deploy-projects.sh` - Dev project with user membership
- `deploy-memberships.sh` - Additional project memberships

## Configuration

All scripts support config file override:
```bash
./script-name.sh config-6778.yaml
```

Default configuration file: `config.yaml`

## Prerequisites

- AWS CLI configured with appropriate permissions
- AWS Identity Center (IDC) enabled
- `yq` YAML processor installed

## For Complete Setup Instructions

See [development.md](../../development.md) for:
- Detailed deployment progression
- Integration testing setup
- GitHub workflow configuration
- Troubleshooting guide
