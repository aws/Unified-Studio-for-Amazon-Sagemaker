import argparse
import time
import boto3
import json
from pprint import pprint

from botocore.exceptions import ClientError
import json

ROLE_REPLACEMENT = 'use-your-own-role'
ROLE_ENHANCEMENT = 'enhance-project-role'

# There should only one Role found per Project
def _find_project_execution_role(args, iam_client, datazone):
    tooling_env_id = datazone.list_environments(
        domainIdentifier=args.domain_id,
        projectIdentifier=args.project_id,
        name="Tooling"
    )['items'][0]['id']
    tooling_env_resources = datazone.get_environment(
        domainIdentifier=args.domain_id,
        identifier=tooling_env_id
    )['provisionedResources']
    try:
        user_role = [resource for resource in tooling_env_resources if resource['name'] == 'userRoleArn'][0]
        role_arn = user_role['value']
    except:
        raise Exception(f"Could not find execution IAM role from Project {args.project_id} tooling environment")
    try:
        return iam_client.get_role(
            RoleName=_get_role_name_from_arn(role_arn),
        )
    except:
        raise Exception(f"Could not find execution IAM role {role_arn} from IAM, please make sure the role exists")


# Find all attached(managed) policies for the project's EMR Instance Role
def _find_emr_instance_role_policies(args, iam_client):
    paginator = iam_client.get_paginator('list_roles')
    instance_role_name = None
    for page in paginator.paginate():
        for role in page['Roles']:
            if f"datazone_emr_ec2_instance_role_{args.project_id}" in role['RoleName']:
                print(f"Found Project's EMR Instance Role: {role['RoleName']}\n")
                instance_role_name = role['RoleName']
    if not instance_role_name:
        return None

    paginator = iam_client.get_paginator('list_attached_role_policies')
    policies_to_update = []
    for page in paginator.paginate(RoleName=instance_role_name):
        for policy in page['AttachedPolicies']:
            policies_to_update.append(policy['PolicyArn'])
    print(f"Found {len(policies_to_update)} policies attached to Project's EMR Instance Role\n")
    return policies_to_update

def _get_role_name_from_arn(role_arn):
    return role_arn.split('/')[-1]

# Combine trust policy statements and dedup on statement level
def _combine_trust_policy(trust_policy_1, trust_policy_2):
    combined_trust_policy = trust_policy_1.copy()
    for new_statement in trust_policy_2['Statement']:
        if not any(_statements_equal(new_statement, existing_statement) 
                   for existing_statement in combined_trust_policy['Statement']):
            combined_trust_policy['Statement'].append(new_statement)
    return combined_trust_policy

def _statements_equal(statement1, statement2):
    # Helper function to sort nested structures in trust policy
    def sort_nested(item):
        if isinstance(item, dict):
            return {k: sort_nested(v) for k, v in sorted(item.items())}
        elif isinstance(item, list):
            return sorted(sort_nested(i) for i in item)
        else:
            return item

    # Sort all nested structures
    sorted_statement1 = sort_nested(statement1)
    sorted_statement2 = sort_nested(statement2)
    return json.dumps(sorted_statement1, sort_keys=True) == json.dumps(sorted_statement2, sort_keys=True)


def _update_trust_policy(role_name, new_trust_policy, iam_client, execute_flag):
    if execute_flag:
        print(f"Updating trust policy for role: {role_name}")
        iam_client.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=str(new_trust_policy).replace("'", '"')
        )
        print(f"Trust policy updated successfully for role: `{role_name}`\n")
    else:
        print(f"New trust policy for role `{role_name}` would be:")
        pprint(new_trust_policy)
        print(f"Trust policy update skipped for role: `{role_name}`, set --execute flag to True to do the actual update.\n")

def _replace_role_arn_in_policies(policies_to_update, iam_client, old_role_arn, new_role_arn, execute_flag):
    for policy_arn in policies_to_update:
        policy = iam_client.get_policy(PolicyArn=policy_arn)['Policy']
        policy_document = iam_client.get_policy_version(
            PolicyArn=policy_arn,
            VersionId=policy['DefaultVersionId']
        )['PolicyVersion']['Document']
        # Replace the role ARN if source_role is present in customer managed policy
        policy_str = json.dumps(policy_document)
        if old_role_arn in policy_str:
            update_policy_str = policy_str.replace(old_role_arn, new_role_arn)
            print(f"Updated policy doc for {policy['PolicyName']}: {update_policy_str}\n")
            if execute_flag:
                iam_client.create_policy_version(
                    PolicyArn=policy_arn,
                    PolicyDocument=update_policy_str,
                    SetAsDefault=True
                )
                print(f"Successfully updated policy {policy['PolicyName']} with new version after replacing execution role content.")
            else:
                print(f"Policy {policy['PolicyName']} update skipped, set --execute flag to True to do the actual update.\n")

