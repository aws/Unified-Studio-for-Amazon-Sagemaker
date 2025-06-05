import argparse
import json
import os
import runpy
import sys
import time
from datetime import datetime

import boto3
import botocore
from botocore.exceptions import ClientError
import pandas as pd

from bring_your_own_sagemaker_ai_resources import BringYourOwnSageMakerAIResources
from constants import DZ_PROJECT_PROFILE_NAME, DZ_PROJECT_SCOPE_NAME, SAGEMAKER_AI_DOMAIN_NAME, SAGEMAKER_AI_DOMAIN_ID, \
    MIGRATION_STATUS, SMUS_USER_NAME, \
    SMUS_PROJECT_NAME, SMUS_DOMAIN_NAME, SAGEMAKER_AI_USER_PROFILE_NAME, SMUS_USER_ROLE

USER_MAPPINGS = 'USER_MAPPINGS'


def assumed_role_session(account_id: str, role_name: str, base_session: boto3.Session = None):
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    base_session = base_session or boto3.Session()

    sts = base_session.client('sts')
    current_identity = sts.get_caller_identity()
    print(f"Attempting to assume role {role_arn} from {current_identity['Arn']}")

    try:
        assumed_role = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"AssumedSession-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )

        return boto3.Session(
            aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
            aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
            aws_session_token=assumed_role['Credentials']['SessionToken']
        )
    except botocore.exceptions.ClientError as e:
        print(f"Failed to assume role: {str(e)}")
        raise


def print_separator():
    print("--------------------------------------------------------------------")


def get_yes_no_input(prompt, default='y'):
    """
    Get y/n input with validation and default value

    Args:
        prompt (str): Input prompt message
        default (str): Default value ('y' or 'n')

    Returns:
        bool: True for yes, False for no
    """
    while True:
        choice = input(f"{prompt} (Y/n) ").strip().lower() or default
        if choice in ['y', 'yes']:
            return True
        elif choice in ['n', 'no']:
            return False
        print("Please enter 'y' or 'n'")


