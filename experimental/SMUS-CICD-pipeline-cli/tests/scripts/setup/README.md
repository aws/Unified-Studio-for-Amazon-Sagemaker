# SMUS Integration Testing Setup

This directory contains setup scripts for SMUS integration testing environments.

## Directory Structure

### iam-based-domains/
Setup for domains using IAM authentication (no IDC required).

**Steps**: 1 → 4 → 5
- 1-account-setup
- 4-project-setup
- 5-testing-infrastructure

### idc-based-domains/
Setup for domains using AWS IAM Identity Center (IDC) authentication.

**Steps**: 1 → 2 → 3 → 4 → 5
- 1-account-setup
- 2-domain-creation
- 3-domain-configuration
- 4-project-setup
- 5-testing-infrastructure

## Quick Start

### For IAM-Based Domains
```bash
cd iam-based-domains
cd 1-account-setup && ./deploy.sh
cd ../4-project-setup && ./deploy.sh
cd ../5-testing-infrastructure && ./deploy.sh
```

### For IDC-Based Domains
```bash
cd idc-based-domains
cd 1-account-setup && ./deploy.sh
cd ../2-domain-creation && ./deploy.sh
cd ../3-domain-configuration && ./deploy.sh
cd ../4-project-setup && ./deploy.sh
cd ../5-testing-infrastructure && ./deploy.sh
```

## Notes

- Each step must complete successfully before proceeding to the next
- Configuration files (config.yaml) are required in each step directory
- Outputs from each step are stored in /tmp for use by subsequent steps
