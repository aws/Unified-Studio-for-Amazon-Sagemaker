# Account Setup Scripts

This directory contains scripts for setting up the AWS account infrastructure needed for SMUS CI/CD testing.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Permissions to create IAM roles, VPCs, and CloudFormation stacks

## Scripts

### 1. deploy.sh
Main deployment script that sets up all required infrastructure:
- VPC with public/private subnets
- GitHub OIDC provider and role for GitHub Actions
- S3 bucket for artifacts

Usage:
```bash
./deploy.sh
```

### 2. create-stage-roles.sh
Creates all IAM roles needed for a SMUS project stage:
- Project role (for DataZone project)
- Bedrock agent execution role
- Bedrock agent Lambda role
- Managed policies for Bedrock testing

Usage:
```bash
./create-stage-roles.sh test-marketing-role
./create-stage-roles.sh prod-marketing-role
```

## CloudFormation Templates

### vpc-template.yaml
Creates VPC infrastructure:
- VPC with CIDR 10.0.0.0/16
- 2 public subnets
- 2 private subnets
- Internet Gateway, NAT Gateways, Route tables

### github-oidc-role.yaml
Creates GitHub Actions integration:
- OIDC provider for GitHub Actions
- IAM role that GitHub Actions can assume
- Permissions for deploying to AWS

### stage-roles.yaml
Creates all IAM roles for a project stage:
- Project role with trust policy for 10 AWS services
- Bedrock agent execution role (DEFAULT_AgentExecutionRole)
- Bedrock agent Lambda role (test_agent-lambda-role-{region}-{account})
- BedrockTestingPolicy (Lambda and IAM role management)
- BedrockAgentPassRolePolicy (PassRole for Bedrock agent)

## Outputs

After running deploy.sh:
- VPC ID and subnet IDs
- GitHub Actions role ARN
- S3 bucket name for artifacts

After running create-stage-roles.sh:
- Project role ARN
- Bedrock agent role ARN
- Bedrock agent Lambda role ARN
