/*
 * Create Project profile for SMUS Domain
 * WARNING: This module is currently non-functional due to an open issue 
 */

resource "awscc_datazone_project_profile" "sql_analytics" {
  name = "SQL analytics"
  description = "Analyze your data in SageMaker Lakehouse using SQL"
  domain_identifier = var.domain_unit_id
  status = "ENABLED"
  /*
  environment_configurations = [
    {
      name = "Tooling"
      environment_blueprint_id = var.tooling_id
      description = "Configuration for the Tooling"
      deployment_mode = "ON_CREATE"
      deployment_order = 0
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "enableSpaces"
            value = "false"
            is_editable = false
          },
          {
            name = "maxEbsVolumeSize"
            is_editable = false
          },
          {
            name = "idleTimeoutInMinutes"
            is_editable = false
          },
          {
            name = "lifecycleManagement"
            is_editable = false
          },
          {
            name = "enableNetworkIsolation"
            is_editable = false
          },
          {
            name = "gitConnectionArn"
          }
        ]
      }
    },
    {
      name = "Lakehouse Database"
      environment_blueprint_id = var.data_lake_id
      description = "Creates databases in SageMaker Lakehouse for S3 tables and Athena"
      deployment_mode = "ON_CREATE"
      deployment_order = 1
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "glueDbName"
            value = "glue_db"
            is_editable = true
          }
        ]
      }
    },
    {
      name = "Redshift Serverless"
      environment_blueprint_id = var.redshift_serverless_id
      description = "Creates an Amazon Redshift Serverless workgroup"
      deployment_mode = "ON_CREATE"
      deployment_order = 1
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "redshiftDbName"
            value = "dev"
            is_editable = true
          },
          {
            name = "connectToRMSCatalog"
            value = "true"
            is_editable = false
          },
          {
            name = "redshiftMaxCapacity"
            value = "512"
            is_editable = false
          }
        ]
      }
    },
    {
      name = "OnDemand Redshift Serverless"
      environment_blueprint_id = var.redshift_serverless_id
      description = "Additional Redshift Serverless workgroup"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "redshiftDbName"
            value = "dev"
            is_editable = true
          },
          {
            name = "redshiftMaxCapacity"
            value = "512"
            is_editable = true
          },
          {
            name = "redshiftWorkgroupName"
            value = "redshift-serverless-workgroup"
            is_editable = true
          },
          {
            name = "redshiftBaseCapacity"
            value = "128"
            is_editable = true
          },
          {
            name = "connectionName"
            value = "redshift.serverless"
            is_editable = true
          },
          {
            name = "connectToRMSCatalog"
            value = "false"
            is_editable = false
          }
        ]
      }
    },
    {
      name = "OnDemand Catalog for RMS"
      environment_blueprint_id = var.lakehouse_catalog_id
      description = "Catalog for Redshift Managed Storage"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "catalogName"
            is_editable = true
          },
          {
            name = "catalogDescription"
            value = "RMS catalog"
            is_editable = true
          }
        ]
      }
    },
    {
      name = "OnDemand QuickSight"
      environment_blueprint_id = var.quick_sight_id
      description = "Amazon QuickSight for data visualization"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
    }
  ]
  */
}

