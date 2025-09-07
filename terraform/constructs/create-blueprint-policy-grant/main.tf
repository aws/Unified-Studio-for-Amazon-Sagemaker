/*
 * Enables all blueprints for SMUS domain
 */
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "awscc_datazone_policy_grant" "blueprint_policy_grants" {
  for_each = var.blueprint_ids
  domain_identifier = var.domain_id
  entity_type = "ENVIRONMENT_BLUEPRINT_CONFIGURATION"
  entity_identifier = "${data.aws_caller_identity.current.account_id}:${each.value}"
  policy_type  = "CREATE_ENVIRONMENT_FROM_BLUEPRINT"
  detail = {
     create_environment_from_blueprint = jsonencode({})
   }
  principal = {
    project = {
      project_designation = "CONTRIBUTOR"
      project_grant_filter = {
        domain_unit_filter = {
          domain_unit  = var.domain_unit_id
          include_child_domain_units  = true
         }
       }
     }
   }
}