"""Knowledge Base setup for SMUS CLI agent using CloudFormation."""

import boto3
import json
import time
from pathlib import Path
from typing import Dict, Any
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth


def deploy_kb_stack(
    region: str = "us-east-1", user_role_arn: str = None, auto_approve: bool = False
) -> Dict[str, Any]:
    """Deploy CloudFormation stack for KB infrastructure."""
    session = boto3.Session(region_name=region)
    cfn = session.client("cloudformation")
    sts = session.client("sts")

    # Auto-detect user role ARN
    if not user_role_arn:
        caller_identity = sts.get_caller_identity()
        caller_arn = caller_identity["Arn"]
        account_id = caller_identity["Account"]

        if ":assumed-role/" in caller_arn:
            role_name = caller_arn.split("/")[-2]
            user_role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        else:
            user_role_arn = caller_arn

    # Check if stack exists
    stack_name = "smus-cli-kb-stack"
    try:
        cfn.describe_stacks(StackName=stack_name)
        stack_exists = True
        operation = "UPDATE"
    except cfn.exceptions.ClientError:
        stack_exists = False
        operation = "CREATE"

    # Show what will be created/updated
    if not auto_approve:
        print("\n" + "=" * 70)
        print(f"🚀 Knowledge Base Setup - {operation} Stack")
        print("=" * 70)
        print(f"\nRegion: {region}")
        print(f"Account: {account_id}")
        print(f"User Role: {user_role_arn}")
        print(f"\nResources to {operation.lower()}:")
        print("  1. IAM Role: SMUSCLIKnowledgeBaseRole")
        print("  2. OpenSearch Encryption Policy: smus-cli-kb-encryption")
        print("  3. OpenSearch Network Policy: smus-cli-kb-network")
        print("  4. OpenSearch Data Access Policy: smus-cli-kb-access")
        print("  5. OpenSearch Collection: smus-cli-kb (VECTORSEARCH)")

        if not stack_exists:
            print("\nAdditional resources (created after stack):")
            print("  6. OpenSearch Index: bedrock-knowledge-base-default-index")
            print("  7. Bedrock Knowledge Base: SMUS-CLI-KB")
            print("  8. Data Source: SMUS-CLI-Docs")
            print("  9. Ingestion Job: (started)")

        print(f"\nEstimated time: ~5-6 minutes")
        print("=" * 70)

        response = input("\nProceed? (yes/no): ").strip().lower()
        if response not in ["yes", "y"]:
            print("❌ Cancelled by user")
            return None

    print(f"\n🚀 Deploying KB CloudFormation stack in {region}...")
    print(f"👤 User role: {user_role_arn}")

    # Load template
    template_path = Path(__file__).parent / "kb_stack.yaml"
    template_body = template_path.read_text()

    try:
        if stack_exists:
            print("📝 Updating existing stack...")
            try:
                cfn.update_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=[
                        {"ParameterKey": "UserRoleArn", "ParameterValue": user_role_arn}
                    ],
                    Capabilities=["CAPABILITY_NAMED_IAM"],
                )
                waiter = cfn.get_waiter("stack_update_complete")
            except cfn.exceptions.ClientError as e:
                if "No updates are to be performed" in str(e):
                    print("✅ Stack already up to date")
                    response = cfn.describe_stacks(StackName=stack_name)
                    outputs = {
                        o["OutputKey"]: o["OutputValue"]
                        for o in response["Stacks"][0]["Outputs"]
                    }
                    return outputs
                raise
        else:
            print("📝 Creating new stack...")
            cfn.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=[
                    {"ParameterKey": "UserRoleArn", "ParameterValue": user_role_arn}
                ],
                Capabilities=["CAPABILITY_NAMED_IAM"],
            )
            waiter = cfn.get_waiter("stack_create_complete")

        print("⏳ Waiting for stack operation to complete...")
        print("   (This may take 3-5 minutes)")

        # Poll with progress updates every minute
        start_time = time.time()
        last_update = 0
        while True:
            try:
                waiter.wait(
                    StackName=stack_name, WaiterConfig={"Delay": 15, "MaxAttempts": 1}
                )
                break
            except Exception as e:
                if "Max attempts exceeded" in str(e):
                    # Still in progress, show elapsed time every minute
                    elapsed = int(time.time() - start_time)
                    if elapsed - last_update >= 60:
                        minutes = elapsed // 60
                        print(f"   Still working... ({minutes}m elapsed)")
                        last_update = elapsed
                    continue
                raise

        print("✅ Stack operation complete")

    except Exception as e:
        print(f"\n❌ Stack operation failed: {e}")

        # Show failure details
        print("\nFailure details:")
        try:
            events = cfn.describe_stack_events(StackName=stack_name)
            shown = 0
            for event in events["StackEvents"]:
                if "FAILED" in event["ResourceStatus"] and shown < 5:
                    reason = event.get("ResourceStatusReason", "Unknown")
                    print(f"  • {event['LogicalResourceId']}: {reason}")
                    shown += 1
        except Exception as detail_error:
            print(f"  Could not retrieve details: {detail_error}")

        raise

    # Get stack outputs
    response = cfn.describe_stacks(StackName=stack_name)
    outputs = {
        o["OutputKey"]: o["OutputValue"] for o in response["Stacks"][0]["Outputs"]
    }

    return outputs


