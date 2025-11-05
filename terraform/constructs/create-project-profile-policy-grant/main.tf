/*
 * Create policy grants for all project profiles in a domain or associated domain
 */
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "awscc_datazone_policy_grant" "project_profile_policy_grant" {
  domain_identifier = var.domain_id
  entity_type = "DOMAIN_UNIT"
  entity_identifier = var.domain_unit_id
  policy_type  = "CREATE_PROJECT_FROM_PROJECT_PROFILE"
  detail = {
     create_project_from_project_profile = {
       include_child_domain_units=true
       project_profiles = var.project_profile_ids
     }
   }
  principal = {
    user = {
      all_users_grant_filter = jsonencode({})
    }
   }
}