# Customer managed Policy may contain project user role's Arn, we need to update policy content with BYOR role when necessary
# We will do the change for both
#   case 1: Role Replacement
#   case 2: Role Enhancement
# so basically just check all source role's managed policies, and update any source role arn string to dest role arn
def _copy_managed_policies_arn(source_role, dest_role, iam_client, execute_flag):
    paginator = iam_client.get_paginator('list_attached_role_policies')
    policies_to_attach = []
    for page in paginator.paginate(RoleName=source_role['Role']['RoleName']):
        for policy in page['AttachedPolicies']:
            policies_to_attach.append(policy['PolicyArn'])
    
    _replace_role_arn_in_policies(policies_to_attach, iam_client, source_role['Role']['Arn'], dest_role['Role']['Arn'], execute_flag)

    if execute_flag:
        for policy_arn in policies_to_attach:
            iam_client.attach_role_policy(
                RoleName=dest_role['Role']['RoleName'],
                PolicyArn=policy_arn
            )
        print(f"Managed policies attached successfully to role: `{dest_role['Role']['RoleName']}`\n")
    else:
        print(f"Managed policies to attach to role `{dest_role['Role']['RoleName']}` would be:")
        pprint(policies_to_attach)
        print(f"Managed policies attach skipped for role: `{dest_role['Role']['RoleName']}`, set --execute flag to True to do the actual update.\n")

def _copy_inline_policies_arn(source_role, dest_role, iam_client, execute_flag):
    paginator = iam_client.get_paginator('list_role_policies')
    for page in paginator.paginate(RoleName=source_role['Role']['RoleName']):
        for policy_name in page['PolicyNames']:
            policy_document = iam_client.get_role_policy(
                RoleName=source_role['Role']['RoleName'],
                PolicyName=policy_name
            )['PolicyDocument']
            if execute_flag:
                iam_client.put_role_policy(
                    RoleName=dest_role['Role']['RoleName'],
                    PolicyName=policy_name,
                    PolicyDocument=str(policy_document).replace("'", '"')
                )
            else:
                print(f"New inline policy `{policy_name}` would be copied to role `{dest_role['Role']['RoleName']}` is:")
                pprint(policy_document)
                print(f"Skipping copy new inline policy `{policy_name}` to role `{dest_role['Role']['RoleName']}`, set --execute flag to True to do the actual copy.\n")
    if execute_flag:
        print(f"Successfully copied inline policies to role: `{dest_role['Role']['RoleName']}`\n")
 
def _copy_tags(source_role_name, dest_role_name, iam_client, execute_flag):
    paginator = iam_client.get_paginator('list_role_tags')
    tags_to_copy = []
    for page in paginator.paginate(RoleName=source_role_name):
        for tag in page['Tags']:
            if tag['Key'] == 'RoleName' and tag['Value'] == source_role_name:
                tag['Value'] = dest_role_name
                print(f"Update IAM Role's tag {tag['Key']} value from {source_role_name} to {dest_role_name}\n")
            tags_to_copy.append(tag)
    if tags_to_copy and execute_flag:
        iam_client.tag_role(
            RoleName=dest_role_name,
            Tags=tags_to_copy
        )
        print(f"Tags copied successfully to role: `{dest_role_name}`\n")
    else:
        print(f"Tags to copy to role `{dest_role_name}` would be:")
        pprint(tags_to_copy)
        print(f"Tags copy skipped for role: `{dest_role_name}`, set --execute flag to True to do the actual update.\n")

class EnvironmentWithRole:
    def __init__(self, name, id, user_role_arn):
        self.name = name
        self.id = id
        self.user_role_arn = user_role_arn

# Get environment name, id and its userRoleArn
def _get_enviroments_with_role_from_project(datazone, args, fallback_role_arn):
    environment_lists = []
    paginator = datazone.get_paginator('list_environments')
    for page in paginator.paginate(domainIdentifier=args.domain_id, projectIdentifier=args.project_id):
        for environment in page['items']:
            provisioned_resources = datazone.get_environment(
                domainIdentifier=args.domain_id,
                identifier=environment['id']
            )['provisionedResources']
            try:
                user_role = [resource for resource in provisioned_resources if resource['name'] == 'userRoleArn'][0]
                role_arn = user_role['value']
            except (IndexError, KeyError):
                # Use fallback role if userRoleArn is not found
                role_arn = fallback_role_arn
            environment_lists.append(EnvironmentWithRole(environment['name'], environment['id'], role_arn))
    return environment_lists
                
