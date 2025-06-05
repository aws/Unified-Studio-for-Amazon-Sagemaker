import argparse
import boto3

from collections import defaultdict


class BringYourOwnSageMakerAIResources:
    def __init__(self, region, account_id, sagemaker_domain_id, datazone_project_id, iam_profile):
        self.region = region
        self.account_id = account_id
        self.assumed_role_name = "Admin"
        self.sagemaker_domain_id = sagemaker_domain_id
        self.datazone_project_id = datazone_project_id
        if iam_profile:
            session = boto3.Session(profile_name=iam_profile, region_name=region)
        else:
            session = boto3.Session(region_name=region)
        datazone_endpoint_url = "https://datazone." + region + ".api.aws"
        sagemaker_endpoint_url = "https://api.sagemaker." + region + ".amazonaws.com"

        self.sagemaker_client = session.client("sagemaker", region_name=self.region,
                                               endpoint_url=sagemaker_endpoint_url)

        self.datazone_client = session.client("datazone", region_name=self.region, endpoint_url=datazone_endpoint_url)
        self.tagging_client = session.client('resourcegroupstaggingapi', region_name=self.region)

    def _get_sagemaker_resources_tagged_with_domain_arn(self):
        print("\nGetting all resources tagged with your SageMaker AI domain")
        paginator = self.tagging_client.get_paginator('get_resources')

        sagemaker_domain_arn = f"arn:aws:sagemaker:{self.region}:{self.account_id}:domain/{self.sagemaker_domain_id}"
        tag_filters = [
            {
                'Key': "sagemaker:domain-arn",
                'Values': [sagemaker_domain_arn]
            }
        ]

        tagged_resources = defaultdict(list)

        for page in paginator.paginate(
                ResourceTypeFilters=['sagemaker'],
                TagFilters=tag_filters
        ):
            for resource in page['ResourceTagMappingList']:
                arn = resource['ResourceARN']
                resource_type = arn.split(':')[5].split('/')[0]
                tagged_resources[resource_type].append(arn)

        return tagged_resources

    def _tag_sagemaker_resource_with_datazone_project(self):
        tagged_resources = self._get_sagemaker_resources_tagged_with_domain_arn()
        if not tagged_resources:
            print(f"\nNo SageMaker resources found with the specified domain tag {self.sagemaker_domain_id}")
            return

        for resource_type, resources in tagged_resources.items():
            if resource_type in ['user-profile', 'space', 'app']:
                continue
            print(
                f"Importing {resource_type} resources in SageMaker Unified Studio project {self.datazone_project_id}")
            for arn in resources:
                print(f"Processing {resource_type} {arn}...")
                try:
                    self.sagemaker_client.add_tags(
                        ResourceArn=arn,
                        Tags=[{
                            'Key': 'AmazonDataZoneProject',
                            'Value': self.datazone_project_id
                        }]
                    )
                    print(f"Successfully imported {arn}")
                except Exception as e:
                    print(f"Failed to import {arn}': {str(e)}")

    def import_sagemaker_ai_resources(self):
        print("Starting import of SageMaker AI resources in Unified Studio Project ...")
        self._tag_sagemaker_resource_with_datazone_project()
        print("Import complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get the resources tagged with SageMaker AI domain and import "
                                                 "them in SageMaker Unified Studio Project")
    parser.add_argument("--region", help="AWS Region", required=True)
    parser.add_argument("--account-id", help="AWS Account ID", required=True)
   
    parser.add_argument("--sagemaker-domain-id", help="SageMaker AI Domain ID", required=True)
    parser.add_argument("--unified-studio-project-id", help="SageMaker Unified Studio Project ID",
                        required=True)
    parser.add_argument(
        "--iam-profile",
        type=str,
        required=False,
        help="AWS Credentials profile to use.",
    )
    args = parser.parse_args()

    bring_your_own_sagemaker_ai_resources = BringYourOwnSageMakerAIResources(args.region, args.account_id,
                                                                             args.sagemaker_domain_id,
                                                                             args.unified_studio_project_id, args.iam_profile)

    bring_your_own_sagemaker_ai_resources.import_sagemaker_ai_resources()
