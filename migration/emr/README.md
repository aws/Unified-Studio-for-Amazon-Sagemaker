# Migrating from EMR Studio Notebooks to SageMaker Unified Studio for Data Processing

## Introduction

This guide provides step-by-step instructions and example script samples to help you migrate from Amazon EMR Studio to SageMaker Unified Studio for Data Processing. These resources will assist you in creating SageMaker Unified Studio for Data Processing projects in AWS Organization Member accounts.

# Considerations and Limitations

- All project members can access saved notebooks migrated to a project
- Sagemaker Unified Studio does not support EMR Studio Notebooks with multiple runtime roles, yet (But can be worked around with connections)
- Migration of existing IAM Runtime roles into Project User role is not supported (yet)
- You can configure one IAM (user) role per project following below instructions
- [AWS CloudShell](https://aws.amazon.com/cloudshell/) is the preferred Unix shell environment for running these commands.
- **IMPORTANT**: EMR Security Requirements
  EMR on EC2 clusters must have a security configuration with in-transit encryption enabled before they can be onboarded to SageMaker Studio. This is a mandatory prerequisite.

**NOTE**: EMR Serverless Integration
- Console integration: Adding existing EMR Serverless Applications via the SageMaker Studio UI will be available in future releases
- Current workaround: You can attach existing EMR Serverless Applications using the custom connector script provided in this git page.


## The migration process focuses on three key areas:

1. IAM Roles (Runtime Roles)
2. EMR Studio (Notebooks)
3. EMR Compute (Permission Changes)


## End-to-End Migration Flow

The following diagram illustrates the end-to-end migration process:

![End-to-End Migration Flow](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/raw/main/migration/emr/img/e2e.png)

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Migration Steps](#migration-steps)
   - [2.1 IAM Roles Migration](#step-1-iam-roles-runtime-roles---bring-your-own-role)
   - [2.2 Notebooks Migration](#step-2-inventory-your-emr-studio-resources)
   - [2.3 EMR Compute Migration](#step-2-emr-compute---update-data-source-connections-in-unified-studio)


## Prerequisites

Before proceeding with migration, ensure you have:

- Understanding of [Amazon SageMaker Unified Studio](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/adminguide/what-is-sagemaker-unified-studio.html)
- Access to a [domain](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/adminguide/working-with-domains.html) and a project created in SageMaker Unified Studio (Refer to [Create a new project](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/create-new-project.html))
- Python, [boto3](https://pypi.org/project/boto3/) installed on the machine where you'll execute migration steps
- [AWS Command Line Interface (AWS CLI)](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) installed/updated and configured on the machine where you'll execute migration steps
- The IAM User/Role performing the steps in this guide should have the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
              "elasticmapreduce:GetClusterSessionCredentials"
            ],
            "Resource": "arn:aws:elasticmapreduce:<region>:<aws-account-id>:cluster/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "codecommit:GetBranch",
                "codecommit:CreateCommit"
            ],
            "Resource": "arn:aws:codecommit:<region>:<aws-account-id>:<repo-name>"
        },
        {
            "Effect": "Allow",
            "Action": [
                "datazone:ListConnections",
                "datazone:UpdateConnection"
            ],
            "Resource": "*"
        }
    ]
}
```
- Add the IAM user/role as the [domain's owner](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/adminguide/user-management.html) and the [project's owner](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/add-project-members.html) to be able to execute steps in this guide

## Migration Steps

### Step 1: IAM Roles (Runtime roles) - Bring your own role

Refer to this [section](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/blob/main/migration/bring-your-own-role/README.md) for migrating your existing roles into Sagemaker Unified Studio.

### Step 2: Inventory Your EMR Studio Resources

- List all notebooks, workspaces, and associated data
- Identify and Copy Necessary Artifacts for Migration to Sagemaker Unified Studio

From your SM Unified Studio Project notebook terminal, perform the following steps:

![Terminal](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/blob/main/migration/emr/img/terminal.png))

a. Describe the EMR Studio by its ID to get the Default S3 location:

```bash
aws emr describe-studio --studio-id es-XXXXX
```

Example output:

```
{
"Studio": {
"StudioId": "es-XXXXX",
"StudioArn": "arn:aws:elasticmapreduce:us-west-2:XXXXXXXXXX:studio/es-XXXXX",
"Name": "Studio_2",
"Description": "",
"AuthMode": "IAM",
"ServiceRole": "arn:aws:iam::XXXXXXXXXX:role/service-role/AmazonEMRStudio_ServiceRole_1728498237293",
"Url": "https://es-D5G4WREET32JMJ0W90RN686KH.emrstudio-prod.us-west-2.amazonaws.com",
"CreationTime": "2024-10-09T11:24:12.396000-07:00",
"DefaultS3Location": "s3://aws-emr-studio-XXXXXXXXXX-us-west-2/YYYYYYYYYY",
"Tags": [],
"IdcUserAssignment": "null"
}
}
```
b. List S3 default path to identify workspace folders:

NOTE: You might have more than one studio workspace. You have the option to migrate all notebooks across workspaces if your organization allows combining them together, or you can choose to migrate a specific workspace based on your needs. Consider your organization's policies and project requirements when deciding which workspaces to migrate.
If you decide to migrate all workspaces, you'll need to repeat the following steps for each workspace. If you're migrating a specific workspace, choose the appropriate workspace folder in the next step.

```
aws s3 ls s3://aws-emr-studio-XXXXXXXXXX-us-west-2/YYYYYYYYYY/
```

Example output:
```
                           PRE e-XXXXX/
                           PRE e-YYYYY/