class SageMakerAIDomainToUnifiedStudioDomainMigrator:
    def __init__(self, region: str, account_id: str, iam_profile: str, migration_config_file: str):
        self.iam_profile = iam_profile
        self.region = region
        self.account_id = account_id
        self.migration_config_file = migration_config_file

        if iam_profile:
            session = boto3.Session(profile_name=iam_profile, region_name=region)
        else:
            session = boto3.Session(region_name=region)
        datazone_endpoint_url = "https://datazone." + region + ".api.aws" 
        sagemaker_endpoint_url = "https://api.sagemaker." + region + ".amazonaws.com" 
        self.sagemaker_client = session.client("sagemaker", region_name=self.region,
                                               endpoint_url=sagemaker_endpoint_url)
        self.datazone_client = session.client("datazone", region_name=self.region, endpoint_url=datazone_endpoint_url)

    def _list_domains(self, domain_type, client, paginator_name, filter_condition=None):
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

    def _get_unified_studio_domains(self):
        print(f"\nFetching Unified Studio domains in your account")
        domains, domain_map = self._list_domains(
            "UnifiedStudio",
            self.datazone_client,
            'list_domains',
            lambda d: d['status'] == 'AVAILABLE'
        )

        if domains is None:
            print("No existing Unified Studio domains found in this account. "
                  "Please make sure you have created a Unified Studio Domain and Populated it in the file.")
            exit(1)

        self.datazone_domains = domains
        self.datazone_domain_name_id_map = domain_map

    def _choose_sagemaker_domain(self):
        print("\nList of InService SageMaker Domains for your account.")
        print_separator()
        domains, domain_map = self._list_domains(
            "AIStudio",
            self.sagemaker_client,
            'list_domains',
            lambda d: d['Status'] == 'InService'
        )

        if domains is None:
            return None
        self.sagemaker_domains = domains
        domain_name = input(f"\nEnter SageMaker AI Domain Name that you wish to migrate: ")
        while domain_name not in domain_map:
            print(f"SageMaker AI Domain {domain_name} not found. Please choose a domain name from the list.")
            domain_name = input(f"\nEnter SageMaker AI Domain Name that you wish to migrate: ")

        domain_id = domain_map[domain_name]
        print(
            f"\nChosen SageMaker AI Domain [{domain_name}] with Domain Id [{domain_id}]"
        )
        describe_domain_response = self.sagemaker_client.describe_domain(
            DomainId=domain_id
        )
        self.sagemaker_domain_vpc_id = describe_domain_response.get("VpcId")
        self.sagemaker_domain_subnet_ids = describe_domain_response.get("SubnetIds")
        sagemaker_domain_name, sagemaker_domain_id = domain_name, domain_id

    def _list_and_get_tooling_blueprint_for_datazone_domain(self, datazone_domain_id: str):
        print_separator()
        print(f"\nList of environment blueprints for your domain [{datazone_domain_id}]")
        try:
            paginator = self.datazone_client.get_paginator('list_environment_blueprints')
            blueprint_items = []

            # Iterate through all pages
            for page in paginator.paginate(
                    domainIdentifier=datazone_domain_id,
                    managed=True
            ):
                if 'items' in page:
                    blueprint_items.extend(page['items'])

            self.domain_env_blueprints = blueprint_items
            for bp in self.domain_env_blueprints:
                print("Id: ", bp["id"], " Name: ", bp["name"])

            base_tooling_blueprint = next((bp for bp in self.domain_env_blueprints if bp["name"] == "Tooling"), None)
            if base_tooling_blueprint is None:
                print("Managed Tooling blueprint not found. Cannot proceed.")
                return
            chosen_blueprint_id = base_tooling_blueprint["id"]
            chosen_blueprint_name = base_tooling_blueprint["name"]
            chosen_blueprint_description = base_tooling_blueprint["description"]
            is_blueprint_enabled, datazone_project_s3_path = self._check_blueprint_enabled_for_datazone_domain(
                chosen_blueprint_id,
                chosen_blueprint_name, datazone_domain_id)
            if not is_blueprint_enabled:
                raise RuntimeError("Managed Tooling blueprint is not enabled in the domain. Cannot proceed.")
            print(f"\nChoosing blueprint {chosen_blueprint_id} to create a new project profile")
            return chosen_blueprint_id, chosen_blueprint_name, chosen_blueprint_description, datazone_project_s3_path

        except ClientError as e:
            raise RuntimeError(f"Error listing environment blueprints: {e}")

    def _check_blueprint_enabled_for_datazone_domain(self, blueprint_id: str, blueprint_name: str,
                                                     datazone_domain_id: str):
        print(f"\n Checking if {blueprint_name} blueprint is enabled.")
        try:
            # List blueprint configurations
            response = self.datazone_client.get_environment_blueprint_configuration(
                domainIdentifier=datazone_domain_id,
                environmentBlueprintIdentifier=blueprint_id
            )

            # Check if the current region is in the enabledRegions list
            if self.region in response.get('enabledRegions', []):
                print(
                    f"\n{blueprint_name} Blueprint with id: {blueprint_id} is enabled in domain {datazone_domain_id} for region {self.region}")
                # Extract S3 location from regionalParameters
                regional_params = response.get('regionalParameters', {}).get(self.region, {})
                if regional_params and 'S3Location' in regional_params:
                    datazone_project_s3_path = regional_params['S3Location']
                    print(f"Found S3 location: {datazone_project_s3_path}")
                return True, datazone_project_s3_path

            print(
                f"\nBlueprint with name: {blueprint_name} and id: {blueprint_id} is not enabled in domain {datazone_domain_id} for region {self.region}."
                f"Please enable the blueprint and try again.")
            return False, None

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(
                f"\nError occurred when listing blueprint configuration errorcode: {error_code} with message: {error_message}")
        return False, None

    def _get_tooling_environment(self, datazone_domain_id: str, datazone_project_id: str):
        print("List of Unified Studio Environments.")
        print_separator()
        datazone_env_map = {}
        for env in self.datazone_client.list_environments(
                domainIdentifier=datazone_domain_id, projectIdentifier=datazone_project_id
        )["items"]:
            print(f'Name: {env["name"]} Id: {env["id"]}')
            datazone_env_map[env["name"]] = env["id"]
        chosen_env_name = "Tooling"
        env_id = datazone_env_map[chosen_env_name]
        print(f"\nUsing environment: {chosen_env_name} with id {env_id}")

        return env_id

    def _enable_project_profile_for_all_users(self, project_profile_id: str, datazone_domain_id: str):
        print_separator()
        try:
            # Get domain info to get root domain unit ID
            domain_info = self.datazone_client.get_domain(
                identifier=datazone_domain_id
            )
            self.root_domain_unit_id = domain_info.get('rootDomainUnitId')
            print(f"\nEnabling project profile {project_profile_id} for all users in the root domain unit "
                  f"{self.root_domain_unit_id} for domain {datazone_domain_id}")
            if not self.root_domain_unit_id:
                raise ValueError("Root domain unit ID not found in domain info")

            # Add policy grant for all users
            self.datazone_client.add_policy_grant(
                domainIdentifier=datazone_domain_id,
                entityType='DOMAIN_UNIT',
                entityIdentifier=self.root_domain_unit_id,
                policyType='CREATE_PROJECT_FROM_PROJECT_PROFILE',
                principal={
                    'user': {
                        'allUsersGrantFilter': {}
                    }
                },
                detail={
                    'createProjectFromProjectProfile': {
                        'projectProfiles': [project_profile_id],
                        'includeChildDomainUnits': True
                    }
                }
            )

            print(f"Successfully enabled project profile for all users in domain {datazone_domain_id}")
        except ClientError as e:
            print(f"Error enabling project profile for all users: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error enabling project profile: {e}")
            raise

    def _create_project_profile_for_datazone_domain(self, datazone_domain_id: str, blueprint_name: str,
                                                    blueprint_description: str,
                                                    blueprint_id: str):
        print(f"\nUsing the {blueprint_name} blueprint to create a new project profile")
        try:
            # Create the project profile configuration
            project_profile_configuration = {
                "domainIdentifier": datazone_domain_id,
                "name": DZ_PROJECT_PROFILE_NAME,
                "description": "This sample project profile creates a tooling environment without spaces.",
                "environmentConfigurations": [
                    {
                        "awsAccount": {
                            "awsAccountId": self.account_id
                        },
                        "awsRegion": {
                            "regionName": self.region
                        },
                        "configurationParameters": {
                            "parameterOverrides": [
                                {
                                    "isEditable": True,
                                    "name": "enableSpaces",
                                    "value": "false"
                                }
                            ]
                        },
                        "description": blueprint_description,
                        "environmentBlueprintId": blueprint_id,
                        "name": blueprint_name,
                        "deploymentMode": "ON_CREATE",
                        "deploymentOrder": 0
                    }
                ],
                "status": "ENABLED"
            }

            # Create the project profile
            create_project_profile_response = self.datazone_client.create_project_profile(
                **project_profile_configuration
            )
            datazone_project_profile_id = create_project_profile_response['id']
            self._enable_project_profile_for_all_users(datazone_project_profile_id, datazone_domain_id)
            print(
                f"\nCreated project profile: {project_profile_configuration['name']} with id: {datazone_project_profile_id}")
            return datazone_project_profile_id
        except ClientError as e:
            if "Conflict with projectProfile" in str(e) \
                    or "(ConflictException) when calling the CreateProjectProfile operation" in str(e):
                print(
                    "Project Profile already exists. Skipping creation ..."
                )
                datazone_project_profile_id = self.datazone_client.list_project_profiles(
                    domainIdentifier=datazone_domain_id,
                    name=DZ_PROJECT_PROFILE_NAME
                )['items'][0]['id']
                self._enable_project_profile_for_all_users(datazone_project_profile_id, datazone_domain_id)
                return datazone_project_profile_id
            else:
                raise RuntimeError(f"Error creating project profile: {e}")

    def _get_datazone_project_from_sagemaker_domain(self, sagemaker_domain_id: str):
        print(
            f"\nChecking if the SageMaker AI domain {sagemaker_domain_id} is associated with a Unified Studio project.")
        try:
            describe_domain_response = self.sagemaker_client.describe_domain(
                DomainId=sagemaker_domain_id
            )
            domain_settings = describe_domain_response.get("DomainSettings")
            if domain_settings:
                unified_studio_settings = domain_settings.get("UnifiedStudioSettings")
                if unified_studio_settings:
                    if 'ProjectId' in unified_studio_settings:
                        project_id = unified_studio_settings['ProjectId']
                        datazone_domain_id = unified_studio_settings['DomainId']
                        if datazone_domain_id != datazone_domain_id:
                            print(
                                f"\nSageMaker AI domain {sagemaker_domain_id} is associated with Unified Studio project {project_id} in a different domain {datazone_domain_id}")
                        else:
                            continue_with_existing_project = get_yes_no_input(
                                f"\nSageMaker AI domain {sagemaker_domain_id} is already associated with Unified "
                                f"Studio project {project_id}. Do you want to continue with same project? Enter n to create a new project. "
                                f"Note: If your SageMaker AI domain execution role is already mapped to Unified Studio "
                                f"project, please delete this project first and then re-run the script.")
                            if continue_with_existing_project:
                                datazone_project_id = project_id
                                project_details = self.datazone_client.get_project(
                                    domainIdentifier=datazone_domain_id,
                                    identifier=datazone_project_id
                                )
                                datazone_project_name = project_details.get("name")
                                return True, datazone_project_name, datazone_project_id
                            else:
                                return False, None, None
                else:
                    print(
                        f"\nSageMaker domain {sagemaker_domain_id} is not associated with any Unified Studio "
                        f"project.")
            return False, None, None

        except ClientError as e:
            print(f"Error getting domain information: {e}")
            return None, None, None

    def _create_datazone_project_for_domain(self, datazone_domain_id: str, datazone_project_name: str,
                                            datazone_project_profile_id: str):
        print_separator()
        print(f"\nCreating a new project for Unified Studio domain {datazone_domain_id}")
        try:
            # Create the project profile configuration
            project_configuration = {
                "domainIdentifier": datazone_domain_id,
                "name": f"{datazone_project_name}",
                "description": "This sample project creates a tooling environment without spaces.",
                "projectProfileId": datazone_project_profile_id
            }

            # Create the project profile
            create_project_response = self.datazone_client.create_project(
                **project_configuration
            )
            datazone_project_id = create_project_response['id']
            self._wait_for_project_environment_deployment(datazone_domain_id, datazone_project_id,
                                                          datazone_project_name)
            print(
                f"\nSuccessfully Created project: {project_configuration['name']} with id: {create_project_response['id']}")
            return datazone_project_id
        except ClientError as e:
            if "Conflict with project" in str(e) \
                    or "(ConflictException) when calling the CreateProject operation" in str(e):
                raise Exception(
                    f"Project with name {datazone_project_name} already exists in domain {datazone_domain_id}. "
                    f"Please ensure the file contains valid input"
                )
            else:

                raise Exception(f"Error occurred creating Unified Studio project: {e}")

    def _wait_for_project_environment_deployment(self, datazone_domain_id: str, datazone_project_id: str,
                                                 datazone_project_name: str):
        print(
            f"\nWaiting for project name:{datazone_project_name}, id: {datazone_project_id} to become active...")
        while True:
            try:
                response = self.datazone_client.get_project(
                    domainIdentifier=datazone_domain_id,
                    identifier=datazone_project_id
                )

                deployment_details = response.get('environmentDeploymentDetails', {})
                if deployment_details is None:
                    print("No deployment details found for the project.")
                    raise Exception("Project creation did not start!! This is not expected.")
                status = deployment_details.get('overallDeploymentStatus')
                print(f"Current environment deployment status: {status}")

                if status == 'SUCCESSFUL':
                    print("Environment deployment completed successfully")
                    return True
                elif status in ['FAILED_VALIDATION', 'FAILED_DEPLOYMENT']:
                    failure_reasons = deployment_details.get('environmentFailureReasons', {})
                    print("\nDeployment failed with reasons:")
                    for env_id, errors in failure_reasons.items():
                        print(f"\nEnvironment {env_id} failures:")
                        for error in errors:
                            print(f"- {error.get('errorMessage', 'Unknown error')}")
                    raise Exception(f"Project environment deployment failed with status: {status}")

                time.sleep(10)  # Wait 10 seconds before next check

            except ClientError as e:
                print(f"Error checking project status: {e}")
                raise

    def _poll_for_sagemaker_domain_status(self, sagemaker_domain_id: str, target_status="InService"):
        print(f"\nWaiting for domain {sagemaker_domain_id} to reach {target_status} status...")

        while True:
            try:
                response = self.sagemaker_client.describe_domain(DomainId=sagemaker_domain_id)
                current_status = response.get('Status')

                if current_status == target_status:
                    print(f"\nSageMaker AI domain {target_status} update completed.")
                    return response

                print(f"Current status: {current_status}")
                time.sleep(10)

            except Exception as e:
                print(f"Error checking domain status: {e}")
                raise

    def _update_sagemaker_domain_with_tags(self, sagemaker_domain_name: str, sagemaker_domain_id: str,
                                           datazone_domain_id: str,
                                           datazone_project_id: str, datazone_env_id: str,
                                           datazone_project_s3_path: str):
        print_separator()
        print("\nUpdating SageMaker AI domain with Unified Studio metadata and tags")
        try:
            sagemaker_domain_arn = "arn:aws:sagemaker:{}:{}:domain/{}".format(
                self.region, self.account_id, sagemaker_domain_id
            )

            # Add DataZone tags to the Studio AI domain
            sagemaker_domain_tags = [
                {"Key": "AmazonDataZoneEnvironment", "Value": datazone_env_id},
                {"Key": "AmazonDataZoneProject", "Value": datazone_project_id},
                {"Key": "AmazonDataZoneScopeName", "Value": DZ_PROJECT_SCOPE_NAME}
            ]

            # Create the project profile
            self.sagemaker_client.add_tags(ResourceArn=sagemaker_domain_arn, Tags=sagemaker_domain_tags)
            print_separator()
            print(
                "Adding the following tags to SageMaker Domain [{}]".format(
                    sagemaker_domain_name
                )
            )
            for t in sagemaker_domain_tags:
                print(t)

            print(
                f"\nNOTE: AutoMountHomeEFS will be enabled by default for your SageMaker AI domain {sagemaker_domain_name}.")

            print(
                f"\nNOTE: You will still be able to access your domain {sagemaker_domain_name} from SageMaker AI.")
            # TODO: VpcOnlyTrustedAccounts would need to be updated if DomainType is VPCOnly
            print(f"\nNOTE: IdleShutdown for SageMaker AI domain {sagemaker_domain_name} will be enabled.")
            self.sagemaker_client.update_domain(
                DomainId=sagemaker_domain_id,
                DefaultUserSettings={
                    "AutoMountHomeEFS": "Enabled",
                    "JupyterLabAppSettings": {
                        "AppLifecycleManagement": {
                            "IdleSettings": {
                                "LifecycleManagement": "ENABLED",
                                "IdleTimeoutInMinutes": 60,
                                "MaxIdleTimeoutInMinutes": 525600,
                                "MinIdleTimeoutInMinutes": 60
                            }
                        }
                    },
                    "CodeEditorAppSettings": {
                        "AppLifecycleManagement": {
                            "IdleSettings": {
                                "LifecycleManagement": "ENABLED",
                                "IdleTimeoutInMinutes": 60,
                                "MaxIdleTimeoutInMinutes": 525600,
                                "MinIdleTimeoutInMinutes": 60
                            }
                        }
                    }
                },
                DomainSettingsForUpdate={
                    "DockerSettings": {
                        "EnableDockerAccess": "ENABLED",
                        "VpcOnlyTrustedAccounts": []
                    },
                    "UnifiedStudioSettings": {
                        "StudioWebPortalAccess": "ENABLED",
                        "DomainId": datazone_domain_id,
                        "ProjectId": datazone_project_id,
                        "EnvironmentId": datazone_env_id,
                        "ProjectS3Path": f"{datazone_project_s3_path}/{datazone_domain_id}/{datazone_project_id}/{DZ_PROJECT_SCOPE_NAME}"
                    }
                }
            )
            print(f"\nSuccessfully updated domain {sagemaker_domain_name} with tags")
            response = self._poll_for_sagemaker_domain_status(sagemaker_domain_id)

            print(f"\nDomain details after update: {json.dumps(response, indent=4, default=str)}")
        except ClientError as e:
            print(f"Error getting or adding tags to domain: {e}")

    def _get_datazone_users(self, datazone_domain_id):
        user_types = [
            "DATAZONE_SSO_USER"
        ]
        try:
            users = []
            paginator = self.datazone_client.get_paginator('search_user_profiles')
            for user_type in user_types:
                for page in paginator.paginate(
                        domainIdentifier=datazone_domain_id,
                        userType=user_type):
                    users.extend(page['items'])
            return users
        except Exception as e:
            print(f"Error getting DataZone users: {e}")
            raise

    def _list_datazone_users(self, datazone_users):
        print("\nAvailable Unified Studio Users:")
        for user in datazone_users:
            user_type = user.get('type', 'Unknown')
            user_details = user['details']
            username = user.get('details', {}).get('sso', {}).get('username')
            user_id = user.get('id')
            if username:
                print(
                    f" Username: {username}, Id: {user_id}")
            elif user_type == "IAM":
                print(
                    f" UserArn: {user_details['iam']['arn']}, Id: {user['id']}")

    def _list_sagemaker_spaces(self, sagemaker_username, sagemaker_domain_id):
        print(f"\nGetting SageMaker AI Private Spaces with Owner UserProfile as {sagemaker_username}...")
        try:
            paginator = self.sagemaker_client.get_paginator('list_spaces')
            private_spaces = {}
            for page in paginator.paginate(DomainIdEquals=sagemaker_domain_id):
                for space in page['Spaces']:
                    if ('SpaceSharingSettingsSummary' in space and
                            space['SpaceSharingSettingsSummary']['SharingType'] == "Private"):
                        if space['OwnershipSettingsSummary']['OwnerUserProfileName'] == sagemaker_username:
                            space_name = space['SpaceName']
                            private_spaces[space_name] = space

            for space_name, space in private_spaces.items():
                print(f"\n Name: {space['SpaceName']}, Status: {space['Status']}")
            return private_spaces
        except Exception as e:
            print(f"Error getting SageMaker spaces: {e}")

    def _tag_sagemaker_spaces(self, sagemaker_username, user_tags, sagemaker_domain_id):
        sagemaker_spaces = self._list_sagemaker_spaces(sagemaker_username, sagemaker_domain_id)
        if len(sagemaker_spaces) == 0:
            print(
                f"\nNo Private Spaces found in domain {sagemaker_domain_id} with owner user profile: {sagemaker_username}")
            return
        else:
            for space_name in sagemaker_spaces:
                print(f"\nTagging space {space_name} with tags {user_tags}")
                sagemaker_space_arn = f"arn:aws:sagemaker:{self.region}:{self.account_id}:space/{sagemaker_domain_id}/{space_name}"
                self.sagemaker_client.add_tags(
                    ResourceArn=sagemaker_space_arn,
                    Tags=user_tags
                )
                print(f"\nSuccessfully tagged space {space_name} with tags")
                print_separator()

    def _list_user_mappings(self, user_mappings, datazone_sso_users_dict):
        for sagemaker_username, datazone_username in user_mappings.items():
            datazone_user_id = datazone_sso_users_dict[datazone_username]
            print(
                f" SageMaker AI Username: {sagemaker_username} -> Unified Studio UserName: {datazone_username}, UserId: {datazone_user_id}")

    def _map_users(self, sagemaker_domain_id, datazone_domain_id, user_mappings_dict, datazone_project_id):
        print_separator()
        print("\nStarting user mapping process...")

        # Get users from both services
        datazone_users = self._get_datazone_users(datazone_domain_id)

        if not datazone_users:
            print("No users found for Unified Studio domain")
            return

        datazone_users_dict = {user['id']: user for user in datazone_users}
        datazone_sso_usernames_dict = {}
        for user in datazone_users:
            username = user.get('details', {}).get('sso', {}).get('username')
            user_id = user.get('id')
            user_type = user.get('type')

            if user_type and user_type == 'IAM':
                continue
            if username and user_id:
                datazone_sso_usernames_dict[username] = user_id

        # Process user mappings
        for mapping in user_mappings_dict:
            sagemaker_username = mapping[SAGEMAKER_AI_USER_PROFILE_NAME]
            datazone_username = mapping[SMUS_USER_NAME]
            datazone_user_role = mapping[SMUS_USER_ROLE]
            try:
                print(f"\nUpdating tags for SageMaker AI UserProfile {sagemaker_username}")
                user_profile_arn = f"arn:aws:sagemaker:{self.region}:{self.account_id}:user-profile/{sagemaker_domain_id}/{sagemaker_username}"

                # Create tags for the mapping
                datazone_userid = datazone_sso_usernames_dict[datazone_username]
                user_tags = [
                    {"Key": "AmazonDataZoneUser", "Value": datazone_userid},
                    {"Key": "AmazonDataZoneProject", "Value": datazone_project_id}
                ]

                # Apply tags to user profile
                self.sagemaker_client.add_tags(
                    ResourceArn=user_profile_arn,
                    Tags=user_tags
                )

                print(f"Successfully added tags {user_tags} for SageMaker AI UserProfile {sagemaker_username}")

                # Step 2, add the user as a project Owner in Datazone
                if datazone_user_role == 'PROJECT_OWNER':
                    print(
                        f"\n Adding Unified Studio user {datazone_username} to project {datazone_project_id} as Project Owner")
                    self._add_user_to_datazone_project(datazone_userid, 'PROJECT_OWNER',
                                                       datazone_domain_id, datazone_project_id)
                else:
                    print(
                        f"\n Adding Unified Studio user {datazone_username} to project {datazone_project_id} as Project Contributor")
                    self._add_user_to_datazone_project(datazone_userid, 'PROJECT_CONTRIBUTOR',
                                                       datazone_domain_id, datazone_project_id)
                self._tag_sagemaker_spaces(sagemaker_username, user_tags, sagemaker_domain_id)
                print("\nUser mappings Applied!")
                print_separator()
            except Exception as e:
                raise RuntimeError(f"Error applying mapping for user {sagemaker_username}: {e}")

    def _add_user_to_datazone_project(self, datazone_user_id, user_role, datazone_domain_id,
                                      datazone_project_id):
        try:
            self.datazone_client.create_project_membership(
                domainIdentifier=datazone_domain_id,
                projectIdentifier=datazone_project_id,
                designation=user_role,
                member={
                    'userIdentifier': datazone_user_id
                }
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ValidationException":
                error_message = e.response["Error"]["Message"]
                if "User profile" in error_message and "not found for domain" in error_message:
                    print(
                        f"User profile not found error: User {datazone_user_id} does not have a profile in domain {datazone_domain_id}."
                        f"Please add the user {datazone_user_id} to the UnifiedStudio domain and try again!")
                    sys.exit(1)
                else:
                    print(f"\nError adding user {datazone_user_id} to project {datazone_project_id}")
        except Exception as e:
            print(f"\nUnexpected error occurred when adding user to DataZone project: {e}")
            raise

    def _call_byor(self, datazone_domain_id: str, sagemaker_domain_id: str, datazone_project_id: str):
        """
        Interactive function to call BYOR script with user inputs
        """
        describe_domain_response = self.sagemaker_client.describe_domain(
            DomainId=sagemaker_domain_id
        )
        sagemaker_domain_execution_role = describe_domain_response["DefaultUserSettings"]["ExecutionRole"]

        bring_in_role_arn = sagemaker_domain_execution_role
        execute = True
        print("\nUpdating Unified Studio Project Role with SageMaker AI domain execution role")

        # Show summary of inputs
        print("\n=== Role Configuration Summary ===")
        print(f"Domain ID: {datazone_domain_id}")
        print(f"Project ID: {datazone_project_id}")
        print(f"Region: {self.region}")
        print(f"Role ARN: {bring_in_role_arn}")
        print(f"Execute: {execute}")

        # Save original argv
        original_argv = sys.argv.copy()
        role_update_successful = False
        try:
            sys.argv = [
                'byor.py',  # Script name
                'use-your-own-role',  # command
                '--domain-id', datazone_domain_id,
                '--project-id', datazone_project_id,
                '--region', self.region,
                '--bring-in-role-arn', bring_in_role_arn
            ]

            if self.iam_profile:
                sys.argv.append(['--iam-profile', self.iam_profile])
            if execute:
                sys.argv.append('--execute')

            # Get the path to byor.py
            byor_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'bring-your-own-role', 'byor.py'))

            print_separator()
            print("\nStarting to update the Unified Studio Project Role...")
            # Call the main function
            runpy.run_path(byor_path, run_name='__main__')
            role_update_successful = True
            print_separator()

        except Exception as e:
            print(f"\nError updating Unified Studio Project Role: {e}")
            raise

        finally:
            sys.argv = original_argv
            if role_update_successful:
                print("\nUnified Studio Project Role updated successfully")

    def _validate_domain_project_mapping(self, df):
        # Get unique domain-project mappings
        domain_project_mappings = df[[SAGEMAKER_AI_DOMAIN_ID, SMUS_DOMAIN_NAME, SMUS_PROJECT_NAME]].drop_duplicates()

        # Check if any domain has multiple projects
        sagemaker_domains_with_multiple_projects = (
            domain_project_mappings.groupby(SAGEMAKER_AI_DOMAIN_ID)
            .size()
            .loc[lambda x: x > 1]
        )

        if not sagemaker_domains_with_multiple_projects.empty:
            problematic_domains = sagemaker_domains_with_multiple_projects.index.tolist()
            raise ValueError(
                f"\nThe following SageMaker AI Domains are mapped to multiple projects: "
                f"{problematic_domains}.\nEach SageMaker AI domain must be mapped to exactly one project in a SageMaker Unified Studio domain."
            )

        duplicate_projects = (
            domain_project_mappings.groupby([SMUS_DOMAIN_NAME, SMUS_PROJECT_NAME])
            .size()
            .loc[lambda x: x > 1]
        )

        if not duplicate_projects.empty:
            problematic_mappings = duplicate_projects.index.tolist()
            raise ValueError(
                f"\nThe following SageMaker Unified Studio domain and project combinations are mapped to multiple SageMaker AI domains: "
                f"{problematic_mappings}\nEach project within a SMUS domain must be mapped to exactly one SageMaker AI domain."
            )


    def _validate_file_input(self):
        print(f"\nValidating Migration config from file {self.migration_config_file}")
        df = pd.read_csv(self.migration_config_file)
        if df.empty:
            print("The provided CSV file is empty.")
            sys.exit(1)

        self._validate_domain_project_mapping(df)

        # For each sagemaker AI domain, check whether each user profile maps to a unique Unified Studio user
        # And that atleast one Unified Studio User is marked as PROJECT_OWNER
        for domain_id in df[SAGEMAKER_AI_DOMAIN_ID].unique():
            domain_df = df[df[SAGEMAKER_AI_DOMAIN_ID] == domain_id]
            num_user_profiles = domain_df[SAGEMAKER_AI_USER_PROFILE_NAME].nunique()
            num_user_names = domain_df[SMUS_USER_NAME].nunique()
            if num_user_profiles != num_user_names:
                raise ValueError(
                    f"\nEach user profile in SageMaker AI Domain - {domain_id} must be mapped to a unique Unified Studio user.")
            if 'PROJECT_OWNER' not in domain_df[SMUS_USER_ROLE].values:
                raise ValueError(
                    f"\nAtleast one user in SageMaker AI Domain - {domain_id} must be marked as PROJECT_OWNER")

        # create a dictionary of sagemaker domain with other fields that we should map it to from the file
        self.sagemaker_domain_migration_config = dict()
        for index, row in df.iterrows():
            domain_name = row[SAGEMAKER_AI_DOMAIN_NAME]
            if domain_name not in self.sagemaker_domain_migration_config:
                self.sagemaker_domain_migration_config[domain_name] = {
                    SAGEMAKER_AI_DOMAIN_ID: row[SAGEMAKER_AI_DOMAIN_ID],
                    SMUS_DOMAIN_NAME: row[SMUS_DOMAIN_NAME],
                    SMUS_PROJECT_NAME: row[SMUS_PROJECT_NAME],
                    MIGRATION_STATUS: row[MIGRATION_STATUS],
                    USER_MAPPINGS: []
                }
            user_mapping_info = {
                SAGEMAKER_AI_USER_PROFILE_NAME: row[SAGEMAKER_AI_USER_PROFILE_NAME],
                SMUS_USER_NAME: row[SMUS_USER_NAME],
                SMUS_USER_ROLE: row[SMUS_USER_ROLE]
            }
            self.sagemaker_domain_migration_config[domain_name][USER_MAPPINGS].append(user_mapping_info)
        print("\nValidation Complete! Proceeding with migration")

    def update_original_csv(self, csv_path):
        # Read the original CSV
        df_original = pd.read_csv(csv_path)

        # Update the migration status for each row
        for index, row in df_original.iterrows():
            domain_name = row[SAGEMAKER_AI_DOMAIN_NAME]
            if domain_name in self.sagemaker_domain_migration_config:
                domain_config = self.sagemaker_domain_migration_config[domain_name]
                df_original.at[index, MIGRATION_STATUS] = domain_config[MIGRATION_STATUS]

        # Write back to the same CSV file
        df_original.to_csv(csv_path, index=False)
        print(f"\nMigration status has been updated in: {csv_path}")

    def migrate_guided(self):
        self._validate_file_input()
        if self.sagemaker_domain_migration_config is None:
            print("No SageMaker AI domain to migrate.")
            return
        print_separator()
        self._get_unified_studio_domains()
        for sagemaker_domain_name, domain_config in self.sagemaker_domain_migration_config.items():
            migration_status = domain_config[MIGRATION_STATUS]
            if migration_status == "Pending":
                try:
                    sagemaker_domain_id = domain_config[SAGEMAKER_AI_DOMAIN_ID]
                    datazone_project_name = domain_config[SMUS_PROJECT_NAME]
                    datazone_domain_name = domain_config[SMUS_DOMAIN_NAME]
                    datazone_domain_id = self.datazone_domain_name_id_map[datazone_domain_name]
                    user_mappings = domain_config[USER_MAPPINGS]
                    print(f"\nStarting migration for SageMaker AI domain {sagemaker_domain_name} "
                          f"into Unified Studio domain {datazone_domain_name}...")

                    blueprint_id, blueprint_name, blueprint_description, datazone_project_s3_path = (
                        self._list_and_get_tooling_blueprint_for_datazone_domain(datazone_domain_id))

                    datazone_project_profile_id = self._create_project_profile_for_datazone_domain(datazone_domain_id,
                                                                                                   blueprint_name,
                                                                                                   blueprint_description,
                                                                                                   blueprint_id)
                    # Check if the SM AI domain is assigned to another datazone project if yes, use that project name.
                    use_existing_project_if_exists, existing_datazone_project_name, datazone_project_id = (
                        self._get_datazone_project_from_sagemaker_domain(sagemaker_domain_id))
                    if not use_existing_project_if_exists:
                        datazone_project_id = self._create_datazone_project_for_domain(datazone_domain_id,
                                                                                       datazone_project_name,
                                                                                       datazone_project_profile_id)
                    else:
                        datazone_project_name = existing_datazone_project_name

                    datazone_env_id = self._get_tooling_environment(datazone_domain_id, datazone_project_id)
                    self._update_sagemaker_domain_with_tags(sagemaker_domain_name, sagemaker_domain_id,
                                                            datazone_domain_id,
                                                            datazone_project_id, datazone_env_id,
                                                            datazone_project_s3_path)
                    self._map_users(sagemaker_domain_id, datazone_domain_id, user_mappings, datazone_project_id)
                    self._call_byor(datazone_domain_id, sagemaker_domain_id, datazone_project_id)

                    print_separator()
                    bring_your_own_sagemaker_ai_resources = BringYourOwnSageMakerAIResources(self.region,
                                                                                             self.account_id,
                                                                                             sagemaker_domain_id,
                                                                                             datazone_project_id,
                                                                                             self.iam_profile)
                    bring_your_own_sagemaker_ai_resources.import_sagemaker_ai_resources()
                    # Update status to Successful if everything completes
                    self.sagemaker_domain_migration_config[sagemaker_domain_name][MIGRATION_STATUS] = "Successful"
                    print(f"\nSageMaker AI domain {sagemaker_domain_name} Migration completed successfully!")
                except Exception as e:
                    error_message = (f"Key '{e.args[0]}' was not found. Verify your config file!"
                                     if isinstance(e, KeyError)
                                     else str(e))
                    print(f"\nError occurred during migration of SageMaker AI domain {sagemaker_domain_name}: {error_message}")
                    self.sagemaker_domain_migration_config[sagemaker_domain_name][MIGRATION_STATUS] = "Failed"
            else:
                print(
                    f"\nSkipping migration for SageMaker AI domain {sagemaker_domain_name} as it is in status {migration_status}.")
        # After all domains have been processed, update the CSV
        self.update_original_csv(self.migration_config_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SageMaker Studio Domain Migration Tool")
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

    parser.add_argument(
        "--migration-config-file",
        type=str,
        required=True,
        help="The path of the csv template generated after running Pre-Migration script.",
    )
    args = parser.parse_args()
    region = args.region
    account_id = args.account_id
    iam_profile = args.iam_profile
    migration_config_file = args.migration_config_file

    print_separator()
    migrator = SageMakerAIDomainToUnifiedStudioDomainMigrator(region, account_id, iam_profile,
                                                              migration_config_file)
    migrator.migrate_guided()
    print_separator()
