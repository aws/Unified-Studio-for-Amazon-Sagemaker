# Cross-Domain Data Product Publication & Subscription

Publish data products from one SageMaker Unified Studio (SMUS) domain and make them discoverable, subscribable, and queryable in another domain without data duplication.

## Overview

This solution enables cross-domain data product publication and subscription in SageMaker Unified Studio (SMUS). It lets you publish a data product in one SMUS domain and make it discoverable, subscribable, and queryable in another domain, while the data stays in the producer's account and is read in place.

It extends the native SMUS experience so organizations with multiple domains (for example, separate business units, regulatory boundaries, or newly acquired teams) can share governed data products across those boundaries and consume them through the standard SMUS subscription workflow.

## Use cases

- Share curated data products across business-unit or regulatory domain boundaries.
- Offer a central "marketplace" domain where products from many producer domains are discoverable in one place.
- Give consumers a familiar SMUS subscribe-and-query experience for data that lives in another domain, with Lake Formation governing access and no data duplication.

## How it works

Event-driven catalog mirroring with Lambda functions that sync table metadata, business context, data quality results, and lineage across domains. Consumers subscribe and query through native SMUS workflows with Lake Formation governing access.

### Key Features

- **Zero-copy data access**: consumers read producer's S3 directly via LF credential vending
- **Native SageMaker Catalog subscription fulfilment**: managed assets with automatic LF grants on approval
- **Business metadata sync**: name, description, readme, column descriptions from producer domain
- **DQ results propagation**: real-time via a native Glue DQ event (event-driven), and also pulled from the producer on each asset sync as a backstop
- **Lineage sync**: OpenLineage COMPLETE events forwarded across domains, triggered by Producer Glue job completions
- **Lake Formation fine-grained access control**: column/row level security in the consumer domain

## Architecture

![Cross-domain data product synchronization architecture](diagrams/architecture.jpg)

## Components

| Component | Purpose |
|-----------|---------|
| `lambda/glue_table_sync.py` | Mirrors the Glue table schema (including partition keys) and grants Lake Formation permissions to the project role |
| `lambda/catalog_sync_mirror.py` | Syncs business metadata, DQ results, and lineage; creates and publishes the managed-asset revision |
| `lambda/dq_results_sync.py` | Event-driven DQ path: on a native Glue DQ completion event from the Producer, posts the result onto the matching managed asset |
| `lambda/lineage_sync.py` | Event-driven lineage path: on a Producer Glue job completion, forwards COMPLETE OpenLineage events into this domain (domain id remapped) |
| `cloudformation/template.yaml` | Marketplace-account stack: Lambdas, scoped EventBridge rules, dead-letter queues, least-privilege IAM, and the Lake Formation role |
| `cloudformation/producer-account.yaml` | Producer-account stack: the three cross-account roles and the EventBridge forwarding rules |
| `tests/` | Unit tests for the Glue table sync and catalog sync mirror Lambdas (mocked boto3) |
| `Makefile` | `make verify` (lint + tests) and `make package` (build deployment zips) |

## Prerequisites

- Two AWS accounts with SMUS domains configured
- Producer account: Tables in a Glue database, S3 bucket with data
- Marketplace account: SMUS project with Lakehouse Database environment
- Cross-account EventBridge permissions configured
- Lake Formation: Producer's S3 location registered in Marketplace account
- If either Glue Data Catalog is **Lake Formation-managed**, the sync roles need explicit LF grants (created by the stacks — see Step 4); if the Marketplace catalog is **SSE-KMS encrypted**, the Lambda role also needs KMS access (Step 4e)

## Deployment

### Cross-account trust model

This solution runs in the Marketplace account and reaches into the Producer account. The Marketplace `CatalogSyncLambdaRole` assumes roles in the Producer account, so the Producer roles must trust the Marketplace account. There are three separate cross-account paths, and they use different mechanisms. Do not merge them into one role.

| Path | Direction | Mechanism |
|------|-----------|-----------|
| Metadata and DQ reads | Marketplace `CatalogSyncLambdaRole` assumes Producer `GlueFederationAccessRole` and `DataZoneReaderRole` | `sts:AssumeRole` |
| Event forwarding | Producer EventBridge rules send events to the Marketplace default event bus | `events:PutEvents` via a Producer events role trusting `events.amazonaws.com` |
| S3 zero-copy reads | Marketplace `MirrorCatalogLFRole` reads Producer S3 | Lake Formation credential vending, allowed by the Producer S3 bucket policy |

Steps 4, 5, and 6 implement this model in the Producer account.

### Step 1: Build and upload the Lambda packages

