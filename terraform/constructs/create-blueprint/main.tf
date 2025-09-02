/*
 * Enables all blueprints for SMUS domain
 */

data "aws_region" "current" {}

data "aws_datazone_environment_blueprint" "amazon_bedrock_chat_agent" {
  domain_id = var.domain_id
  name      = "AmazonBedrockChatAgent"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "amazon_bedrock_chat_agent" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.amazon_bedrock_chat_agent.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
}

data "aws_datazone_environment_blueprint" "amazon_bedrock_evaluation" {
  domain_id = var.domain_id
  name      = "AmazonBedrockEvaluation"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "amazon_bedrock_evaluation" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.amazon_bedrock_evaluation.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.amazon_bedrock_chat_agent
  ]
}

data "aws_datazone_environment_blueprint" "amazon_bedrock_flow" {
  domain_id = var.domain_id
  name      = "AmazonBedrockFlow"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "amazon_bedrock_flow" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.amazon_bedrock_flow.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.amazon_bedrock_evaluation
  ]
}

data "aws_datazone_environment_blueprint" "amazon_bedrock_function" {
  domain_id = var.domain_id
  name      = "AmazonBedrockFunction"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "amazon_bedrock_function" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.amazon_bedrock_function.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.amazon_bedrock_flow
  ]
}

data "aws_datazone_environment_blueprint" "amazon_bedrock_guardrail" {
  domain_id = var.domain_id
  name      = "AmazonBedrockGuardrail"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "amazon_bedrock_guardrail" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.amazon_bedrock_guardrail.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.amazon_bedrock_function
  ]
}

data "aws_datazone_environment_blueprint" "amazon_bedrock_knowledge_base" {
  domain_id = var.domain_id
  name      = "AmazonBedrockKnowledgeBase"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "amazon_bedrock_knowledge_base" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.amazon_bedrock_knowledge_base.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.amazon_bedrock_guardrail
  ]
}

data "aws_datazone_environment_blueprint" "amazon_bedrock_prompt" {
  domain_id = var.domain_id
  name      = "AmazonBedrockPrompt"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "amazon_bedrock_prompt" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.amazon_bedrock_prompt.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.amazon_bedrock_knowledge_base
  ]
}

data "aws_datazone_environment_blueprint" "data_lake" {
  domain_id = var.domain_id
  name      = "DataLake"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "data_lake" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.data_lake.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.amazon_bedrock_prompt
  ]
}

data "aws_datazone_environment_blueprint" "emr_on_ec2" {
  domain_id = var.domain_id
  name      = "EmrOnEc2"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "emr_on_ec2" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.emr_on_ec2.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.data_lake
  ]
}

data "aws_datazone_environment_blueprint" "emr_serverless" {
  domain_id = var.domain_id
  name      = "EmrServerless"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "emr_serverless" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.emr_serverless.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.emr_on_ec2
  ]
}

data "aws_datazone_environment_blueprint" "lakehouse_catalog" {
  domain_id = var.domain_id
  name      = "LakehouseCatalog"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "lakehouse_catalog" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.lakehouse_catalog.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
    // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.emr_serverless
  ]
}

data "aws_datazone_environment_blueprint" "ml_experiments" {
  domain_id = var.domain_id
  name      = "MLExperiments"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "ml_experiments" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.ml_experiments.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.lakehouse_catalog
  ]
}

data "aws_datazone_environment_blueprint" "partner_apps" {
  domain_id = var.domain_id
  name      = "PartnerApps"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "partner_apps" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.partner_apps.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.ml_experiments
  ]
}

data "aws_datazone_environment_blueprint" "quick_sight" {
  domain_id = var.domain_id
  name      = "QuickSight"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "quick_sight" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.quick_sight.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.partner_apps
  ]
}

data "aws_datazone_environment_blueprint" "redshift_serverless" {
  domain_id = var.domain_id
  name      = "RedshiftServerless"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "redshift_serverless" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.redshift_serverless.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.quick_sight
  ]
}

data "aws_datazone_environment_blueprint" "tooling" {
  domain_id = var.domain_id
  name      = "Tooling"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "tooling" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.tooling.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.redshift_serverless
  ]
}

data "aws_datazone_environment_blueprint" "workflows" {
  domain_id = var.domain_id
  name      = "Workflows"
  managed   = true
}
resource "aws_datazone_environment_blueprint_configuration" "workflows" {
  domain_id = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.workflows.id
  manage_access_role_arn = var.amazon_sage_maker_manage_access_role
  provisioning_role_arn = var.amazon_sage_maker_provisioning_role
  regional_parameters = {
      "${data.aws_region.current.region}" = {
        S3Location = var.dzs3_bucket
        Subnets = var.sage_maker_subnets
        VpcId = var.amazon_sage_maker_vpc_id
      }
  }
  
  enabled_regions = [
    data.aws_region.current.region
  ]
  // enable sequentially to avoid service limit
  depends_on = [
    aws_datazone_environment_blueprint_configuration.tooling
  ]
}