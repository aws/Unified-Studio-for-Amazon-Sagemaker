variable "domain_id" {
  type = string
  description = "The ID of the DataZone domain"
}

variable "domain_arn" {
  type = string
  description = "The ARN of the DataZone domain"
}

variable "account_id" {
  type = string
  description = "The account ID to attach to the trust policy. When creating this in a shared domain, the account id will the the id of the origin account."
}