```
c. Download an entire sub-folder to your local machine:

```
aws s3 cp --recursive s3://aws-emr-studio-XXXXXXXXXX-us-west-2/YYYYYYYYYY/e-XXXXX/ emr_workspace_files/e-XXXXX
```

### Step 2. Migrate your notebooks

    - Export notebooks from EMR Studio
    - Import notebooks into SageMaker Unified Studio

a.  Clone the GitHub repository:

```
$ git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
$ cd Unified-Studio-for-Amazon-Sagemaker/migration/emr/
```

b. Execute the migration script, replacing repo_id with your project's repository ID. You can find the repo_id in your SageMaker Studio project's overview page (right panel). Example format: datazone-yyyyyyyyyyy-dev

```
$ python3 emr-migration.py --localPath <Local_path_To_EMR_workspace with e-BBBBBB> --repo <Sagemaker_studio_project_repoid> --emrStudioId es-AAAAAAA --emrWorkspaceId e-BBBBBB
```

c. After running this script, go to the Sagemaker Unified Studio portal and perform a git pull from the UI to see the imported files from the EMR workspace:


<table>
  <tr>
    <td><img src="https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/blob/main/migration/emr/img/repo.png" width="400"></td>
    <td><img src="https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/blob/main/migration/emr/img/repo2.png" width="400"></td>
  </tr>
</table>


### Step 3: EMR Compute - Update Data Source Connections in Unified Studio

    - Reconfigure data source connections in SageMaker Unified Studio 
    - Prepare Your EMR Compute for Sagemaker Unified Studio Interface/Notebooks

Unified Studio supports two types of connections for EMR compute:

    1. EMR Serverless
    2. EMR on EC2

Depending on your requirements and existing infrastructure, you'll need to choose and prepare the appropriate EMR compute option for use with Sagemaker Unified Studio. Follow the instructions below based on your situation:

   #### Option 1: Setting Up New EMR Compute

If you plan to use a new EMR Cluster or Application:

For EMR Serverless:

     Go to Portal, project → Compute → Data Analytics → Add Compute → EMR Serverless

For EMR on EC2:

     Go to Portal, project → Compute → Data Analytics → Add Compute → EMR on EC2

![Compute](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/blob/main/migration/emr/img/addcompute.png)

![Compute](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/blob/main/migration/emr/img/addcompute2.png)


After completing these steps, your chosen EMR compute resource will be available for use within your project. You can now use this compute environment with notebooks and workflows.

Ensure that your EMR compute has the necessary permissions and network access to interact with other resources in your project, such as S3 buckets or other AWS services.


   #### Option 2: Using Existing EMR Compute

If you plan to use existing EMR compute resource:

2.1 For existing EMR on EC2 Clusters (Console): Review [AWS docs](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/adding-existing-emr-on-ec2-clusters.html).

2.2 Adding Existing EMR Serverless Applications (Console)
Console support for adding existing EMR Serverless applications is planned for future release. 
For now, use the custom script method described [below](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/blob/main/migration/emr/README.md#optional-setting-up-sagemaker-unified-studio-connector-for-emr-compute) to create connections.


### [Optional] Setting up Sagemaker Unified Studio Connector for EMR Compute

**IMPORTANT NOTE**

These configuration steps are only necessary if you haven't already added your existing EMR Compute through the console or want to bring existing EMR Serverless application. If you have used the console to configure your EMR Compute, you can skip these steps.

#### Configuration Steps
1. EMR Serverless Configuration

Open JupyterHub from Studio Console and execute the following in your notebook:

```
# Install required boto3 version
%%bash
micromamba install -y -c conda-forge boto3="1.36.10"

# Configure variables
domain_id = "dzd_xxxxxxxxx"    # Your DataZone domain ID
project_id = "c4bxxxxxxx"      # Your project ID
env_id = "4c4bxxxxxxx"         # Your environment ID
region = "us-east-1"          # Your AWS region

# Initialize boto3 client
import boto3
print(boto3.__version__)
datazone = boto3.client('datazone', region_name=region)