def wait_for_subscription_grant_deletion(datazone, domain_id, grant_id, max_attempts=30, delay_seconds=5):
    """
    Wait for subscription grant deletion to complete
    
    Args:
        datazone: DataZone client
        domain_id: Domain identifier
        grant_id: Subscription grant identifier
        max_attempts: Maximum number of polling attempts
        delay_seconds: Delay between polling attempts in seconds
    
    Returns:
        True if deletion is successful, False otherwise
    """
    for attempt in range(max_attempts):
        try:
            response = datazone.get_subscription_grant(
                domainIdentifier=domain_id,
                identifier=grant_id
            )
            
            status = response.get('status')
            if status == 'COMPLETED':
                print(f"Deleted subscription grant `{grant_id}` successfully")
                return True
            elif status in ['REVOKE_FAILED', 'GRANT_AND_REVOKE_FAILED']:
                print(f"Deletion failed with status: {status}")
                return False
                
            print(f"Deletion of subscription grant: `{grant_id}` in progress. Current status: {status}. Attempt {attempt + 1}/{max_attempts}")
            time.sleep(delay_seconds)
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"Subscription grant {grant_id} no longer exists")
                return True
            raise
    
    raise TimeoutError(f"Deletion of subscription grant: `{grant_id}` did not complete after {max_attempts} attempts")

def _copy_datazone_subscriptions(domain_id, environment_id, datazone, byor_role, execute_flag):
    """
    Copy Subscription Targets and Subscription Grants to the new BYOR Role
    
    Steps:
        1. List all subscription targets for the environment
        2. For each subscription target, list all subscription grants
        3. Delete each subscription grant
        4. Update the subscription target with the BYOR Role as the authorized principal
        5. Create new subscription grants for the new subscription target
    """
    print(f"Checking and copying subscription targets and grants for environment `{environment_id}`...\n")
    sub_target_paginator = datazone.get_paginator('list_subscription_targets')
    for sub_target_page in sub_target_paginator.paginate(domainIdentifier=domain_id, environmentIdentifier=environment_id):
        for subscription_target in sub_target_page['items']:
            target_id = subscription_target['id']
            print(f"Checking and copying subscription grants for subscription target `{target_id}`...\n")
            sub_grants_list = []
            sub_grant_paginator = datazone.get_paginator('list_subscription_grants')
            for sub_grant_page in sub_grant_paginator.paginate(domainIdentifier=domain_id, subscriptionTargetId=target_id):
                for subscription_grant in sub_grant_page['items']:
                    sub_grants_list.append(subscription_grant)
            print(f"List all Subscription grants for subscription target `{target_id}`:")
            pprint(sub_grants_list)

            # Delete all subscription grants
            for sub_grant in sub_grants_list:
                if execute_flag:
                    print(f"Calling delete subscription grant {sub_grant['id']} API... \n")
                    datazone.delete_subscription_grant(
                        domainIdentifier=domain_id,
                        identifier=sub_grant['id']
                    )
                    wait_for_subscription_grant_deletion(
                        datazone=datazone,
                        domain_id=domain_id,
                        grant_id=sub_grant['id']
                    )
                    print(f"Deleted subscription grant {sub_grant['id']} successfully \n")

            # Update subscription target with the BYOR Role
            if execute_flag:
                # In rare case after deleting all subscription grants, we still get rejected to update subscription target.
                # Add wait time bellow for safe.
                time.sleep(10)
                datazone.update_subscription_target(
                    domainIdentifier=domain_id,
                    environmentIdentifier=environment_id,
                    identifier=subscription_target['id'],
                    authorizedPrincipals=[byor_role['Role']['Arn']]
                )
            
                # Create all subscription grants which were deleted earlier
                for sub_grant in sub_grants_list:
                    create_response = datazone.create_subscription_grant(
                        domainIdentifier=domain_id,
                        environmentIdentifier=environment_id,
                        subscriptionTargetIdentifier=target_id,
                        grantedEntity={
                            'listing': {
                                'identifier': sub_grant['grantedEntity']['listing']['id'],
                                'revision': sub_grant['grantedEntity']['listing']['revision'],
                            }
                        }
                    )
                    print(f"Created new subscription grants successfully: {create_response} \n")

# LakeFormation Resource list got from list_permissions and list_lake_formation_opt_ins APIs may not be usable for create/grant API directly,
# this method does some filter/refactor work to make it work properly.
def _filter_lakeformationsource(resource):
    if resource.get('Table') and resource['Table'].get('Name') is not None and resource['Table'].get('TableWildcard') is not None:
        resource['Table'].pop('Name')
    if resource.get('TableWithColumns') and resource['TableWithColumns'].get('Name') and resource['TableWithColumns']['Name'] == "ALL_TABLES":
        resource['Table'] = resource['TableWithColumns']
        resource['Table']['TableWildcard'] = {}
        resource['Table'].pop('Name')
        resource['Table'].pop('ColumnWildcard')
        resource.pop('TableWithColumns')
    return resource

