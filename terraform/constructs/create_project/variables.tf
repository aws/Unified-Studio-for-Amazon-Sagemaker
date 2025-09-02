variable domain_id {
  description = "Domain for which blueprint needs to be enabled"
  type = string
}
variable project_profile_id {
  description = "Project Profile id for which we need to create project"
  type = string
}

variable name {
  description = "Name of the project"
  type = string
}

variable users {
  description = "Users for the project"
  type = set(string)
}

