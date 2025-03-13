# Glue Database Catalog Assets Import to SageMaker Unified Studio Project

This Python script allows you to import specific Glue tables or all tables within a glue database into a specified project in SageMaker Unified Studio.

## Script Details

The script (`bring_your_own_gdc_assets.py`) checks if the specified Glue database and tables are managed by Lake Formation. If they are not, it enables Lake Formation opt-in. When only a database is provided, the script performs this check and enables opt-in for all tables within that database. It verifies whether each S3 location (or its sub paths), associated with the tables being imported, is registered in Lake Formation. If they are not registered, the script registers the S3 location in Lake Formation with Hybrid Mode. Additionally, it grants SUPER (ALL) permissions on the tables, along with SUPER WITH GRANT Option permissions, to the specified project IAM role.

## Prerequisites
Ensure you have the appropriate permissions configured through an IAM role or user before using this script.

### Required Permissions

1. Create a new IAM policy with the following permissions.
```
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Effect": "Allow",
			"Action": [
			    "lakeformation:ListPermissions",
			    "lakeformation:ListLakeFormationOptIns",
			    "lakeformation:CreateLakeFormationOptIn",
				"lakeformation:ListResources",
				"lakeformation:RegisterResource",
				"lakeformation:GrantPermissions",
				"glue:GetDatabase",
				"glue:GetTable",
				"glue:GetTables",
				"iam:GetRole",
				"iam:PassRole",
				"iam:GetRolePolicy",
				"iam:PutRolePolicy"
			],
			"Resource": "*"
		}
	]
}
```
**Note**: While this example uses "*" for `Resource`, consider restricting it according to your security requirements.

### Configuration Steps

1. Create a IAM policy as shown above
2. Attach the policy to your executor resource (IAM user or role)
3. Add the executor(IAM user or role) as LakeFormation Data Lake Administrator in the region where you will execute the script.
4. To configure CLI credentials to use the executor permissions, refer to the [AWS CLI documentation on role configuration](https://docs.aws.amazon.com/cli/v1/userguide/cli-configure-role.html).

### Current limitations
1. DZ Subscription will not work on Glue tables that have IAM access control (i.e., tables with Lake Formation permissions assigned to the IAMAllowedPrincipals group)

## Usage

### Location
Navigate to the directory containing `bring_your_own_gdc_assets.py` in the terminal before executing commands.

### Available Commands

#### Use Case 1: Import an existing Glue table into SageMaker Unified Studio Project
```
python3 bring_your_own_gdc_assets.py \
    --project-role-arn <Project role ARN> \
    --table-name <Glue Table name to import>
    --database-name <Glue Database name of the table which you want to bring in> \
    --iam-role-arn-lf-resource-register <IAM role arn with access to the S3 location of the glue table> \
    --region <region-code> 
```

#### Use Case 2: Import all existing Glue tables from a given Glue database into SageMaker Unified Studio Project
```
python3 bring_your_own_gdc_assets.py \
    --project-role-arn <Project role ARN> \
    --database-name <Glue Database name to import> \
    --iam-role-arn-lf-resource-register <IAM role arn with access to the S3 location of all tables in the glue database> \
    --region <region-code> 
```

### Important Notes
- The `--iam-role-arn-lf-resource-register` parameter is optional. It's only used if the S3 location associated with the Glue table is not registered in LakeFormation. If not provided and the S3 location is unregistered, the script registers the S3 location with the AWSServiceRoleForLakeFormation service-linked role. For more information, see [AWS Lake Formation Documentation](https://docs.aws.amazon.com/lake-formation/latest/dg/registration-role.html).
- The `--region` parameter is optional. If not specified, it defaults to AWS region specified in the CLI credentials config.
