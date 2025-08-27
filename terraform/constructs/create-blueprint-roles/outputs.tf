output "sagemaker_manage_access_role_arn" {
  value = aws_iam_role.sagemaker_manage_access.arn
}
output "sagemaker_provisioning_role_arn" {
  value = aws_iam_role.sagemaker_provisioning.arn
}