# Create EMR Serverless connection
response = datazone.create_connection(
    domainIdentifier=domain_id,
    environmentIdentifier=env_id,
    name='emr-serverless',    # Customizable connection name
    props={
        'sparkEmrProperties': {
            'computeArn': 'arn:aws:emr-serverless:us-east-1:0123456789:/applications/00f000000000'
        }
    }
)

# Store connection_id from response for future reference
connection_id = response['connectionId']

# Verify connection
datazone.get_connection(
    domainIdentifier=domain_id,
    identifier=connection_id,
    withSecret=True
)
```

After executing the appropriate configuration code:
        a. Click the refresh button next to the connector dropdown in the notebook cell
        b. Select PySpark and your newly created connection name

Open a new notebook in Unified Studio to verify the connector appears in the available options

![EMR Serverless Connector](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/blob/main/migration/emr/img/emr-s-connect.png)


2. EMR on EC2 Configuration:

Open JupyterHub from Studio Console and execute the following in your notebook:

```
# Install required boto3 version
%%bash
micromamba install -y -c conda-forge boto3="1.36.10"

# Configure variables
domain_id = "dzd_b4ddddddddd"
project_id = "dzd_b4ddddddddd"
env_id = "40ddddddddd"
region = "us-east-1"

# Initialize boto3 client
import boto3
print(boto3.__version__)
datazone = boto3.client('datazone', region_name=region)

# Create EMR on EC2 connection
response = datazone.create_connection(
    domainIdentifier=domain_id,
    environmentIdentifier=env_id,
    name='emr-on-ec2',    # Customizable connection name
    props={
        'sparkEmrProperties': {
            'computeArn': 'arn:aws:elasticmapreduce:us-west-2:0123456789:cluster/j-ERRFTGTTF',
            'trustedCertificatesS3Uri': 's3://amazon-maxdome-0123456789-us-east-1-196990529/dzd_b4ddddddddd/xxxxxxxx/emr-cert/trustedCertificates.pem'
        }
    }
)

# Store connection_id from response for future reference
connection_id = response['connectionId']

# Verify connection
datazone.get_connection(
    domainIdentifier=domain_id,
    identifier=connection_id,
    withSecret=True
)
```

After executing the appropriate configuration code:
        a. Click the refresh button next to the connector dropdown in the notebook cell
        b. Select PySpark and your newly created connection name

Open a new notebook in Unified Studio to verify the connector appears in the available options

![EMR on EC2 Connector](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/blob/main/migration/emr/img/emr-ec2.png)

#### Important Considerations:

When connecting to an Amazon EMR Serverless application, Unified Studio can only use the project role (also known as the user role) as the runtime role. This differs from EMR Studio, where users can choose from multiple runtime roles. To ensure that migrated EMR Studio notebooks continue to function properly, the project/user role must have the same permissions as the runtime role previously used in EMR Studio.

1. Ensure your EMR Serverless application is using EMR version 7 or later.
2. Verify that the Livy endpoint is enabled in your EMR Serverless application configuration.
3. Add the following trust relationship to your Sagemaker Unified Studio project/user role:

```
{
"Sid": "ServerlessTrustPolicy",
"Effect": "Allow",
"Principal": {
"Service": "emr-serverless.amazonaws.com"
},
"Action": "sts:AssumeRole",
"Condition": {
"StringLike": {
"aws:SourceAccount": "121223232323232",
"aws:SourceArn": "arn:aws:emr-serverless:us-west-2:121223232323232:/applications/00fsdsdssdsldkfd"
}
}
}
```

#### Differences in EMR Magics

EMR magics are special commands used in notebooks to interact with EMR clusters. The syntax and availability of these magics differ between EMR Studio Notebooks and SageMaker Studio Notebooks. Below is a comparison table showing the differences and, where available, the corresponding equivalents:


| EMR Studio Notebook Magic | SageMaker Studio Notebook Equivalent | Notes |
| ------------------------- | ------------------------------------ | ----- |
| %%sql                     | %%sql                                | Available in both environments, but may have slight syntax differences |
| %%info                    | %%info                               | Use alternative methods to get cluster information |
| %%configure               | Need connection switch               | Change to Local Python and use syntax: %%configure -f —name "YOUR_CONNECTION_NAME" |
| %%display                 | %display                             | Changed to line magic |
| %%spark                   | Use PySpark directly                 | In SageMaker, you typically write PySpark code without a specific magic |
| %%sparkql                 | Use Spark SQL API                    | Write Spark SQL queries using the PySpark SQL API |
| %%python                  | Not needed                           | Python is the default in SageMaker notebooks |
| %execute-notebook         | Not available                        | Use alternative methods for notebook-level operations |
| %mount_workspace_dir      | Not available                        | Use alternative methods for notebook-level operations |
| %generate_s3_download_url | Not available                        | Use alternative methods for notebook-level operations |
| %matplotlib               | Not available                        | Use alternative methods for notebook-level operations |

