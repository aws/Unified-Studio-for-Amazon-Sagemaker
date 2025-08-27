/*
 * Create the AmazonSageMakerDomainExecution and AmazonSageMakerDomainService IAM Roles required for the SageMaker Unified Studio Domain
 * Learn more about the AmazonSageMakerDomainExecution role here: https://docs.aws.amazon.com/sagemaker-unified-studio/latest/adminguide/AmazonSageMakerDomainExecution.html
 * Learn more about AmazonSageMakerDomainService role here: https://docs.aws.amazon.com/sagemaker-unified-studio/latest/adminguide/AmazonSageMakerDomainService.html
 */

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

resource "random_string" "role_name_suffix" {
  length           = 8
  special          = false
}

resource "aws_iam_role" "sagemaker_domain_execution_role" {
  name = "AmazonSageMakerDomainExecution${random_string.role_name_suffix.result}"
  assume_role_policy = jsonencode({
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "datazone.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:SetContext",
          "sts:TagSession"
        ]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          "ForAllValues:StringLike" = {
            "aws:TagKeys" = "datazone*"
          }
        }
      },

      // needed to allow initial domain creation or else it fails
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "datazone.amazonaws.com"
        }
      }
    ]
    Version = "2012-10-17"
  })
  path = "/service-role/"
}

resource "aws_iam_role_policy_attachment" "domain-execution-attach-studio-execution-policy" {
  role       = aws_iam_role.sagemaker_domain_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/SageMakerStudioDomainExecutionRolePolicy"
}
resource "aws_iam_role_policy_attachment" "domain-execution-attach-datazone-execution-policy" {
  role       = aws_iam_role.sagemaker_domain_execution_role.name
  policy_arn =  "arn:aws:iam::aws:policy/service-role/AmazonDataZoneDomainExecutionRolePolicy"
}

resource "aws_iam_role" "sagemaker_service_role" {
  name = "AmazonSageMakerDomainService${random_string.role_name_suffix.result}"
  assume_role_policy = jsonencode({
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "datazone.amazonaws.com"
        }
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
    Version = "2012-10-17"
  })
  path = "/service-role/"
}

resource "aws_iam_role_policy_attachment" "service-attach-service-policy" {
  role       = aws_iam_role.sagemaker_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/SageMakerStudioDomainServiceRolePolicy"
}