def create_opensearch_index(
    collection_endpoint: str,
    region: str,
    index_name: str = "bedrock-knowledge-base-default-index",
):
    """Create OpenSearch index for Bedrock KB."""
    print(f"📊 Creating OpenSearch index: {index_name}...")

    session = boto3.Session(region_name=region)
    credentials = session.get_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        region,
        "aoss",
        session_token=credentials.token,
    )

    host = collection_endpoint.replace("https://", "")
    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )

    # Check if index exists
    if client.indices.exists(index=index_name):
        print(f"✅ Index already exists: {index_name}")
        return

    # Create index with FAISS engine and 1024 dimensions (Titan v2)
    index_body = {
        "settings": {"index.knn": True},
        "mappings": {
            "properties": {
                "bedrock-knowledge-base-default-vector": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {"engine": "faiss", "name": "hnsw"},
                },
                "AMAZON_BEDROCK_TEXT_CHUNK": {"type": "text"},
                "AMAZON_BEDROCK_METADATA": {"type": "text"},
            }
        },
    }

    client.indices.create(index=index_name, body=index_body)
    print(f"✅ Created index: {index_name}")

    # Wait for index to be ready
    time.sleep(30)


def create_bedrock_kb(
    role_arn: str, collection_arn: str, region: str
) -> Dict[str, str]:
    """Create Bedrock Knowledge Base."""
    print("🤖 Creating Bedrock Knowledge Base...")

    bedrock_agent = boto3.client("bedrock-agent", region_name=region)

    try:
        response = bedrock_agent.create_knowledge_base(
            name="SMUS-CLI-KB",
            description="Knowledge Base for SMUS CLI Agent",
            roleArn=role_arn,
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {
                    "embeddingModelArn": f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"
                },
            },
            storageConfiguration={
                "type": "OPENSEARCH_SERVERLESS",
                "opensearchServerlessConfiguration": {
                    "collectionArn": collection_arn,
                    "vectorIndexName": "bedrock-knowledge-base-default-index",
                    "fieldMapping": {
                        "vectorField": "bedrock-knowledge-base-default-vector",
                        "textField": "AMAZON_BEDROCK_TEXT_CHUNK",
                        "metadataField": "AMAZON_BEDROCK_METADATA",
                    },
                },
            },
        )

        kb_id = response["knowledgeBase"]["knowledgeBaseId"]
        print(f"✅ Created Knowledge Base: {kb_id}")
        return {"kb_id": kb_id}

    except bedrock_agent.exceptions.ConflictException:
        # KB already exists, find it
        response = bedrock_agent.list_knowledge_bases()
        for kb in response["knowledgeBaseSummaries"]:
            if kb["name"] == "SMUS-CLI-KB":
                kb_id = kb["knowledgeBaseId"]
                print(f"✅ Knowledge Base already exists: {kb_id}")
                return {"kb_id": kb_id}
        raise


def create_data_source(kb_id: str, bucket_name: str, region: str) -> str:
    """Create Bedrock data source."""
    print("📚 Creating data source...")

    bedrock_agent = boto3.client("bedrock-agent", region_name=region)

    try:
        response = bedrock_agent.create_data_source(
            knowledgeBaseId=kb_id,
            name="SMUS-CLI-Docs",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {"bucketArn": f"arn:aws:s3:::{bucket_name}"},
            },
        )

        ds_id = response["dataSource"]["dataSourceId"]
        print(f"✅ Created data source: {ds_id}")
        return ds_id

    except bedrock_agent.exceptions.ConflictException:
        # Data source already exists
        response = bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)
        ds_id = response["dataSourceSummaries"][0]["dataSourceId"]
        print(f"✅ Data source already exists: {ds_id}")
        return ds_id


