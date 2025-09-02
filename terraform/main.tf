/*
 * Create a SMUS domain and configure resources
 */

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

data "aws_region" "alternate" {
  provider = aws.alternate
}
data "aws_caller_identity" "alternate" {
  provider = aws.alternate
}

// deploy in primary account
module "domain_service_roles" {
  source = "./constructs/create-service-roles"

}

// avoid race condition by forcing domain to be created in series
resource "time_sleep" "wait_after_role_creation" {
  depends_on      = [module.domain_service_roles]
  create_duration = "10s"
}

// create domain in primary account
resource "awscc_datazone_domain" "domain" {
  provider              = awscc
  name                  = var.domain_name
  description           = "Test Domain"
  domain_execution_role = module.domain_service_roles.sagemaker_domain_execution_role_arn
  service_role          = module.domain_service_roles.sagemaker_service_role_arn
  domain_version        = "V2"
  single_sign_on = {
    type            = "IAM_IDC"
    user_assignment = "AUTOMATIC"
  }
  depends_on = [
    time_sleep.wait_after_role_creation
  ]
}

// add SSO users to domain
resource "aws_datazone_user_profile" "sso_users" {
  for_each = toset(var.sso_users)
  domain_identifier = awscc_datazone_domain.domain.domain_id
  user_identifier = each.key
  user_type = "SSO_USER"
}

// create RAM share from primary account
resource "awscc_ram_resource_share" "domain_share" {
  provider                  = awscc
  name                      = "DataZone-${awscc_datazone_domain.domain.name}-${awscc_datazone_domain.domain.domain_id}"
  resource_arns             = [awscc_datazone_domain.domain.arn]
  allow_external_principals = true
  permission_arns = [
    "arn:aws:ram::aws:permission/AWSRAMPermissionsAmazonDatazoneDomainExtendedServiceAccess"
  ]
  principals = [
    data.aws_caller_identity.alternate.account_id
  ]
}

// accept RAM share from associated account
// this step can be skipped when using AWS Organizations, as resources will be automatically accepted
resource "aws_ram_resource_share_accepter" "receiver_accept" {
  provider  = aws.alternate
  share_arn = awscc_ram_resource_share.domain_share.arn
}

// create storage bucket in associated account
resource "aws_s3_bucket" "dzs3_bucket" {
  provider = aws.alternate
  bucket   = "amazon-sagemaker-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.region}-${replace(awscc_datazone_domain.domain.domain_id, "dzd_", "")}"
}

// create roles in associated account
// when doing cross-account deployment, the account id will be set to the source account to allow for the domain to call in
module "blueprint_roles" {
  source     = "./constructs/create-blueprint-roles"
  domain_arn = awscc_datazone_domain.domain.arn
  domain_id  = awscc_datazone_domain.domain.domain_id
  account_id = data.aws_caller_identity.current.account_id
  // deploy in associated account
  providers = {
    "aws"   = aws.alternate
    "awscc" = awscc.alternate
  }
  depends_on = [
    aws_ram_resource_share_accepter.receiver_accept
  ]
}

// enable blueprints for the domain
// If a cross-account association is used, these blueprints will be created in the associated account by specifying the provider
module "blueprints" {
  source                               = "./constructs/create-blueprint"
  domain_id                            = awscc_datazone_domain.domain.domain_id
  amazon_sage_maker_manage_access_role = module.blueprint_roles.sagemaker_manage_access_role_arn
  amazon_sage_maker_provisioning_role  = module.blueprint_roles.sagemaker_provisioning_role_arn
  dzs3_bucket                          = "s3://${aws_s3_bucket.dzs3_bucket.id}/"
  sage_maker_subnets                   = join(",", var.sagemaker_subnets)
  amazon_sage_maker_vpc_id             = var.sagemaker_vpc_id
  // deploy in associated account
  providers = {
    "aws"   = aws.alternate
    "awscc" = awscc.alternate
  }
  // need to accept and associate domain before enabling blueprints
  depends_on = [
    aws_ram_resource_share_accepter.receiver_accept
  ]
}

module "blueprint_policy_grants" {
  source         = "./constructs/create-blueprint-policy-grant"
  domain_id      = awscc_datazone_domain.domain.domain_id
  domain_unit_id = awscc_datazone_domain.domain.root_domain_unit_id

  blueprint_ids = tomap({
    lakehouse_catalog_id             = module.blueprints.lakehouse_catalog_id,
    amazon_bedrock_guardrail_id      = module.blueprints.amazon_bedrock_guardrail_id,
    ml_experiments_id                = module.blueprints.ml_experiments_id,
    tooling_id                       = module.blueprints.tooling_id,
    redshift_serverless_id           = module.blueprints.redshift_serverless_id,
    emr_serverless_id                = module.blueprints.emr_serverless_id,
    workflows_id                     = module.blueprints.workflows_id,
    amazon_bedrock_prompt_id         = module.blueprints.amazon_bedrock_prompt_id,
    data_lake_id                     = module.blueprints.data_lake_id,
    amazon_bedrock_evaluation_id     = module.blueprints.amazon_bedrock_evaluation_id,
    amazon_bedrock_knowledge_base_id = module.blueprints.amazon_bedrock_knowledge_base_id,
    partner_apps_id                  = module.blueprints.partner_apps_id,
    amazon_bedrock_chat_agent_id     = module.blueprints.amazon_bedrock_chat_agent_id,
    amazon_bedrock_function_id       = module.blueprints.amazon_bedrock_function_id,
    amazon_bedrock_flow_id           = module.blueprints.amazon_bedrock_flow_id,
    emr_on_ec2_id                    = module.blueprints.emr_on_ec2_id,
    quick_sight_id                   = module.blueprints.quick_sight_id,
  })
  // deploy in associated account
  providers = {
    "aws"   = aws.alternate
    "awscc" = awscc.alternate
  }
}

