/*
 * Create Projects for SMUS Domain
 * WARNING: This module is currently non-functional due to an open issue 
 */

resource "awscc_datazone_project" "project" {
  description             = "Testing CFN Project"
  domain_identifier       = var.domain_id
  name                    = var.name
  project_profile_id      = var.project_profile_id
  user_parameters = [
    {
      environment_configuration_name = "Lakehouse Database"
      environment_parameters = [
        {
          name  = "glueDbName"
          value = "glue_override"
        }
      ]
    },
    {
      environment_configuration_name = "Redshift Serverless"
      environment_parameters = [
        {
          name  = "redshiftDbName"
          value = "rs_db_override"
        }
      ]
    }
  ]
}

resource "awscc_datazone_project_membership" "project_membership" {
  for_each           = var.users
  domain_identifier  = var.domain_id
  project_identifier = awscc_datazone_project.project.project_id
  member = {
    user_identifier = each.key
  }
  designation = "PROJECT_OWNER"
  depends_on = [ awscc_datazone_project.project ]
}
