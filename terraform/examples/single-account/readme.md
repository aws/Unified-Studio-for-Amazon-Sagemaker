# AWS SageMaker Unified Studio Domain Setup - Terraform Single-Account Example

## Overview

This example is a sample Terraform composition for setting up and configuring an AWS SageMaker Unified Studio domain with various resources and capabilities within a single account. The setup includes creating a domain, creating associated resources, enabling blueprints, setting up project profiles, and creating a project using a created project profile.

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