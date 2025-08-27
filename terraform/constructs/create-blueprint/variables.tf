variable domain_id {
  description = "Domain for which blueprint needs to be enabled"
  type = string
}

variable amazon_sage_maker_manage_access_role {
  description = "IAM role to manage access to SageMaker environments"
  type = string
}

variable amazon_sage_maker_provisioning_role {
  description = "IAM role to provision SageMaker environments"
  type = string
}

variable dzs3_bucket {
  description = "S3 location for Tooling environment"
  type = string
}

variable sage_maker_subnets {
  description = "Subnet IDs for SageMaker"
  type = string
}

variable amazon_sage_maker_vpc_id {
  description = "VPC ID for SageMaker"
  type = string
}