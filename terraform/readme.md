# AWS SageMaker Unified Studio Domain Setup - Terraform

## Overview

This repository contains a sample Terraform composition for setting up and configuring an AWS SageMaker Unified Studio domain with various resources and capabilities. The setup includes creating a domain, creating associated resources, enabling blueprints, and setting up project profiles.

## Deployment

Visit `/terraform/examples/` to see examples of single account and multi-account deployment.

## Modification

By default, the `/terraform/constructs/create-blueprint` module enables all blueprints by default. If only a select number of blueprints need to be enabled, then the unused blueprints have to be disabled. Each blueprint deployment depends on the previous blueprint deployment before proceeding. This is to serialize blueprint enablement one-at-a-time to avoid running into service limits by enabling all of them at once. If select blueprints are disabled, the subsequent blueprints `depends_on` statement has to be updated.

By default the `/terraform/constructs/create-blueprint` module creates an All capabilities and SQL Analytics project profile. Custom project profiles can be created by only referencing select blueprints in the definition.

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