def start_ingestion(kb_id: str, ds_id: str, region: str):
    """Start ingestion job."""
    bedrock_agent = boto3.client("bedrock-agent", region_name=region)

    # Wait for KB to be ACTIVE
    print("⏳ Waiting for Knowledge Base to be ACTIVE...")
    for i in range(30):
        response = bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)
        status = response["knowledgeBase"]["status"]
        if status == "ACTIVE":
            break
        print(f"   Status: {status}")
        time.sleep(10)

    print("🔄 Starting ingestion job...")
    response = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=kb_id, dataSourceId=ds_id
    )

    job_id = response["ingestionJob"]["ingestionJobId"]
    print(f"✅ Started ingestion job: {job_id}")
    return job_id


def delete_kb_stack(region: str = "us-east-1"):
    """Delete CloudFormation stack and all resources."""
    print("🗑️  Deleting KB stack...")

    session = boto3.Session(region_name=region)
    cfn = session.client("cloudformation")
    bedrock_agent = session.client("bedrock-agent")
    aoss = session.client("opensearchserverless")

    # Delete Bedrock KB first (not in stack)
    try:
        response = bedrock_agent.list_knowledge_bases()
        for kb in response["knowledgeBaseSummaries"]:
            if kb["name"] == "SMUS-CLI-KB":
                kb_id = kb["knowledgeBaseId"]
                print(f"🗑️  Deleting Knowledge Base: {kb_id}")
                bedrock_agent.delete_knowledge_base(knowledgeBaseId=kb_id)
                time.sleep(5)
    except Exception as e:
        print(f"⚠️  Error deleting KB: {e}")

    # Delete stack
    try:
        cfn.delete_stack(StackName="smus-cli-kb-stack")
        print("⏳ Waiting for stack deletion...")
        waiter = cfn.get_waiter("stack_delete_complete")
        waiter.wait(StackName="smus-cli-kb-stack")
        print("✅ Stack deleted")
    except cfn.exceptions.ClientError as e:
        if "does not exist" in str(e):
            print("✅ Stack already deleted")
        else:
            raise

    # Clean up orphaned OpenSearch collection
    try:
        response = aoss.batch_get_collection(names=["smus-cli-kb"])
        if response["collectionDetails"]:
            collection_id = response["collectionDetails"][0]["id"]
            print(f"🗑️  Deleting orphaned collection: {collection_id}")
            aoss.delete_collection(id=collection_id)
            time.sleep(10)
    except aoss.exceptions.ResourceNotFoundException:
        pass
    except Exception as e:
        print(f"⚠️  Error deleting collection: {e}")

    # Clean up orphaned OpenSearch policies (in case stack creation failed)
    # Note: Data access policies use delete_access_policy, not delete_security_policy
    try:
        aoss.delete_access_policy(name="smus-cli-kb-access", type="data")
        print(f"🗑️  Deleted orphaned policy: smus-cli-kb-access")
    except aoss.exceptions.ResourceNotFoundException:
        pass
    except Exception as e:
        print(f"⚠️  Error deleting policy smus-cli-kb-access: {e}")

    for policy_name, policy_type in [
        ("smus-cli-kb-network", "network"),
        ("smus-cli-kb-encryption", "encryption"),
    ]:
        try:
            aoss.delete_security_policy(name=policy_name, type=policy_type)
            print(f"🗑️  Deleted orphaned policy: {policy_name}")
        except aoss.exceptions.ResourceNotFoundException:
            pass
        except Exception as e:
            print(f"⚠️  Error deleting policy {policy_name}: {e}")


def ensure_kb_exists():
    """Placeholder for chat agent compatibility."""
    from .config import load_config

    config = load_config()
    return config.get("bedrock", {}).get("knowledge_base_id")


def sync_kb():
    """Sync KB with latest docs."""
    from .config import load_config

    config = load_config()
    kb_id = config.get("bedrock", {}).get("knowledge_base_id")
    ds_id = config.get("bedrock", {}).get("data_source_id")
    region = config.get("interactive", {}).get("region", "us-east-1")

    if not kb_id or not ds_id:
        print("❌ Knowledge Base not configured.")
        response = input("Would you like to set it up now? (yes/no): ").strip().lower()
        if response in ["yes", "y"]:
            print("\nPlease run: smus-cli kb setup")
        return

    start_ingestion(kb_id, ds_id, region)