def _copy_lakeformation_grants(lakeformation, source_role_arn, destination_role_arn, execute_flag, script_option):
    print(f"Checking and copying lakeformation grants associated with role `{source_role_arn}` to role `{destination_role_arn}`...\n")
    grants_list_to_copy = []
    response = lakeformation.list_permissions()
    for grant in response['PrincipalResourcePermissions']:
        if grant['Principal']['DataLakePrincipalIdentifier'] == source_role_arn:
            grants_list_to_copy.append(grant)
    while response.get('NextToken'):
        response = lakeformation.list_permissions(NextToken=response['NextToken'])
        for grant in response['PrincipalResourcePermissions']:
            if grant['Principal']['DataLakePrincipalIdentifier'] == source_role_arn:
                grants_list_to_copy.append(grant)
    if not grants_list_to_copy:
        if script_option == ROLE_REPLACEMENT:
            # Auto generated Project role has grants associated with it in some project profiles but not all, log out warn message
            print(f"WARN: No grants found associated with role {source_role_arn}, skipping copy... Please make sure you added script executor as LakeFormation Data lake administrators properly.\n")

    for grant_to_copy in grants_list_to_copy:
        print(f"Copying LakeFormation Grant:")
        pprint(grant_to_copy)
        print(f"to new role: {destination_role_arn}...\n")
        if execute_flag:
            lakeformation.grant_permissions(
                Principal={
                    'DataLakePrincipalIdentifier': destination_role_arn
                },
                Resource=_filter_lakeformationsource(grant_to_copy['Resource']),
                Permissions=grant_to_copy['Permissions'],
                PermissionsWithGrantOption=grant_to_copy['PermissionsWithGrantOption']
            )
            print(f"Successfully copy LakeFormation Grant:")
            pprint(grant_to_copy)
            print(f"to new role: {destination_role_arn} \n")
        else:
            print(f"Skipping copy LakeFormation Grant:")
            pprint(grant_to_copy)
            print(f"to new role: {destination_role_arn}, set --execute flag to True to do the actual update.\n")

def _copy_lakeformation_opt_ins(lakeformation, source_role_arn, destination_role_arn, execute_flag):
    print(f"Checking and copying lakeformation opt ins associated with role `{source_role_arn}` to role `{destination_role_arn}`...\n")
    opt_in_list_to_copy = []
    response = lakeformation.list_lake_formation_opt_ins(
        Principal={
            'DataLakePrincipalIdentifier': source_role_arn
        }
    )
    for opt_in in response['LakeFormationOptInsInfoList']:
        opt_in_list_to_copy.append(opt_in)
    while response.get('NextToken'):
        response = lakeformation.list_lake_formation_opt_ins(NextToken=response['NextToken'])
        for opt_in in response['LakeFormationOptInsInfoList']:
            opt_in_list_to_copy.append(opt_in)

    for opt_in_to_copy in opt_in_list_to_copy:
        print(f"Copying LakeFormation Opt In:")
        pprint(opt_in_to_copy)
        print(f"to new role: {destination_role_arn}...\n")
        if execute_flag:
            try:
                lakeformation.create_lake_formation_opt_in(
                    Principal={
                        'DataLakePrincipalIdentifier': destination_role_arn
                    },
                    Resource=_filter_lakeformationsource(opt_in_to_copy['Resource']),
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidInputException':
                    print(f"Opt-in already exists, skipping...\n")
                else:
                    raise e
            print(f"Successfully copy LakeFormation Opt In:")
            pprint(opt_in_to_copy)
            print(f"to new role: {destination_role_arn} \n")
        else:
            print(f"Skipping copy LakeFormation Opt In:")
            pprint(opt_in_to_copy)
            print(f"to new role: {destination_role_arn}, set --execute flag to True to do the actual update.\n")

def _find_sagemaker_domain_id(sagemaker_client, args):
    project_id = args.project_id
    paginator = sagemaker_client.get_paginator('list_domains')
    for page in paginator.paginate():
        for domain in page['Domains']:
            if f"SageMakerUnifiedStudio-{project_id}" in domain['DomainName']:
                print(f"Found Project's SageMaker Domain, name: {domain['DomainName']}, id: {domain['DomainId']}\n")
                return domain['DomainId']

def _wait_for_sagemaker_app_deletion(sagemaker,
                                    domain_id,
                                    app_name,
                                    app_type,
                                    user_profile_name=None,
                                    space_name=None,
                                    max_attempts=30,
                                    delay_seconds=5):
    """
    Wait for SageMaker App to be deleted
    """
    for attempt in range(max_attempts):
        try:
            if user_profile_name:
                response = sagemaker.describe_app(
                    DomainId=domain_id,
                    AppType=app_type,
                    AppName=app_name,
                    UserProfileName=user_profile_name
                )
            elif space_name:
                response = sagemaker.describe_app(
                    DomainId=domain_id,
                    AppType=app_type,
                    AppName=app_name,
                    SpaceName=space_name
                )
            else:
                raise ValueError("Either UserProfileName or SpaceName must be passed for DescribeApp operation.")
            
            status = response.get('Status')
            if status == 'Deleted':
                print(f"Deleted SageMaker App `{app_name}` deleted successfully")
                return
            print(f"Deletion of SageMaker App `{app_name}` in progress. Current status: {status}. Attempt {attempt + 1}/{max_attempts}")
            time.sleep(delay_seconds)
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"Deleted SageMaker App `{app_name}` deleted successfully")
                return
            raise e
    
    raise TimeoutError(f"Deletion of SageMaker App `{app_name}` did not complete after {max_attempts} attempts")

