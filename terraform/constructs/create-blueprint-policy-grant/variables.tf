variable domain_id {
  description = "Domain for which blueprint needs to be enabled"
  type = string
}

variable domain_unit_id {
  description = "Domain unit for which blueprint needs to be enabled"
  type = string
}

variable blueprint_ids {
  description = "A list of blueprint IDs to be enabled"
  type = map(string)
}