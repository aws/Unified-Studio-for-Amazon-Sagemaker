# This is where to configure providers
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 1.0"
    }
  }
}

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