def _stop_apps_under_domain(sagemaker_client, sagemaker_domain_id, execute_flag):
    paginator = sagemaker_client.get_paginator('list_apps')
    for page in paginator.paginate(DomainIdEquals=sagemaker_domain_id):
        for app in page['Apps']:
            print(f"Found app {app['AppName']} under Project's SageMaker Domain id: {sagemaker_domain_id}\n")
            if execute_flag:
                try:
                    if app.get('UserProfileName'):
                        sagemaker_client.delete_app(
                            DomainId=sagemaker_domain_id,
                            AppType=app['AppType'],
                            AppName=app['AppName'],
                            UserProfileName=app['UserProfileName']
                        )
                        _wait_for_sagemaker_app_deletion(sagemaker_client, sagemaker_domain_id, app['AppName'], app['AppType'], app['UserProfileName'], None)
                    elif app.get('SpaceName'):
                        sagemaker_client.delete_app(
                            DomainId=sagemaker_domain_id,
                            AppType=app['AppType'],
                            AppName=app['AppName'],
                            SpaceName=app['SpaceName']
                        )
                        _wait_for_sagemaker_app_deletion(sagemaker_client, sagemaker_domain_id, app['AppName'], app['AppType'], None, app['SpaceName'])
                    print(f"Stopped app {app['AppName']} successfully\n")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ValidationException':
                        print(f"App {app['AppName']} already deleted, skipping...\n")
                    else:
                        raise e
            else:
                print(f"Skipping stop app {app['AppName']}, set --execute flag to True to do the actual update")

def _update_domain_execution_role(sagemaker, domain_id, bring_in_role_arn, execute_flag):
    print(f"Updating Project's SageMaker Domain id: {domain_id} execution role to {bring_in_role_arn}...\n")
    if execute_flag:
        sagemaker.update_domain(
            DomainId=domain_id,
            DefaultUserSettings={
                'ExecutionRole': bring_in_role_arn
            },
            DefaultSpaceSettings={
                'ExecutionRole': bring_in_role_arn
            }
        )
        print(f"Updated Project's SageMaker Domain id: {domain_id} default execution role to {bring_in_role_arn} successfully\n")
    else:
        print(f"Skipping update Project's SageMaker Domain id: {domain_id} default execution role, set --execute flag to True to do the actual update\n")

def _update_s3_lakeformation_registration(lakeformation, old_role_arn, new_role_arn, execute_flag):
    print(f"Updating lakeformation resource registered with role: `{old_role_arn}` to role `{new_role_arn}`...\n")
    resources_list = []
    response = lakeformation.list_resources(
        FilterConditionList=[
            {
                'Field': 'ROLE_ARN',
                'ComparisonOperator': 'EQ',
                'StringValueList': [
                    old_role_arn,
                ]
            },
        ]
    )
    for resource in response['ResourceInfoList']:
        resources_list.append(resource)
    while response.get('NextToken'):
        response = lakeformation.list_resources(
            FilterConditionList=[
                {
                    'Field': 'ROLE_ARN',
                    'ComparisonOperator': 'EQ',
                    'StringValueList': [
                        old_role_arn,
                    ]
                },
            ]
        )
        for resource in response['ResourceInfoList']:
            resources_list.append(resource)
    for resource in resources_list:
        if execute_flag:
            lakeformation.update_resource(
                RoleArn=new_role_arn,
                ResourceArn=resource['ResourceArn']
            )
            print(f"Successfully updated LakeFormation Resource: `{resource['ResourceArn']}` by updating RoleArn to `{new_role_arn}` successfully\n")
        else:
            print(f"Skipping updating LakeFormation Resource: `{resource['ResourceArn']}` by updating RoleArn to `{new_role_arn}`, set --execute flag to True to do the actual update.\n")