resource "awscc_datazone_project_profile" "all_capabilities_project_profile" {
  name = "All capabilities"
  description = "Analyze data and build machine learning and generative AI models and applications powered by Amazon Bedrock, Amazon EMR, AWS Glue, Amazon Athena, Amazon SageMaker AI and Amazon SageMaker Lakehouse"
  status = "ENABLED"
  domain_identifier = var.domain_unit_id
  /*
  environment_configurations = [
    {
      name = "Tooling"
      environment_blueprint_id = var.tooling_id
      description = "Configuration for the Tooling"
      deployment_order = 0
      deployment_mode = "ON_CREATE"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "enableSpaces"
            value = "true"
            is_editable = false
          },
          {
            name = "maxEbsVolumeSize"
            is_editable = false
          },
          {
            name = "idleTimeoutInMinutes"
            is_editable = false
          },
          {
            name = "lifecycleManagement"
            is_editable = false
          },
          {
            name = "enableNetworkIsolation"
            is_editable = false
          },
          {
            name = "enableAmazonBedrockPermissions"
            value = "true"
            is_editable = false
          },
          {
            name = "gitConnectionArn"
          }
        ]
      }
    },
    {
      name = "Lakehouse Database"
      environment_blueprint_id = var.data_lake_id
      description = "Creates databases in Amazon SageMaker Lakehouse for storing tables in S3 and Amazon Athena resources for your SQL workloads"
      deployment_order = 1
      deployment_mode = "ON_CREATE"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "glueDbName"
            value = "glue_db"
            is_editable = true
          }
        ]
      }
    },
    {
      name = "RedshiftServerless"
      environment_blueprint_id = var.redshift_serverless_id
      description = "Creates an Amazon Redshift Serverless workgroup for your SQL workloads"
      deployment_order = 1
      deployment_mode = "ON_CREATE"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "redshiftDbName"
            value = "dev"
            is_editable = true
          },
          {
            name = "connectToRMSCatalog"
            value = "true"
            is_editable = false
          },
          {
            name = "redshiftMaxCapacity"
            value = "512"
            is_editable = false
          }
        ]
      }
    },
    {
      name = "OnDemand Workflows"
      environment_blueprint_id = var.workflows_id
      description = "Enables you to create Airflow workflows to be executed on MWAA environments"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "environmentClass"
            value = "mw1.micro"
            is_editable = false
          }
        ]
      }
    },
    {
      name = "OnDemand MLExperiments"
      environment_blueprint_id = var.ml_experiments_id
      description = "Enables you to create Amazon Sagemaker mlflow in the project"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "mlflowTrackingServerSize"
            value = "Small"
            is_editable = true
          },
          {
            name = "mlflowTrackingServerName"
            value = "tracking-server"
            is_editable = true
          }
        ]
      }
    },
    {
      name = "OnDemand EMR on EC2 Memory-Optimized"
      environment_blueprint_id = var.emr_on_ec2_id
      description = "Enables you to create an additional memory optimized Amazon EMR on Amazon EC2"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "emrRelease"
            value = "emr-7.5.0"
            is_editable = true
          },
          {
            name = "connectionDescription"
            value = "Spark connection for EMR EC2 cluster"
            is_editable = true
          },
          {
            name = "clusterName"
            value = "emr-ec2-cluster"
            is_editable = true
          },
          {
            name = "primaryInstanceType"
            value = "r6g.xlarge"
            is_editable = true
          },
          {
            name = "coreInstanceType"
            value = "r6g.xlarge"
            is_editable = true
          },
          {
            name = "taskInstanceType"
            value = "r6g.xlarge"
            is_editable = true
          }
        ]
      }
    },
    {
      name = "OnDemand EMR on EC2 General-Purpose"
      environment_blueprint_id = var.emr_on_ec2_id
      description = "Enables you to create an additional general purpose Amazon EMR on Amazon EC2"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "emrRelease"
            value = "emr-7.5.0"
            is_editable = true
          },
          {
            name = "connectionDescription"
            value = "Spark connection for EMR EC2 cluster"
            is_editable = true
          },
          {
            name = "clusterName"
            value = "emr-ec2-cluster"
            is_editable = true
          },
          {
            name = "primaryInstanceType"
            value = "m6g.xlarge"
            is_editable = true
          },
          {
            name = "coreInstanceType"
            value = "m6g.xlarge"
            is_editable = true
          },
          {
            name = "taskInstanceType"
            value = "m6g.xlarge"
            is_editable = true
          }
        ]
      }
    },
    {
      name = "OnDemand RedshiftServerless"
      environment_blueprint_id = var.redshift_serverless_id
      description = "Enables you to create an additional Amazon Redshift Serverless workgroup for your SQL workloads"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "redshiftDbName"
            value = "dev"
            is_editable = true
          },
          {
            name = "redshiftMaxCapacity"
            value = "512"
            is_editable = true
          },
          {
            name = "redshiftWorkgroupName"
            value = "redshift-serverless-workgroup"
            is_editable = true
          },
          {
            name = "redshiftBaseCapacity"
            value = "128"
            is_editable = true
          },
          {
            name = "connectionName"
            value = "redshift.serverless"
            is_editable = true
          },
          {
            name = "connectToRMSCatalog"
            value = "false"
            is_editable = false
          }
        ]
      }
    },
    {
      name = "OnDemand Catalog for Redshift Managed Storage"
      environment_blueprint_id = var.lakehouse_catalog_id
      description = "Enables you to create additional catalogs in Amazon SageMaker Lakehouse for storing data in Redshift Managed Storage"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "catalogName"
            is_editable = true
          },
          {
            name = "catalogDescription"
            value = "RMS catalog"
            is_editable = true
          }
        ]
      }
    },
    {
      name = "OnDemand EMRServerless"
      environment_blueprint_id = var.emr_serverless_id
      description = "Enables you to create an additional Amazon EMR Serverless application for running Spark workloads"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
      configuration_parameters = {
        parameter_overrides = [
          {
            name = "connectionDescription"
            is_editable = true
          },
          {
            name = "connectionName"
            is_editable = true
          },
          {
            name = "releaseLabel"
            value = "emr-7.5.0"
            is_editable = true
          }
        ]
      }
    },
    {
      name = "Amazon Bedrock Chat Agent"
      environment_blueprint_id = var.amazon_bedrock_chat_agent_id
      description = "A configurable generative AI app with a conversational interface"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
    },
    {
      name = "Amazon Bedrock Knowledge Base"
      environment_blueprint_id = var.amazon_bedrock_knowledge_base_id
      description = "A reusable component for providing your own data to apps"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
    },
    {
      name = "Amazon Bedrock Guardrail"
      environment_blueprint_id = var.amazon_bedrock_guardrail_id
      description = "A reusable component for implementing safeguards on model outputs"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
    },
    {
      name = "Amazon Bedrock Function"
      environment_blueprint_id = var.amazon_bedrock_function_id
      description = "A reusable component for including dynamic information in model outputs"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
    },
    {
      name = "Amazon Bedrock Flow"
      environment_blueprint_id = var.amazon_bedrock_flow_id
      description = "A configurable generative AI workflow"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
    },
    {
      name = "Amazon Bedrock Prompt"
      environment_blueprint_id = var.amazon_bedrock_prompt_id
      description = "A reusable set of inputs that guide model outputs"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
    },
    {
      name = "Amazon Bedrock Evaluation"
      environment_blueprint_id = var.amazon_bedrock_evaluation_id
      description = "Enables evaluation features to compare Bedrock models"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
    },
    {
      name = "QuickSight"
      environment_blueprint_id = var.quick_sight_id
      description = "Amazon QuickSight for data visualization and business intelligence"
      deployment_mode = "ON_DEMAND"
      aws_account = {
        aws_account_id = var.account_id
      }
      aws_region = {
        region_name = var.region
      }
    }
  ]
  */
}