```bash
make package
# Upload the artifacts to a bucket the Marketplace CloudFormation stack can read
aws s3 cp build/glue_table_sync.zip     s3://<CODE_BUCKET>/glue_table_sync.zip
aws s3 cp build/catalog_sync_mirror.zip s3://<CODE_BUCKET>/catalog_sync_mirror.zip
aws s3 cp build/dq_results_sync.zip     s3://<CODE_BUCKET>/dq_results_sync.zip
aws s3 cp build/lineage_sync.zip        s3://<CODE_BUCKET>/lineage_sync.zip
```

### Step 2: Deploy the Producer-account stack (Account 1)

This creates `GlueFederationAccessRole`, `DataZoneReaderRole`, `EventForwardingRole`, and the four EventBridge forwarding rules (Glue table changes, SageMaker Catalog asset publishes, Glue Data Quality results, and Glue job completions for lineage). It implements the cross-account trust model above.

```bash
aws cloudformation deploy \
  --template-file cloudformation/producer-account.yaml \
  --stack-name cross-domain-data-product-sync-producer \
  --parameter-overrides \
    MarketplaceAccountId=<MARKETPLACE_ACCOUNT_ID> \
    MarketplaceRegion=<MARKETPLACE_REGION> \
    ProducerDatabase=<PRODUCER_GLUE_DB> \
    ProducerS3BucketArn=arn:aws:s3:::<PRODUCER_S3_BUCKET> \
  --capabilities CAPABILITY_NAMED_IAM
```

Then add `DataZoneReaderRole` as a **Contributor** to the Producer's SMUS project (required for `GetAsset`).

### Step 3: Deploy the Marketplace-account stack (Account 2)

This creates `CatalogSyncLambdaRole`, `MirrorCatalogLFRole`, the four Lambdas (from the uploaded packages), the scoped EventBridge rules, dead-letter queues, and the event-bus policy. Use the role ARNs output by the Producer stack.

```bash
aws cloudformation deploy \
  --template-file cloudformation/template.yaml \
  --stack-name cross-domain-data-product-sync \
  --parameter-overrides \
    SourceAccountId=<PRODUCER_ACCOUNT_ID> \
    SourceDatabase=<PRODUCER_GLUE_DB> \
    SourceDomainId=<PRODUCER_DOMAIN_ID> \
    SourceProjectId=<PRODUCER_PROJECT_ID> \
    TargetDatabase=<MARKETPLACE_GLUE_DB> \
    DomainId=<MARKETPLACE_DOMAIN_ID> \
    ProjectId=<MARKETPLACE_PROJECT_ID> \
    ProjectEnvironmentRoleArn=<MARKETPLACE_PROJECT_ENV_ROLE_ARN> \
    SourceGlueRoleArn=<GlueFederationAccessRole_ARN_from_producer_stack> \
    SourceDataZoneRoleArn=<DataZoneReaderRole_ARN_from_producer_stack> \
    S3BucketArn=arn:aws:s3:::<PRODUCER_S3_BUCKET> \
    CodeS3Bucket=<CODE_BUCKET> \
  --capabilities CAPABILITY_NAMED_IAM
```

### Step 4: Manual setup in the Marketplace account (Account 2)

| Step | Action | Why |
|------|--------|-----|
| 4a | Register Producer's S3 location in Lake Formation with `MirrorCatalogLFRole` | Enables credential vending for cross-account S3 reads |
| 4b | Add `CatalogSyncLambdaRole` as **Contributor** to the Marketplace SMUS project | Lambda needs SageMaker Catalog permissions to search/update assets |
| 4c | Create a **Data Source** in the Marketplace project pointing to the target Glue database | Required for creating managed assets (subscription-eligible) |
| 4d | Enable LF Application Integration Settings: "Allow external engines to access data in Amazon S3 locations with full table access" | Required only when an external/third-party engine needs full-table (unfiltered) credential vending; not needed for the fine-grained LF path |
| 4e | If this account's Glue Data Catalog is **SSE-KMS encrypted**, grant `CatalogSyncLambdaRole` `kms:Decrypt`, `kms:GenerateDataKey`, and `kms:DescribeKey` on the catalog CMK | Otherwise `CreateTable`/`UpdateTable` fail with `GlueEncryptionException`. Skip if the catalog is unencrypted |

> **Lake Formation grants:** The stacks now create the Lake Formation grants the
> sync roles need (`CatalogSyncLambdaRole` on the target DB, `GlueFederationAccessRole`
> on the Producer DB). For those `AWS::LakeFormation::PrincipalPermissions` resources
> to deploy, the principal running each `cloudformation deploy` must be a **Lake
> Formation data lake administrator** in that account.