def _ensure_list(value):
    return [value] if not isinstance(value, list) else value

def _update_smus_provisioning_role(datazone_client, iam_client, domain_id, byor_role_arn, execute_flag):
    # Find Provisioning Role of current SMUS Domain
    tooling_blueprint = datazone_client.list_environment_blueprints(
        domainIdentifier=domain_id,
        managed=True,
        name="Tooling"
    )['items'][0]
    tooling_blueprint_config = datazone_client.get_environment_blueprint_configuration(
        domainIdentifier=domain_id,
        environmentBlueprintIdentifier=tooling_blueprint['id']
    )
    provisioning_role_name = tooling_blueprint_config['provisioningRoleArn'].split('/')[2]
    print(f"Updating SageMaker Unified Studio Provisioning Role \"{provisioning_role_name}\" to have necessary permissions to {byor_role_arn}...\n")
    # Get AWS managed policy "SageMakerStudioProjectProvisioningRolePolicy"
    managed_policies = iam_client.list_attached_role_policies(
        RoleName=provisioning_role_name
    )
    new_policy_statements_to_append = []
    # Traverse all statements in SMUS Provisioning Role's AWS managed policies
    for managed_policy in managed_policies['AttachedPolicies']:
        if managed_policy['PolicyArn'].startswith('arn:aws:iam::aws:policy/'):
            policy = iam_client.get_policy(PolicyArn=managed_policy['PolicyArn'])
            policy_version = iam_client.get_policy_version(
                PolicyArn=policy['Policy']['Arn'],
                VersionId=policy['Policy']['DefaultVersionId']
            )
            for statement in policy_version['PolicyVersion']['Document']['Statement']:
                if 'Resource' in statement:
                    resources = statement['Resource'] if isinstance(statement['Resource'], list) else [statement['Resource']]
                    # Copy policy statement granting permission to datazone_usr_role_*
                    if any('arn:aws:iam::*:role/datazone_usr_role_*' in resource for resource in resources):
                        new_policy_statements_to_append.append(statement)
    # Define the policy document, replace resource to "byor_role_arn"
    for statement_to_append in new_policy_statements_to_append:
        statement_to_append['Resource'] = [byor_role_arn]
    try:
        # Get existing inline policy and combine it with "policy_statements_to_copy"
        current_inline_policy = iam_client.get_role_policy(
            RoleName=provisioning_role_name,
            PolicyName='byoInlinePolicy'
        )
        # Get the existing policy document
        current_inline_policy_doc = current_inline_policy['PolicyDocument']
        current_inline_policy_doc['Statement'] = _ensure_list(current_inline_policy_doc['Statement'])
        new_policy_statements_to_append_sids = {item['Sid']: item for item in new_policy_statements_to_append}
        for statement in current_inline_policy_doc['Statement']:
            sid = statement['Sid']
            if sid in new_policy_statements_to_append_sids:
                resources1 = set(new_policy_statements_to_append_sids[sid]['Resource'])
                resources2 = set(statement['Resource'])
                new_policy_statements_to_append_sids[sid]['Resource'] = list(resources1.union(resources2))
            else:
                new_policy_statements_to_append_sids[sid] = statement
        new_policy_statements_to_append = list(new_policy_statements_to_append_sids.values())
        new_policy_document = {
            "Version": "2012-10-17",
            "Statement": new_policy_statements_to_append
        }
        # Policy exists, update it
        if execute_flag:
            iam_client.put_role_policy(
                RoleName=provisioning_role_name,
                PolicyName='byoInlinePolicy',
                PolicyDocument=json.dumps(new_policy_document)
            )
            print(f"Updated existing inline policy 'byoInlinePolicy' for role {provisioning_role_name}, new policy:\n")
            pprint(new_policy_statements_to_append)

    except iam_client.exceptions.NoSuchEntityException:
        # Policy doesn't exist, create new one
        new_policy_document = {
            "Version": "2012-10-17",
            "Statement": new_policy_statements_to_append
        }
        if execute_flag:
            iam_client.put_role_policy(
                RoleName=provisioning_role_name,
                PolicyName='byoInlinePolicy',
                PolicyDocument=json.dumps(new_policy_document)
            )
            print(f"Created new inline policy 'byoInlinePolicy' for role {provisioning_role_name}, new policy:\n")
            pprint(new_policy_document)

    if not execute_flag:
        print(f"Skipping update/create inline policy 'byoInlinePolicy' for role {provisioning_role_name}, set --execute flag to True to do the actual update.\n")

