# BringYourOwnRoleScript for SageMaker Unified Studio

This utility script helps you configure permissions and customize role assignments for SageMaker Unified Studio environments.

## Considerations and Limitations

Please review this section carefully before proceeding to execute the script.
1. Ensure that you save your work and that you do not have any running tasks or processes (for e.g., starting or reconfiguring a JupyterLab space, creating a new compute resource) because these can get interrupted or may cause the script to fail.

## Prerequisites

1. You need the following IAM permissions to execute the script for configuring permissions and customizing role assignments. If you have an existing IAM user with these permissions, use it for running the script. If not, then create a new IAM policy with the following permissions. The example below uses `*` for `Resource`, but you can restrict it according to your security requirements. These permissions are not needed once you complete executing the script.

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DataZone",
            "Effect": "Allow",
            "Action": [
                "datazone:ListSubscriptions",
                "datazone:ListSubscriptionGrants",
                "datazone:UpdateSubscriptionTarget",
                "datazone:ListEnvironments",
                "datazone:DisassociateEnvironmentRole",
                "datazone:ListSubscriptionTargets",
                "datazone:AssociateEnvironmentRole",
                "datazone:ListSubscriptionRequests",
                "datazone:GetEnvironment",
                "datazone:CreateSubscriptionGrant",
                "datazone:DeleteSubscriptionGrant",
                "datazone:GetSubscriptionGrant",
                "datazone:ListEnvironmentBlueprints",
                "datazone:GetEnvironmentBlueprintConfiguration"
            ],
            "Resource": [
                "*"
            ]
        },
        {
            "Sid": "Glue",
            "Effect": "Allow",
            "Action": [
                "glue:GetDatabase",
                "glue:GetTable"
            ],
            "Resource": [
                "*"
            ]
        },
        {
            "Sid": "IAM",
            "Effect": "Allow",
            "Action": [
                "iam:GetRole",
                "iam:UpdateAssumeRolePolicy",
                "iam:PassRole",
                "iam:ListRoleTags",
                "iam:ListAttachedRolePolicies",
                "iam:TagRole",
                "iam:ListRoles",
                "iam:AttachRolePolicy",
                "iam:PutRolePolicy",
                "iam:ListRolePolicies",
                "iam:GetRolePolicy",
                "iam:GetPolicy",
                "iam:GetPolicyVersion",
                "iam:CreatePolicyVersion"
            ],
            "Resource": [
                "*"
            ]
        },
        {
            "Sid": "KMS",
            "Effect": "Allow",
            "Action": [
                "kms:Decrypt",
                "kms:GenerateDataKey",
                "kms:CreateGrant",
                "kms:ListGrants"
            ],
            "Resource": "*"
        },
        {
            "Sid": "Lakeformation",
            "Effect": "Allow",
            "Action": [
                "lakeformation:GrantPermissions",
                "lakeformation:ListLakeFormationOptIns",
                "lakeformation:ListPermissions",
                "lakeformation:CreateLakeFormationOptIn",
                "lakeformation:ListResources",
                "lakeformation:UpdateResource",
                "lakeformation:GetDataAccess"
            ],
            "Resource": "*"
        },
        {
            "Sid": "SageMaker",
            "Effect": "Allow",
            "Action": [
                "sagemaker:ListDomains",
                "sagemaker:ListApps",
                "sagemaker:DeleteApp",
                "sagemaker:DescribeApp",
                "sagemaker:UpdateDomain"
            ],
            "Resource": "*"
        }
    ]
}
```

2. Go to the Amazon SageMaker console and add the executor IAM user as a user in your SageMaker Unified Studio Domain. See [user management](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/adminguide/user-management.html) for more details. Then, add the executor IAM user as an owner for the SageMaker Unified Studio project in which you want to execute this script.

3. In the AWS Lake Formation console, add the executor IAM user as a Data Lake Administrator.

### Authentication Setup

For information on configuring credentials to use the executor permissions, refer to the AWS CLI documentation on role configuration: https://docs.aws.amazon.com/cli/v1/userguide/cli-configure-role.html

## Usage

Clone the [Unified-Studio-for-Amazon-Sagemaker](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker) repo using:
```
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
```
In your CLI, navigate to the directory containing `bring_your_own_role.py`

#### Use Case 1: Replace SageMaker Unified Studio Project Role with your own Role
Replace the default project role with your custom role:
```
python3 bring_your_own_role.py use-your-own-role \
    --domain-id <SageMaker-Unified-Studio-Domain-Id> \
    --project-id <SageMaker-Unified-Studio-Project-Id> \
    --bring-in-role-arn <Custom-IAM-Role-Arn> \
    --region <region-code>
```
#### Use Case 2: Enhance SageMaker Unified Studio Project Role using your own Role
```
python3 bring_your_own_role.py enhance-project-role \
    --domain-id <SageMaker-Unified-Studio-Domain-Id> \
    --project-id <SageMaker-Unified-Studio-Project-Id> \
    --bring-in-role-arn <Custom-IAM-Role-Arn> \
    --region <region-code>
```
### Important Notes
- Both commands will display a preview of proposed changes by default. To apply the changes for `use-your-own-role`, add the `--execute` `--force-update` flag. To apply the changes for `enhance-project-role`, add the `--execute` flag
- The `--region` parameter is optional and only required when necessary. If not specified, it defaults to AWS region specified in the CLI credentials config
- In `use-your-own-role` case, the role you bring in must not be used as the project User Role in another SageMaker Unified Studio Project
