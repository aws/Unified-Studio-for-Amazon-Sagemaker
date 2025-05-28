# AWS DataZone Domain Setup

## Table of Contents
1. [Overview](#overview)
2. [Templates](#templates)
   - [create_domain.yaml](#1-create_domainyaml)
   - [fetch_accounts.yml](#2-fetch_accountsyml)
   - [create_resource_share.yaml](#3-create_resource_shareyaml)
   - [enable_all_blueprints.yaml](#4-enable_all_blueprintsyaml)
   - [create_project_profiles.yaml](#5-create_project_profilesyaml)
   - [policy_grant.yaml](#6-policy_grantyaml)
3. [Prerequisites](#prerequisites)
4. [Deployment Instructions](#deployment-instructions)
5. [Important Considerations](#important-considerations)
6. [Troubleshooting](#troubleshooting)
7. [Maintenance and Updates](#maintenance-and-updates)
8. [Security Notes](#security-notes)

## Overview

This repository contains a set of AWS CloudFormation templates for setting up and configuring an AWS DataZone domain with various resources and capabilities. The setup includes creating a domain, enabling blueprints, setting up project profiles, and configuring necessary permissions (grants).

## Templates

### 1. create_domain.yaml

The primary template that orchestrates the entire setup process.

#### Parameters:
```yaml
Parameters:
  DomainName:
    Type: String
    Description: Name of the DataZone domain

  OrganizationId:
    Type: String
    Description: AWS Organizations ID

  DomainExecutionRole:
    Type: String
    Description: IAM role ARN for domain execution

  ServiceRole:
    Type: String
    Description: IAM service role ARN for the domain

  AmazonSageMakerManageAccessRole:
    Type: String
    Description: IAM role ARN to manage access to SageMaker environments

  AmazonSageMakerProvisioningRole:
    Type: String
    Description: IAM role ARN to provision SageMaker environments

  DZS3Bucket:
    Type: String
    Description: S3 bucket name for Tooling environment

  SageMakerSubnets:
    Type: String
    Description: Comma-separated list of subnet IDs for SageMaker

  AmazonSageMakerVpcId:
    Type: String
    Description: VPC ID for SageMaker
```

#### Resources:
- `Domain`: Creates the AWS DataZone domain
- `FetchOrganisationAccountIdsStack`: Nested stack for fetching organization accounts
- `TestResourceShareStack`: Nested stack for resource sharing
- `EnableBlueprintsStack`: Nested stack for enabling blueprints
- `ProjectProfileStack`: Nested stack for creating project profiles
- `PolicyGrantStack`: Nested stack for configuring permissions

### 2. fetch_accounts.yml

Lambda function to retrieve active AWS Organization account IDs.

#### Resources:
```yaml
Resources:
  GetActiveOrgAccountIdsLambda:
    Type: AWS::Lambda::Function
    Properties:
      # Lambda function configuration for listing organization accounts

  LambdaRole:
    Type: AWS::IAM::Role
    Properties:
      # IAM role with permissions to list organization accounts
```

#### Outputs:
```yaml
Outputs:
  AccountIds:
    Value: !Join [ ",", !Split [ "|" , !GetAtt GetActiveOrgAccountIds.AccountIds ]]
    Export:
      Name: OrgAccountIds
```

### 3. create_resource_share.yaml

Sets up AWS RAM resource sharing for the DataZone domain.

#### Parameters:
```yaml
Parameters:
  DomainId:
    Description: Domain for which blueprint needs to be enabled
    Type: String
  DomainName:
    Description: Name of the Domain
    Type: String
  DomainARN:
    Description: ARN of the Domain
    Type: String
  AccountsForResourceShare:
    Description: Owner AccountId for domain
    Type: CommaDelimitedList
```

#### Resources:
```yaml
Resources:
  "Fn::ForEach::Accounts":
    # Creates RAM resource shares for each account
```

### 4. enable_all_blueprints.yaml

Enables various blueprints for the DataZone domain.

#### Parameters:
```yaml
Parameters:
  DomainId:
    Type: String
  AmazonSageMakerManageAccessRole:
    Type: String
  AmazonSageMakerProvisioningRole:
    Type: String
  DZS3Bucket:
    Type: String
  SageMakerSubnets:
    Type: String
  AmazonSageMakerVpcId:
    Type: String
```

#### Resources:
Enables the following blueprints:
- LakehouseCatalog
- AmazonBedrockGuardrail
- MLExperiments
- Tooling
- RedshiftServerless
- EmrServerless
- Workflows
- AmazonBedrockPrompt
- DataLake
- AmazonBedrockEvaluation
- AmazonBedrockKnowledgeBase
- PartnerApps
- AmazonBedrockChatAgent
- AmazonBedrockFunction
- AmazonBedrockFlow
- EmrOnEc2

#### Outputs:
- IDs for all enabled blueprints


### 5. create_project_profiles.yaml

Creates project profiles with specific capabilities.

#### Parameters:
```yaml
Parameters:
  DomainId:
    Type: String
  DomainUnitId:
    Type: String
  AccountId:
    Type: String
  Region:
    Type: String
  # Blueprint ID Parameters for all enabled blueprints
```

#### Resources:
1. SQL Analytics Profile:
    - Tooling configuration
    - Lakehouse Database
    - Redshift Serverless
    - OnDemand Redshift Serverless
    - OnDemand Catalog for RMS

2. All Capabilities Profile:
    - All SQL Analytics capabilities
    - OnDemand Workflows
    - OnDemand MLExperiments
    - OnDemand EMR configurations
    - Amazon Bedrock capabilities
    - Additional analytics tools

#### Outputs:
```yaml
Outputs:
  SQLAnalyticsProfileId:
    Value: !GetAtt SQLAnalytics.Id
  AllCapabilitiesProjectProfileId:
    Value: !GetAtt AllCapabilitiesProjectProfile.Id
```

### 6. policy_grant.yaml

Configures permissions and policy grants.

#### Parameters:
```yaml
Parameters:
  DomainId:
    Type: String
  AccountId:
    Type: String
  DomainUnitId:
    Type: String
  # Blueprint and Profile IDs
```

#### Resources:
1. Lambda Function:
   ```yaml
   DataZoneGrantPolicyFunction:
     Type: AWS::Lambda::Function
     Properties:
       # Lambda function for adding policy grants
   ```

2. Policy Grants:
    - Grants for all blueprints
    - Grants for project profiles
    - Custom resource for each grant

## Prerequisites

1. AWS Account and Access:
    - Active AWS account
    - Administrator access
    - AWS Organizations enabled

2. IAM Roles:
    - Domain Execution Role with permissions:
        - DataZone domain management
        - SageMaker operations
        - S3 access
    - Service Role with permissions:
        - Cross-account access
        - Resource sharing
    - SageMaker Roles with permissions:
        - Environment management
        - Resource provisioning

3. Network Configuration:
    - VPC with appropriate subnets
    - Internet access for service communication
    - Security groups configured

4. S3 Storage:
    - S3 bucket for tooling environment
    - Appropriate bucket policies

## Deployment Instructions

1. Prepare Environment:
   ```bash
   # Create S3 bucket for templates
   aws s3 mb s3://your-template-bucket

   # Upload templates
   aws s3 cp create_domain.yaml s3://your-template-bucket/
   aws s3 cp fetch_accounts.yml s3://your-template-bucket/
   # ... upload all templates
   ```

2. Deploy Main Template:
   ```bash
   aws cloudformation create-stack \
     --stack-name datazone-setup \
     --template-url https://your-template-bucket.s3.amazonaws.com/create_domain.yaml \
     --parameters \
       ParameterKey=DomainName,ParameterValue=your-domain-name \
       # ... other parameters
     --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
   ```

3. Monitor Deployment:
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name datazone-setup
   ```