def _add_common_arguments(parser):
    parser.add_argument('--domain-id',
                    help='Your Project\'s Domain Id', 
                    required=True)
    parser.add_argument('--project-id',
                        help='Project ID you want to update',
                        required=True)
    parser.add_argument('--bring-in-role-arn',
                        help='Arn of IAM Role you want to update or use as reference',
                        required=True)
    parser.add_argument('--execute',
                        help='Determine if the script should generate overview or do the actual work',
                        action='store_true',
                        default=False)
    parser.add_argument('--region',
                        help='The AWS region. If not specified, the default region from your AWS credentials will be used',
                        required=False)
    parser.add_argument('--endpoint',
                        help='Endpoint where you have your Project',
                        required=False)

def _parse_args():
    parser = argparse.ArgumentParser(description='Tool which grant your role ability to work for specified Project.')
    subparsers = parser.add_subparsers(dest='command', help='The action you want to take.')

    # Parser for use-your-own-role command
    parser_use_own_role = subparsers.add_parser(ROLE_REPLACEMENT, help='Enhance your own role to use.')
    parser_use_own_role.add_argument('--force-update',
                        help='WARNING: Setting this flag to True allows the script to stop existing resources. Only use if you explicitly accept compute resources stopping.',
                        action='store_true',
                        default=False)
    _add_common_arguments(parser_use_own_role)
        
    # Parser for enhance-project-role command
    parser_enhance = subparsers.add_parser(ROLE_ENHANCEMENT, help='Enhance existing Project Role.')
    _add_common_arguments(parser_enhance)

    return parser.parse_args()

