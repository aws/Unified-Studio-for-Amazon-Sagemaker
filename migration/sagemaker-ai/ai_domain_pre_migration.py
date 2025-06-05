import argparse
import boto3
import pandas as pd
from botocore.exceptions import ClientError

from constants import SAGEMAKER_AI_DOMAIN_NAME, SAGEMAKER_AI_DOMAIN_ID, MIGRATION_STATUS, SMUS_USER_NAME, \
    SMUS_PROJECT_NAME, SMUS_DOMAIN_NAME, SAGEMAKER_AI_USER_PROFILE_NAME, SMUS_USER_ROLE


class MigrationConfig:
    def __init__(self, region, account_id, iam_profile):
        self.region = region
        self.account_id = account_id
        self.sagemaker_domain_id = None
        self.sagemaker_domain_vpc_id = None
        self.sagemaker_domain_subnet_ids = None
        self.datazone_project_s3_path = None
        self.datazone_project_id = ""
        if iam_profile:
            session = boto3.Session(profile=iam_profile, region_name=region)
        else:
            session = boto3.Session(region_name=region)
        datazone_endpoint_url = "https://datazone." + region + ".api.aws" 
        sagemaker_endpoint_url = "https://api.sagemaker." + region + ".amazonaws.com"
        
        self.sagemaker_client = session.client("sagemaker", region_name=self.region,
                                               endpoint_url=sagemaker_endpoint_url)
        self.datazone_client = session.client("datazone", region_name=self.region, endpoint_url=datazone_endpoint_url)

    def _get_sagemaker_users(self, domain_id):
        """Get list of users in the SageMaker AI domain"""
        try:
            users = []
            paginator = self.sagemaker_client.get_paginator('list_user_profiles')
            for page in paginator.paginate(DomainIdEquals=domain_id):
                users.extend(page['UserProfiles'])
            return users
        except Exception as e:
            print(f"Error getting SageMaker users: {e}")
            raise

    def _get_domains(self, domain_type, client, paginator_name, filter_condition=None):
        print(f"\nList of {domain_type} Domains for your account")
        domains = []
        try:
            paginator = client.get_paginator(paginator_name)
            for page in paginator.paginate():
                if filter_condition:
                    if domain_type == "UnifiedStudio":
                        domains.extend([d for d in page['items'] if filter_condition(d)])
                    elif domain_type == "AIStudio":
                        domains.extend([d for d in page['Domains'] if filter_condition(d)])
                else:
                    domains.extend(page['items'])
        except ClientError as e:
            print(f"Error listing domains: {str(e)}")
            return None, None

        if not domains:
            print("No domains found in this account.")
            return None, None

        domain_map = {}  # save name->id map
        for idx, domain in enumerate(domains, 1):
            if domain_type == "UnifiedStudio":
                domain_name = domain.get("name", "N/A")
                domain_id = domain.get("id", "N/A")
            elif domain_type == "AIStudio":
                domain_name = domain.get("DomainName", "N/A")
                domain_id = domain.get("DomainId", "N/A")
            domain_map[domain_name] = domain_id
            print(f"{idx}. Name: {domain_name} (ID: {domain_id})")

        return domains, domain_map

    def generate_config(self):
        print("Generating migration config ...")
        fieldnames = [SAGEMAKER_AI_DOMAIN_NAME, SAGEMAKER_AI_DOMAIN_ID, SAGEMAKER_AI_USER_PROFILE_NAME, SMUS_DOMAIN_NAME,
                      SMUS_PROJECT_NAME, SMUS_USER_NAME, SMUS_USER_ROLE, MIGRATION_STATUS]
        df = pd.DataFrame(columns=fieldnames)
        ai_domains, ai_domains_map = self._get_domains(
            "AIStudio",
            self.sagemaker_client,
            'list_domains',
            lambda d: d['Status'] == 'InService'
        )
        for domain_name, domain_id in ai_domains_map.items():
            user_profiles_for_domain = self._get_sagemaker_users(domain_id)
            for user in user_profiles_for_domain:
                df = pd.concat([df, pd.DataFrame([{
                    SAGEMAKER_AI_DOMAIN_NAME: domain_name,
                    SAGEMAKER_AI_DOMAIN_ID: domain_id,
                    SAGEMAKER_AI_USER_PROFILE_NAME: user['UserProfileName'],
                    SMUS_DOMAIN_NAME: "",
                    SMUS_PROJECT_NAME: "",
                    SMUS_USER_NAME: "",
                    SMUS_USER_ROLE: "PROJECT_CONTRIBUTOR",
                    MIGRATION_STATUS: 'Pending'
                }])], ignore_index=True)

        df.to_csv('ai_domain_migration_config.csv', index=False)
        print("Migration Config generated successfully! Please go through README instructions to populate the empty "
              "column values.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SageMaker Studio Domain Migration Config Generator Tool")
    parser.add_argument(
        "--region",
        type=str,
        required=True,
        help="AWS Region with SageMaker resources",
    )
    
    parser.add_argument(
        "--account-id",
        type=str,
        required=True,
        help="AWS AccountId that contains the Studio domain and account where you want your Unified Studio domain to "
             "exist",
    )

    parser.add_argument(
        "--iam-profile",
        type=str,
        required=False,
        help="AWS Credentials profile to use.",
    )

    args = parser.parse_args()
    region = args.region
    account_id = args.account_id
    iam_profile = args.iam_profile

    config_generator = MigrationConfig(region, account_id, iam_profile)
    config_generator.generate_config()
