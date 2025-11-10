"""
Dedicated test for Knowledge Base setup issue.

Issue: OpenSearch Serverless index doesn't exist when creating Bedrock KB
Error: "no such index [bedrock-knowledge-base-default-index]"

This test isolates the KB creation problem to debug and fix it.
"""
import pytest
import boto3
import time
import json
from botocore.exceptions import ClientError


@pytest.mark.integration
@pytest.mark.slow
class TestKBSetupIssue:
    """Isolated test for KB setup index creation issue."""
    
    def test_opensearch_serverless_kb_setup(self):
        """
        Test complete OpenSearch Serverless + Bedrock KB setup.
        
        Steps:
        1. Create IAM role for KB
        2. Create OpenSearch Serverless security policies
        3. Create OpenSearch Serverless collection
        4. Wait for collection to be ACTIVE
        5. Wait for policies to propagate
        6. Create Bedrock Knowledge Base
        
        Expected: KB creation succeeds
        Actual: Fails with "no such index" error
        """
        # Setup
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        region = 'us-east-2'
        
        iam = boto3.client('iam')
        aoss = boto3.client('opensearchserverless', region_name=region)
        bedrock_agent = boto3.client('bedrock-agent', region_name=region)
        s3 = boto3.client('s3', region_name=region)
        
        collection_name = 'test-kb-issue'
        role_name = 'TestKBIssueRole'
        bucket_name = f'test-kb-issue-{account_id}'
        
        # Cleanup any previous test resources
        self._cleanup(aoss, iam, s3, bedrock_agent, collection_name, role_name, bucket_name, account_id)
        
        try:
            # Step 1: Create S3 bucket
            print("\n1. Creating S3 bucket...")
            try:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'BucketAlreadyOwnedByYou':
                    raise
            
            # Step 2: Create IAM role
            print("2. Creating IAM role...")
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            
            role_response = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            role_arn = role_response['Role']['Arn']
            
            # Add S3 permissions
            s3_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:ListBucket"],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{bucket_name}/*"
                    ]
                }]
            }
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName='S3Access',
                PolicyDocument=json.dumps(s3_policy)
            )
            
            # Add OpenSearch Serverless permissions
            aoss_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["aoss:APIAccessAll"],
                    "Resource": f"arn:aws:aoss:{region}:{account_id}:collection/*"
                }]
            }
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName='AOSSAccess',
                PolicyDocument=json.dumps(aoss_policy)
            )
            
            # Attach Bedrock policy
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/AmazonBedrockFullAccess'
            )
            
            print(f"   Role ARN: {role_arn}")
            time.sleep(10)  # Wait for role to propagate
            
            # Step 3: Create security policies
            print("3. Creating OpenSearch Serverless security policies...")
            
            # Get current user role ARN
            caller_arn = sts.get_caller_identity()['Arn']
            if ':assumed-role/' in caller_arn:
                role_name_from_arn = caller_arn.split('/')[-2]
                user_role_arn = f"arn:aws:iam::{account_id}:role/{role_name_from_arn}"
            else:
                user_role_arn = caller_arn
            
            # Encryption policy
            encryption_policy = {
                "Rules": [{
                    "ResourceType": "collection",
                    "Resource": [f"collection/{collection_name}"]
                }],
                "AWSOwnedKey": True
            }
            aoss.create_security_policy(
                name=f'{collection_name}-encryption',
                type='encryption',
                policy=json.dumps(encryption_policy)
            )
            
            # Network policy
            network_policy = [{
                "Rules": [{
                    "ResourceType": "collection",
                    "Resource": [f"collection/{collection_name}"]
                }],
                "AllowFromPublic": True
            }]
            aoss.create_security_policy(
                name=f'{collection_name}-network',
                type='network',
                policy=json.dumps(network_policy)
            )
            
            # Data access policy
            data_policy = [{
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": [f"collection/{collection_name}"],
                        "Permission": [
                            "aoss:CreateCollectionItems",
                            "aoss:UpdateCollectionItems",
                            "aoss:DescribeCollectionItems"
                        ]
                    },
                    {
                        "ResourceType": "index",
                        "Resource": [f"index/{collection_name}/*"],
                        "Permission": [
                            "aoss:CreateIndex",
                            "aoss:UpdateIndex",
                            "aoss:DescribeIndex",
                            "aoss:ReadDocument",
                            "aoss:WriteDocument"
                        ]
                    }
                ],
                "Principal": [role_arn, user_role_arn]
            }]
            aoss.create_access_policy(
                name=f'{collection_name}-access',
                type='data',
                policy=json.dumps(data_policy)
            )
            print("   Policies created")
            
            # Step 4: Create collection
            print("4. Creating OpenSearch Serverless collection...")
            collection_response = aoss.create_collection(
                name=collection_name,
                type='VECTORSEARCH'
            )
            
            # Step 5: Wait for collection to be ACTIVE
            print("5. Waiting for collection to become ACTIVE...")
            collection_arn = None
            for i in range(30):
                time.sleep(10)
                status_response = aoss.batch_get_collection(names=[collection_name])
                if status_response['collectionDetails']:
                    status = status_response['collectionDetails'][0]['status']
                    print(f"   Status: {status} ({i*10}s)")
                    if status == 'ACTIVE':
                        collection_arn = status_response['collectionDetails'][0]['arn']
                        break
            
            assert collection_arn, "Collection never became ACTIVE"
            print(f"   Collection ARN: {collection_arn}")
            
            # Step 6: Wait for policies to propagate
            print("6. Waiting for policies to propagate (2 minutes)...")
            time.sleep(120)
            
            # Step 7: Create Bedrock Knowledge Base
            print("7. Creating Bedrock Knowledge Base...")
            print(f"   Using collection ARN: {collection_arn}")
            print(f"   Using role ARN: {role_arn}")
            print(f"   Index name: bedrock-knowledge-base-default-index")
            
            kb_response = bedrock_agent.create_knowledge_base(
                name='TestKBIssue',
                roleArn=role_arn,
                knowledgeBaseConfiguration={
                    'type': 'VECTOR',
                    'vectorKnowledgeBaseConfiguration': {
                        'embeddingModelArn': f'arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v1'
                    }
                },
                storageConfiguration={
                    'type': 'OPENSEARCH_SERVERLESS',
                    'opensearchServerlessConfiguration': {
                        'collectionArn': collection_arn,
                        'vectorIndexName': 'bedrock-knowledge-base-default-index',
                        'fieldMapping': {
                            'vectorField': 'bedrock-knowledge-base-default-vector',
                            'textField': 'AMAZON_BEDROCK_TEXT_CHUNK',
                            'metadataField': 'AMAZON_BEDROCK_METADATA'
                        }
                    }
                }
            )
            
            kb_id = kb_response['knowledgeBase']['knowledgeBaseId']
            print(f"   ✅ SUCCESS! KB ID: {kb_id}")
            
            # Cleanup
            bedrock_agent.delete_knowledge_base(knowledgeBaseId=kb_id)
            
        finally:
            # Always cleanup
            self._cleanup(aoss, iam, s3, bedrock_agent, collection_name, role_name, bucket_name, account_id)
    
    def _cleanup(self, aoss, iam, s3, bedrock_agent, collection_name, role_name, bucket_name, account_id):
        """Clean up all test resources."""
        print("\nCleaning up...")
        
        # Delete collection
        try:
            response = aoss.batch_get_collection(names=[collection_name])
            if response['collectionDetails']:
                collection_id = response['collectionDetails'][0]['id']
                aoss.delete_collection(id=collection_id)
                print(f"   Deleted collection: {collection_id}")
        except Exception:
            pass
        
        # Delete policies
        try:
            aoss.delete_security_policy(name=f'{collection_name}-encryption', type='encryption')
        except Exception:
            pass
        try:
            aoss.delete_security_policy(name=f'{collection_name}-network', type='network')
        except Exception:
            pass
        try:
            aoss.delete_access_policy(name=f'{collection_name}-access', type='data')
        except Exception:
            pass
        
        # Delete IAM role
        try:
            iam.delete_role_policy(RoleName=role_name, PolicyName='S3Access')
        except Exception:
            pass
        try:
            iam.delete_role_policy(RoleName=role_name, PolicyName='AOSSAccess')
        except Exception:
            pass
        try:
            iam.detach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/AmazonBedrockFullAccess'
            )
        except Exception:
            pass
        try:
            iam.delete_role(RoleName=role_name)
        except Exception:
            pass
        
        # Delete S3 bucket
        try:
            paginator = s3.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name):
                if 'Contents' in page:
                    objects = [{'Key': obj['Key']} for obj in page['Contents']]
                    s3.delete_objects(Bucket=bucket_name, Delete={'Objects': objects})
            s3.delete_bucket(Bucket=bucket_name)
        except Exception:
            pass
        
        print("   Cleanup complete")