// project profiles are created in primary account and reference the account where blueprints are located
// in a multi-account configuration, the project profiles are created in the primary account and reference blueprints created in the associated account
/*
module "project_profiles" {
  source = "./constructs/create_project_profiles"
  // domain to enable project profiles
  domain_id = awscc_datazone_domain.domain.domain_id
  domain_unit_id = awscc_datazone_domain.domain.root_domain_unit_id
  // account where blueprints are deployed
  account_id = data.aws_caller_identity.alternate.account_id
  region = data.aws_region.alternate.region
  // blueprint identifiers
  lakehouse_catalog_id = module.blueprints.lakehouse_catalog_id
  amazon_bedrock_guardrail_id = module.blueprints.amazon_bedrock_guardrail_id
  ml_experiments_id = module.blueprints.ml_experiments_id
  tooling_id = module.blueprints.tooling_id
  redshift_serverless_id = module.blueprints.redshift_serverless_id
  emr_serverless_id = module.blueprints.emr_serverless_id
  workflows_id = module.blueprints.workflows_id
  amazon_bedrock_prompt_id = module.blueprints.amazon_bedrock_prompt_id
  data_lake_id = module.blueprints.data_lake_id
  amazon_bedrock_evaluation_id = module.blueprints.amazon_bedrock_evaluation_id
  amazon_bedrock_knowledge_base_id = module.blueprints.amazon_bedrock_knowledge_base_id
  partner_apps_id = module.blueprints.partner_apps_id
  amazon_bedrock_chat_agent_id = module.blueprints.amazon_bedrock_chat_agent_id
  amazon_bedrock_function_id = module.blueprints.amazon_bedrock_function_id
  amazon_bedrock_flow_id = module.blueprints.amazon_bedrock_flow_id
  emr_on_ec2_id = module.blueprints.emr_on_ec2_id
  quick_sight_id = module.blueprints.quick_sight_id
}
*/

// temporary workaround to use cloudformation
resource "aws_cloudformation_stack" "project_profiles" {
  name = "ProjectProfiles${var.domain_name}"
  parameters = {
    DomainId                     = awscc_datazone_domain.domain.domain_id
    DomainUnitId                 = awscc_datazone_domain.domain.root_domain_unit_id
    AccountId                    = data.aws_caller_identity.alternate.account_id
    Region                       = data.aws_region.alternate.region
    LakehouseCatalogId           = module.blueprints.lakehouse_catalog_id
    AmazonBedrockGuardrailId     = module.blueprints.amazon_bedrock_guardrail_id
    MLExperimentsId              = module.blueprints.ml_experiments_id
    ToolingId                    = module.blueprints.tooling_id
    RedshiftServerlessId         = module.blueprints.redshift_serverless_id
    EmrServerlessId              = module.blueprints.emr_serverless_id
    WorkflowsId                  = module.blueprints.workflows_id
    AmazonBedrockPromptId        = module.blueprints.amazon_bedrock_prompt_id
    DataLakeId                   = module.blueprints.data_lake_id
    AmazonBedrockEvaluationId    = module.blueprints.amazon_bedrock_evaluation_id
    AmazonBedrockKnowledgeBaseId = module.blueprints.amazon_bedrock_knowledge_base_id
    PartnerAppsId                = module.blueprints.partner_apps_id
    AmazonBedrockChatAgentId     = module.blueprints.amazon_bedrock_chat_agent_id
    AmazonBedrockFunctionId      = module.blueprints.amazon_bedrock_function_id
    AmazonBedrockFlowId          = module.blueprints.amazon_bedrock_flow_id
    EmrOnEc2Id                   = module.blueprints.emr_on_ec2_id
    QuickSightId                 = module.blueprints.quick_sight_id
  }
  template_body = file("../cloudformation/domain/create_project_profiles.yaml")
}

module "project_profile_policy_grant" {
  source         = "./constructs/create-project-profile-policy-grant"
  domain_id      = awscc_datazone_domain.domain.domain_id
  domain_unit_id = awscc_datazone_domain.domain.root_domain_unit_id
  project_profile_ids = [
    aws_cloudformation_stack.project_profiles.outputs["SQLAnalyticsProfileId"],
    aws_cloudformation_stack.project_profiles.outputs["AllCapabilitiesProjectProfileId"]
  ]
}


/* Project creation is currently disabled pending API updates
module "sample_project" {
  source = "./constructs/create_project"
  domain_id = awscc_datazone_domain.domain.domain_id
  project_profile_id = aws_cloudformation_stack.project_profiles.outputs["AllCapabilitiesProjectProfileId"]
  name = "DeployedProjectV2"
  users = toset([for user in aws_datazone_user_profile.sso_users: user.user_identifier])
}
*/