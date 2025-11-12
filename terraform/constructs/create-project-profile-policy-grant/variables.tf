variable domain_id {
  description = "Domain for which blueprint needs to be enabled"
  type = string
}

variable domain_unit_id {
  description = "Domain unit for which blueprint needs to be enabled"
  type = string
}

variable project_profile_ids {
  description = "A list of project profile IDs to be enabled"
  type = list(string)
}