```bash
# 4a: Register S3 location
aws lakeformation register-resource \
  --resource-arn arn:aws:s3:::<PRODUCER_S3_BUCKET>/<PATH> \
  --role-arn arn:aws:iam::<MARKETPLACE_ACCOUNT_ID>:role/MirrorCatalogLFRole \
  --no-use-service-linked-role

# 4e (only if the Glue catalog is SSE-KMS encrypted): grant the Lambda role KMS access
aws iam put-role-policy \
  --role-name CatalogSyncLambdaRole \
  --policy-name GlueCatalogKmsAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"],
      "Resource": "<GLUE_CATALOG_KMS_KEY_ARN>"
    }]
  }'

# 4b: Add Lambda role as project Contributor (via SMUS UI or API)
# Navigate to: SMUS Portal -> Project -> Members -> Add Member -> CatalogSyncLambdaRole
```

### Step 5: S3 bucket policy in the Producer account (Account 1)

The Producer stack (Step 2) creates the roles and forwarding rules. The S3 bucket policy must still be updated manually so the Marketplace `MirrorCatalogLFRole` can read the underlying data:

```json
{
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::<MARKETPLACE_ACCOUNT_ID>:role/MirrorCatalogLFRole"
  },
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": [
    "arn:aws:s3:::<PRODUCER_BUCKET>",
    "arn:aws:s3:::<PRODUCER_BUCKET>/*"
  ]
}
```

> Enable CloudTrail in the Producer account so that Glue `CreateTable` and `UpdateTable` calls are delivered to EventBridge as `AWS API Call via CloudTrail` events. The forwarding rule matches these events to trigger table mirroring.

### Setup Summary

| What | Where | How |
|------|-------|-----|
| Package and upload Lambda code | Build machine | `make package` + `aws s3 cp` |
| Producer stack (3 roles + forwarding rules + LF read grants) | Producer account | `cloudformation deploy` (`producer-account.yaml`) |
| Marketplace stack (4 Lambdas, DLQs, rules, roles + LF write grants) | Marketplace account | `cloudformation deploy` (`template.yaml`) |
| LF S3 registration | Marketplace account | CLI (`register-resource`) |
| CatalogSyncLambdaRole as project Contributor | Marketplace SMUS project | UI or API |
| Data Source creation | Marketplace SMUS project | UI |
| LF Application Integration Settings (external-engine full-table access only) | Marketplace account | LF Console |
| Glue catalog KMS access for the Lambda role (SSE-KMS catalogs only) | Marketplace account | CLI (`put-role-policy`) |
| DataZoneReaderRole as project Contributor | Producer SMUS project | UI |
| S3 bucket policy update | Producer account | S3 Console/CLI |

> **Deploying principal must be a Lake Formation admin** in each account, because
> both stacks now create `AWS::LakeFormation::PrincipalPermissions` grants.

## End-to-End Workflow

### First-time setup

1. Producer: create a table. It auto-mirrors to the Marketplace account (about 30s via CloudTrail).
2. Producer: run the data source, curate the asset (name, description, readme), and publish.
3. Marketplace: run the data source (manual) to create the managed asset. This triggers the metadata overlay.
4. Consumer: discover the asset, subscribe, get approval, and query the data.

### Ongoing updates

- Re-publish in the Producer to auto-sync metadata to the Marketplace.
- Schema changes are auto-mirrored via the Glue table sync.
- DQ results sync in real time: a Glue DQ run in the Producer emits a native event that is forwarded and applied to the asset. They are also re-pulled on each asset sync as a backstop.
- Lineage syncs when a Producer Glue job completes: COMPLETE OpenLineage events are forwarded into the Marketplace domain. Lineage is also forwarded (scoped to an asset) during a metadata sync as a backstop.

## Development

```bash
make install   # install dev dependencies (boto3, pytest)
make verify    # byte-compile the Lambdas and run unit tests
make package   # build deployment zips into build/
```

## Considerations

| Consideration | Guidance |
|---------------|----------|
| Glossary terms are domain-scoped | Create matching terms in the Marketplace domain to mirror them |
| Data source run triggers the overlay | Run on demand, schedule it, or trigger via the `StartDataSourceRun` API |
| Subscription approval happens in the Marketplace account | Optionally notify the Producer via EventBridge and a callback |
| Table sync completes in about 30s (CloudTrail-driven) | Well within range for catalog metadata sync |
| DQ event delivery is best-effort | Event-driven DQ sync fires on the native Glue DQ event (`aws.glue-dataquality`); the pull on each asset sync acts as a backstop if an event is missed |

## Security

This solution uses scoped IAM policies (resource-level where the APIs support it), scoped Lake Formation grants, and explicit cross-account trust. As with any reference implementation, review the IAM policies and trust relationships and align them with your organization's security standards before deploying to production.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0
