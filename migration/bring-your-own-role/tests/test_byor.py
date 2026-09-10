import importlib.util
import sys
import types
import unittest
from pathlib import Path


if 'boto3' not in sys.modules:
    boto3 = types.ModuleType('boto3')
    boto3.Session = object
    sys.modules['boto3'] = boto3

if 'botocore.exceptions' not in sys.modules:
    botocore = types.ModuleType('botocore')
    exceptions = types.ModuleType('botocore.exceptions')

    class ClientError(Exception):
        pass

    exceptions.ClientError = ClientError
    botocore.exceptions = exceptions
    sys.modules['botocore'] = botocore
    sys.modules['botocore.exceptions'] = exceptions


MODULE_PATH = Path(__file__).resolve().parents[1] / 'byor.py'
SPEC = importlib.util.spec_from_file_location('byor', MODULE_PATH)
byor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(byor)


class StaticPaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **kwargs):
        return iter(self.pages)


class ManagedPolicyIam:
    def __init__(self):
        self.attach_called = False

    def get_paginator(self, name):
        if name != 'list_attached_role_policies':
            raise AssertionError(name)
        return StaticPaginator([
            {'AttachedPolicies': [{'PolicyArn': 'arn:aws:iam::123:policy/required'}]}
        ])

    def get_policy(self, PolicyArn):
        return {'Policy': {'PolicyName': 'required', 'DefaultVersionId': 'v1'}}

    def get_policy_version(self, PolicyArn, VersionId):
        return {
            'PolicyVersion': {
                'Document': {
                    'Version': '2012-10-17',
                    'Statement': [{'Effect': 'Allow', 'Action': 's3:GetObject', 'Resource': '*'}]
                }
            }
        }

    def attach_role_policy(self, **kwargs):
        self.attach_called = True


class InlinePolicyIam:
    def __init__(self):
        self.put_called = False

    def get_paginator(self, name):
        if name != 'list_role_policies':
            raise AssertionError(name)
        return StaticPaginator([{'PolicyNames': ['project-access']}])

    def get_role_policy(self, RoleName, PolicyName):
        return {
            'PolicyDocument': {
                'Version': '2012-10-17',
                'Statement': [{'Effect': 'Allow', 'Action': 's3:GetObject', 'Resource': '*'}]
            }
        }

    def put_role_policy(self, **kwargs):
        self.put_called = True


class DataZoneProfiles:
    def __init__(self):
        self.members = {'old-group'}
        self.created_profiles = False
        self.created_members = []
        self.deleted_members = []

    def search_group_profiles(self, searchText, **kwargs):
        profiles = {
            'arn:aws:iam::123:role/preprovisioned': {
                'id': 'new-group',
                'status': 'ASSIGNED',
                'rolePrincipalArn': searchText
            },
            'arn:aws:iam::123:role/generated': {
                'id': 'old-group',
                'status': 'ASSIGNED',
                'rolePrincipalArn': searchText
            }
        }
        return {'items': [profiles[searchText]] if searchText in profiles else []}

    def search_user_profiles(self, **kwargs):
        return {'items': []}

    def list_project_memberships(self, **kwargs):
        return {
            'members': [
                {
                    'designation': 'PROJECT_CONTRIBUTOR',
                    'memberDetails': {'group': {'groupId': group_id}}
                }
                for group_id in sorted(self.members)
            ]
        }

    def create_user_profile(self, **kwargs):
        self.created_profiles = True
        raise AssertionError('CreateUserProfile must not be called in preprovisioned mode')

    def create_project_membership(self, member, **kwargs):
        self.created_members.append(member)
        self.members.add(member['groupIdentifier'])

    def delete_project_membership(self, member, **kwargs):
        self.deleted_members.append(member)
        self.members.remove(member['groupIdentifier'])


class PreprovisionedRoleTests(unittest.TestCase):
    def test_policy_comparison_ignores_statement_order(self):
        required = {
            'Statement': [
                {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:ListBucket'], 'Resource': '*'}
            ]
        }
        actual = {
            'Statement': [
                {'Resource': '*', 'Action': ['s3:ListBucket', 's3:GetObject'], 'Effect': 'Allow'}
            ]
        }
        self.assertEqual([], byor._missing_policy_statements(required, actual))

    def test_preprovisioned_managed_policy_validation_does_not_attach(self):
        iam = ManagedPolicyIam()
        role = lambda name: {
            'Role': {
                'RoleName': name,
                'Arn': f'arn:aws:iam::123:role/{name}'
            }
        }
        byor._copy_managed_policies_arn(
            role('generated'), role('preprovisioned'), iam, execute_flag=True,
            preprovisioned_role=True
        )
        self.assertFalse(iam.attach_called)

    def test_preprovisioned_inline_policy_validation_does_not_put(self):
        iam = InlinePolicyIam()
        role = lambda name: {
            'Role': {
                'RoleName': name,
                'Arn': f'arn:aws:iam::123:role/{name}'
            }
        }
        byor._copy_inline_policies_arn(
            role('generated'), role('preprovisioned'), iam, execute_flag=True,
            preprovisioned_role=True
        )
        self.assertFalse(iam.put_called)

    def test_preprovisioned_group_profile_is_reused(self):
        datazone = DataZoneProfiles()
        byor._replace_project_contributor_member(
            datazone,
            'dzd-domain',
            'project-id',
            'arn:aws:iam::123:role/preprovisioned',
            'arn:aws:iam::123:role/generated',
            execute_flag=True,
            preprovisioned_role=True
        )
        self.assertFalse(datazone.created_profiles)
        self.assertEqual([{'groupIdentifier': 'new-group'}], datazone.created_members)
        self.assertEqual([{'groupIdentifier': 'old-group'}], datazone.deleted_members)


if __name__ == '__main__':
    unittest.main()
