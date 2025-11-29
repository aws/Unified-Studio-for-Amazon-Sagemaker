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

variable sso_users {
  description = "SSO users to add to the domain"
  type = list(string)
}