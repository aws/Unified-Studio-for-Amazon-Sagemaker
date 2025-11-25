# AWS SageMaker Unified Studio Domain Setup - Terraform Multi-Account Example

## Overview

This example is a sample Terraform composition for setting up and configuring an AWS SageMaker Unified Studio domain with various resources and capabilities. The setup includes creating a domain, creating associated resources, enabling blueprints, setting up project profiles, and creating a project using a created project profile.

This example demonstrates a cross-account domain deployment without AWS Organizations by utilizing multiple providers. 

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