def byor_main():
    args = _parse_args()
    session = boto3.Session()
    if (args.region):
        session = boto3.Session(region_name=args.region)
    iam_client = session.client('iam')
    datazone = session.client('datazone')
    lakeformation = session.client('lakeformation')
    sagemaker = session.client('sagemaker')
    if args.endpoint:
        datazone = session.client('datazone', endpoint_url=args.endpoint)
        
    if args.command == ROLE_REPLACEMENT:
        print(f"Use bring in Role: {args.bring_in_role_arn} as Project Role...")
        # Get Project's Auto Generated Execution Role, there should be one role per project
        project_role = _find_project_execution_role(args, iam_client, datazone)
        # Get Execution Role's trust policy
        project_role_trust_policy = project_role['Role']['AssumeRolePolicyDocument']
        byor_role = iam_client.get_role(
            RoleName=_get_role_name_from_arn(args.bring_in_role_arn),
        )

        environment_with_role_lists = _get_enviroments_with_role_from_project(datazone, args, project_role['Role']['Arn'])
        # Replace Project Execution Role with BYOR Role
        # Role is attached with environment, and one Project contains multiple environments, so 
        # we need to replace role for each environment within a project
        for environment in environment_with_role_lists:
            print(f"Will replace IAM role {environment.user_role_arn} attached to environment name: {environment.name}, id: {environment.id} with new role {args.bring_in_role_arn}...\n")
            if args.execute:
                try:
                    print(f"Disassociate role {environment.user_role_arn} from environment {environment.id} in progress... \n")
                    response = datazone.disassociate_environment_role(
                        domainIdentifier=args.domain_id,
                        environmentIdentifier=environment.id,
                        environmentRoleArn=environment.user_role_arn
                    )
                    print(f"Successfully disassociate role {environment.user_role_arn} from environment {environment.id}: {response} \n")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        print(f"Disassociate role {environment.user_role_arn} from environment {environment.id} failed: Role not found in environment, skip disassociate. \n")
                    else:
                        raise e
                print(f"Associate role {args.bring_in_role_arn} to environment {environment.id} in progress... \n")
                try:
                    response = datazone.associate_environment_role(
                        domainIdentifier=args.domain_id,
                        environmentIdentifier=environment.id,
                        environmentRoleArn=args.bring_in_role_arn
                    )
                    print(f"Associate role {args.bring_in_role_arn} to environment {environment.id} successfully: {response} \n")
                except Exception as e:
                    # Associate environment role failed, re-associate with original role
                    print(f"Associate role {args.bring_in_role_arn} to environment {environment.id} failed: {e}, re-associate with original role {environment.user_role_arn}. But all subscriptions are lost, please recreate necessary subscriptions.\n")
                    response = datazone.associate_environment_role(
                        domainIdentifier=args.domain_id,
                        environmentIdentifier=environment.id,
                        environmentRoleArn=environment.user_role_arn
                    )
                    raise e
            else:
                print(f"Skipping disassociate and associate role operations, set --execute flag to True to do the actual update. environment {environment.name} still use {environment.user_role_arn} as its role.\n")
            # Copy DataZone Subscriptions
            if not environment.name == 'RedshiftServerless' and not environment.name == 'Redshift Serverless':
                _copy_datazone_subscriptions(args.domain_id, environment.id, datazone, byor_role, args.execute)
            # Copy LakeFormation Permissions and Opt-Ins
            _copy_lakeformation_grants(lakeformation, environment.user_role_arn, args.bring_in_role_arn, args.execute, args.command)
            _copy_lakeformation_opt_ins(lakeformation, environment.user_role_arn, args.bring_in_role_arn, args.execute)

        # Get BYOR Role's trust policy
        byor_role_trust_policy = byor_role['Role']['AssumeRolePolicyDocument']

        # Combine trust policy and update BYOR Role's trust policy
        new_trust_policy = _combine_trust_policy(project_role_trust_policy, byor_role_trust_policy)
        _update_trust_policy(byor_role['Role']['RoleName'], new_trust_policy, iam_client, args.execute)

        # Copy Project Execution Role's managed policies to BYOR Role
        _copy_managed_policies_arn(project_role, byor_role, iam_client, args.execute)

        # Copy Project Execution Role's inline policies to BYOR Role
        _copy_inline_policies_arn(project_role, byor_role, iam_client, args.execute)

        # Copy Project Execution Role's Tags to BYOR Role
        _copy_tags(project_role['Role']['RoleName'], byor_role['Role']['RoleName'], iam_client, args.execute)
        
        # Update associated EMR Instance Role's policies
        emr_instance_role_policies = _find_emr_instance_role_policies(args, iam_client)
        if emr_instance_role_policies is not None:
            _replace_role_arn_in_policies(emr_instance_role_policies,
                                        iam_client,
                                        project_role['Role']['Arn'],
                                        args.bring_in_role_arn,
                                        args.execute)
        
        # Replace SageMaker Domain Execution Role
        sagemaker_domain_id = _find_sagemaker_domain_id(sagemaker, args)
        if sagemaker_domain_id:
            if args.force_update:
                _stop_apps_under_domain(sagemaker, sagemaker_domain_id, args.execute)
            else:
                raise Exception(f"Updating SageMaker Domain without deleting running apps is failing this script execution. Set --force-update flag if you accept app deletion to ensure successful script execution.")
            _update_domain_execution_role(sagemaker, sagemaker_domain_id, args.bring_in_role_arn, args.execute)

        # Update LakeFormation Data lake locations resources with the new Role
        _update_s3_lakeformation_registration(lakeformation, project_role['Role']['Arn'], args.bring_in_role_arn, args.execute)
        # Create or update SMUS Provisioning Role's inline policy
        _update_smus_provisioning_role(datazone, iam_client, args.domain_id, args.bring_in_role_arn, args.execute)
                
        if args.execute:
            print(f"Successfully replace Project {args.project_id} user role with your own role: {byor_role['Role']['Arn']}")
    elif args.command == ROLE_ENHANCEMENT:
        print(f"Enhance Project Role...")
        # Get Project's Auto Generated Role
        project_role = _find_project_execution_role(args, iam_client, datazone)
        # Get Project Role's trust policy
        project_role_trust_policy = project_role['Role']['AssumeRolePolicyDocument']

        # Get BYOR Role's trust policy
        byor_role = iam_client.get_role(
            RoleName=_get_role_name_from_arn(args.bring_in_role_arn),
        )
        print(f"BYOR Role ARN: {args.bring_in_role_arn}\n")
        byor_role_trust_policy = byor_role['Role']['AssumeRolePolicyDocument']

        # Combine trust policy and update Project Role's trust policy
        new_trust_policy = _combine_trust_policy(project_role_trust_policy, byor_role_trust_policy)
        _update_trust_policy(project_role['Role']['RoleName'], new_trust_policy, iam_client, args.execute)

        # Copy BYOR Role's managed policies to Project Role
        _copy_managed_policies_arn(byor_role, project_role, iam_client, args.execute)

        # Copy BYOR Role's inline policies to Project Role
        _copy_inline_policies_arn(byor_role, project_role, iam_client, args.execute)

        # Copy BYOR Role's Tags to Project Role
        _copy_tags(byor_role['Role']['RoleName'], project_role['Role']['RoleName'], iam_client, args.execute)
        
        # Copy LakeFormation Permissions and Opt-Ins
        _copy_lakeformation_grants(lakeformation, args.bring_in_role_arn, project_role['Role']['Arn'], args.execute, args.command)
        _copy_lakeformation_opt_ins(lakeformation, args.bring_in_role_arn, project_role['Role']['Arn'], args.execute)
        if args.execute:
            print(f"Successfully enhance project user role: {project_role['Role']['Arn']} referring to your own role: {byor_role['Role']['Arn']}")
    else:
        print(f"Invalid command. Expecting '{ROLE_REPLACEMENT}' or '{ROLE_ENHANCEMENT}'.")

if __name__ == "__main__":
    byor_main()
