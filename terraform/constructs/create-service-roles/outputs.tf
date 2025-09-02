output "sagemaker_domain_execution_role_arn" {
  value = aws_iam_role.sagemaker_domain_execution_role.arn
  depends_on = [ 
    aws_iam_role_policy_attachment.domain-execution-attach-datazone-execution-policy,
    aws_iam_role_policy_attachment.domain-execution-attach-studio-execution-policy 
  ]
}
output "sagemaker_service_role_arn" {
  value = aws_iam_role.sagemaker_service_role.arn
  depends_on = [ 
    aws_iam_role_policy_attachment.service-attach-service-policy
  ]
}

output "sagemaker_domain_execution_role_id" {
  value = aws_iam_role.sagemaker_domain_execution_role.id
  depends_on = [ 
    aws_iam_role_policy_attachment.domain-execution-attach-datazone-execution-policy,
    aws_iam_role_policy_attachment.domain-execution-attach-studio-execution-policy 
  ]
}
output "sagemaker_service_role_id" {
  value = aws_iam_role.sagemaker_service_role.id
  depends_on = [ 
    aws_iam_role_policy_attachment.service-attach-service-policy
  ]
}