# AWS SageMaker Unified Studio Domain Setup - Terraform

## Overview

This repository contains a sample Terraform composition for setting up and configuring an AWS SageMaker Unified Studio domain with various resources and capabilities. The setup includes creating a domain, creating associated resources, enabling blueprints, and setting up project profiles.

By default, the main example shown demonstrates a cross-account domain deployment without AWS Organizations by utilizing multiple providers. 

## Usage

The main stack requires three variables to be specified before deployment. 

#### Variables:

```tf
variable domain_name {
  description = "Name of the DataZone domain"
  type = string
}

variable sagemaker_subnets {
  description = "A list of subnets within the sagemaker VPC"
  type = list(string)
}

variable sagemaker_vpc_id {
  description = "The VPC ID of the sagemaker VPC"
  type = string
}
```

These variables can be specified in a `.tfvars` file to be referenced during deployment

example.tfvars
```
domain_name = "Example"
sagemaker_subnets = ["subnet-xxx","subnet-xxx","subnet-xxx","subnet-xxx"]
sagemaker_vpc_id = "vpc-xxx"
```

### Configuring Providers

This sample utilizes both [AWS](https://registry.terraform.io/providers/hashicorp/aws/latest) and [AWS Cloud Control](https://registry.terraform.io/providers/hashicorp/awscc/latest) providers to deploy resources. 

By default, this example utilizes four providers located in `providers.tf`, two for the "primary" account where the Sagemaker Unified Studio Domain is deployed and two for an "alternate" associated account which associates with the domain and deploys blueprints and resources. 

These are configured to read from profiles named `primary` and `alternate`. To configure these profiles, run the following commands to set credentials for each profile using the AWS CLI tool:
- `aws configure --profile primary`
- `aws configure --profile alternate`  
```
// primary account providers
provider "aws" {
  profile = "primary"
}
provider "awscc" {
  profile = "primary"
}
// alternate (associated domain) account providers
provider "aws" {
  alias   = "alternate"
  profile = "alternate"
}
provider "awscc" {
  alias   = "alternate"
  profile = "alternate"
}
```

Alternatively, modify the `providers.tf` file to set custom credentials for the provider according to the documentation.
- [AWS](https://registry.terraform.io/providers/hashicorp/aws/latest/docs#authentication-and-configuration)
- [AWS Cloud Control](https://registry.terraform.io/providers/hashicorp/awscc/latest/docs#authentication)
- [Provider Configuration](https://developer.hashicorp.com/terraform/language/providers/configuration)

#### Disabling Cross-Account Deployment

The main stack is configured as an example of a cross-account deployment that is not within an AWS Organization and utilizes two profiles. To disable this, remove instances of "alternate" aws and awscc provider alias in the `main.tf` stack and the stack will deploy entirely in the primary account provider.

```
// change
data.aws_caller_identity.alternate.account_id
// to
data.aws_caller_identity.current.account_id

// change
data.aws_region.alternate.name
// to
data.aws_region.current.name

// remove
data "aws_region" "alternate" {
    provider = aws.alternate
}
data "aws_caller_identity" "alternate" {
    provider = aws.alternate
}

// remove
providers = {
    "aws" = aws.alternate
    "awscc" = awscc.alternate
}

// remove
provider = aws.alternate

// remove
provider "aws" {
  alias   = "alternate"
  profile = "alternate"
}
provider "awscc" {
  alias   = "alternate"
  profile = "alternate"
}

```

### Deployment

Initialize terraform within the `/terraform` project:

```bash
terraform init
```

Plan the project using a `.tfvars` file:

```bash
terraform plan -var-file=example.tfvars
```

Apply the plan to deploy the project:

```bash
terraform apply -var-file=example.tfvars
```

## Notable Differences to the CloudFormation sample

### IAM Role Creation

In the CloudFormation template sample, pre-existing IAM roles for domain execution, service, manage access, and provisioning needed to be provided before the stack could be created. In the Terraform sample, roles are created automatically within the template. These roles align roughly with the roles created using the AWS Console, however, some roles in the console are created once per account while this template creates new roles for every deployment to avoid resource contention.

### S3 Bucket Creation

An Amazon S3 bucket is created by default in this Terraform example for the blueprints to use, so no existing bucket has to be specified.

### AWS Organizations

In the CloudFormation template sample, a custom resource was used to retrieve the accounts within an AWS Organization. A Terraform-native replacement for this is the [`aws_organizations_organization`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/organizations_organization) data source can be used to directly list accounts. 

The [`for_each` Terraform meta-argument](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each) can then be used to enumerate the account IDs and create RAM shares for the domain.

### Removal of Custom Resources

In the CloudFormation template sample, a lambda custom resource was used to create DataZone policy grant to enable access to the blueprints and project profiles. In the Terraform sample, custom resources were removed - therefore blueprints and project profiles require a manual policy grant before creating a project.

## Pending Items

### Project Creation

Module samples to create a Datazone project are currently on hold due to an [open issue for project profile creation](https://github.com/hashicorp/terraform-provider-awscc/issues/2380) through the AWS Cloud Control provider. We will monitor the issue and update the sample once this becomes available.