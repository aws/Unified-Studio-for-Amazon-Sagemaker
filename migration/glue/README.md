# Migrate AWS Glue jobs and connections

Move AWS Glue Python script jobs into an Amazon SageMaker Unified Studio project,
clone supported connections into the project, or discover jobs by execution role.
All three commands default to **dry-run**. Review the output before adding `--apply`.
The [migration skill](SKILL.md) runs connection cloning for every selected job,
including discovery results and already-migrated jobs, then offers script and
attachment cutover after successful cloning.

## Prerequisites

- Python 3.12 or later.
- AWS credentials for the account containing your Glue resources, configured
  through the standard AWS credential chain (for example, an AWS IAM Identity
  Center session or an assume-role profile).
- An existing SageMaker Unified Studio domain and project.
- The [IAM permissions below](#iam-permissions). Connection creation also requires
  membership in the target project: IAM permissions and project membership are
  separate requirements.

The tool uses **the caller's configured credentials**. It does not automatically
assume the project's execution role. Use `--profile` to select a configured profile.

From the repository root:

```bash
python -m venv migration/glue/.venv
source migration/glue/.venv/bin/activate
python -m pip install -r migration/glue/requirements.txt
```

Run the commands below from the repository root. No package installation is needed.

## Choose a command

| Task | Module |
|---|---|
| Migrate one known job | `migration.glue.cli` |
| Clone connections without changing a job | `migration.glue.cli_connections` |
| Discover and migrate jobs by project execution role | `migration.glue.discover_cli` |

### Migrate one job

```bash
python -m migration.glue.cli --job-name my-etl-job \
  --domain-id dzd-example --project-id project-example --region eu-north-1

# Apply the reviewed migration.
python -m migration.glue.cli --job-name my-etl-job \
  --domain-id dzd-example --project-id project-example --region eu-north-1 --apply
```

The tool snapshots the job, grants the project execution role `iam:PassRole`
on the job's execution role, copies its script into the project's bucket,
updates the script location and job settings, then adds migration tags. The
grant is restricted to `iam:PassedToService=glue.amazonaws.com`. Original script
bytes, connection names and the job's IAM role are preserved. The update removes
the old source-control link and normalizes known Glue boolean enable flags for
the Studio editor.

The project execution role and bucket are resolved through the project's default
IAM connection. Dry runs include the proposed grant under `passRole` without
writing IAM policies. On apply, each distinct job role gets a dedicated inline
policy named `SMUSGlueJobPassRole-<hash>` on the project role. Existing matching
policies are reused; conflicting policies fail without being overwritten.
Use `--bucket BUCKET_NAME` to override the bucket, or `--domain-region REGION` when the
domain is in a different Region from the Glue resources. `--region` defaults to
`us-east-2`; set it explicitly for your resources.

### Clone connections

```bash
python -m migration.glue.cli_connections --job-name my-etl-job \
  --domain-id dzd-example --project-id project-example --region eu-north-1

# Select connections directly instead of reading their names from a job.
python -m migration.glue.cli_connections \
  --connection-name source-mysql --connection-name source-snowflake \
  --domain-id dzd-example --project-id project-example --region eu-north-1
```

Add `--apply` after reviewing the plan. Cloning leaves the job, its script and its
attached connections unchanged. Clones use the project's role and the source
connection's existing Secrets Manager secret. The migration tool reads secret
metadata, never secret values.

On apply, an untagged secret or a secret belonging to another project is
automatically tagged `for-use-with-all-datazone-projects=true`, preserving existing
project ownership. This can grant secret access to admin roles in other Studio
projects. Dry runs report planned tags without writing them. `--shared-secret`
remains accepted for compatibility but is no longer needed and has no effect.
`--domain-region` is supported here too.

### Discover jobs

```bash
python -m migration.glue.discover_cli --region eu-north-1

# Limit discovery to a known domain and project.
python -m migration.glue.discover_cli --region eu-north-1 \
  --domain-id dzd-example --project-id project-example
```

Discovery lists accessible domains and projects, resolves their execution roles,
and matches those roles to Glue jobs. Add `--apply` to migrate the matches.
Only Python `.py` script jobs (`glueetl` or `pythonshell`) are matched. Visual,
notebook, streaming, Ray and non-Python jobs are reported as unsupported and skipped.
Unmatched jobs and jobs matching multiple projects are skipped. Connection
cloning uses the separate command above; the migration skill runs it for every
matched job before reporting completion.

Discovery covers one Region. Permission denials exclude a domain and print a
warning; a denied domain listing produces an empty plan. Other service errors
fail the command. A unique match only considers included projects: an excluded
project may share the same role. Review warnings and matches before applying.

## Supported connections and limitations

Connection cloning supports **version 2**, data-source-specific connections for
Amazon DocumentDB, DynamoDB, OpenSearch Service, Redshift, MySQL, PostgreSQL,
Microsoft SQL Server, Oracle, Google BigQuery, Snowflake and Teradata.

- Version 1 and generic `JDBC` connections cannot be cloned.
- OAuth 2.0, Redshift IAM authentication and credentials stored directly in
  connection properties are unsupported. Basic/custom authentication requires a
  Secrets Manager secret reference.
- Accepted risk: cloning keeps only the first `MatchCriteria` entry, truncated to
  ten characters to fit DataZone. Lookups using the original criteria may omit
  the clone; additional criteria are not preserved.
- These cloning restrictions do not restrict the original connections preserved
  by job migration.
- Only Python script jobs are supported; this tool does not convert visual ETL jobs.
- Job migration skips job updates when `AmazonDataZoneProject` already matches
  the target project, but still ensures the project's PassRole grant on apply.
  This also repairs grants for previously migrated jobs. Repeated cloning reuses
  ready clones with matching provenance; conflicting names fail before creation.
- Original connection names are stored in indexed
  `AmazonDataZonePreMigrationConnection-*` tags. Glue's 50-user-tag limit leaves
  at most 48 names, fewer when other tags exist. Names must satisfy Glue tag
  character restrictions; invalid names fail before writes. Studio editors must
  support these indexed tags to display original connections.
- ARN partitions are resolved by boto3 from the configured Region. This does not
  extend SageMaker Unified Studio availability to additional Regions or partitions.

## Recovery

Save the apply output, especially `bucket` and `snapshotKey`. Snapshots live at
`<DOMAIN_ID>/<PROJECT_ID>/.migration-snapshots/<JOB_NAME>/<MIGRATION_ID>.json`.
They contain the original job definition and script bytes. Connection and trigger
capture is best-effort; denied reads do not prevent job migration.

If a job migration fails after a write, inspect the job and its snapshot before
retrying. There is no automatic job rollback. A retry may create another snapshot;
use the snapshot from **before the first change** when restoring the original job.

Rollback is a Python function, available from the same folder:

```python
import json
import boto3
from migration.glue.rollback import rollback_from_snapshot

session = boto3.Session(region_name="eu-north-1")  # optionally profile_name="my-profile"
snapshot = json.loads(session.client("s3").get_object(
    Bucket="PROJECT_BUCKET_NAME",
    Key="SNAPSHOT_KEY",
)["Body"].read())
print(rollback_from_snapshot(session, snapshot))  # preview
# After reviewing the preview:
# print(rollback_from_snapshot(session, snapshot, apply=True))
```

Rollback restores the original job settings and the prior values of tags changed
by migration, removing tags it added. It overwrites subsequent job edits, so stop
concurrent editing first. The original script remains at its source location.
Snapshots must contain `priorJobTags`, which migration records before writing.
Rollback rejects snapshots without this tag history before changing the job.

Rollback retains cloned connections, secret tags, copied scripts, snapshots and
project PassRole policies. A failed migration can also leave its PassRole policy;
other jobs may share that grant. Inspect consumers before manually removing it.
If cloning fails partway through, completed clones and clones whose creation
outcome is uncertain may remain. Error notes identify retained resources and
failed cleanup. Verify consumers before manually deleting clones or removing
sharing tags.

## IAM permissions

Attach permissions to the **caller** used by the tool. The example below covers
job migration, connection cloning and rollback in one account and Region. Replace
all placeholders, restrict job/connection/secret resources to your scope, and
use the domain's Region in DataZone `aws:RequestedRegion` conditions when it
differs from the Glue Region.
Only include permissions for the commands you need.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["glue:GetJob", "glue:GetTags", "glue:UpdateJob"],
      "Resource": "arn:aws:glue:<REGION>:<ACCOUNT_ID>:job/*"
    },
    {
      "Effect": "Allow",
      "Action": ["glue:TagResource", "glue:UntagResource"],
      "Resource": "arn:aws:glue:<REGION>:<ACCOUNT_ID>:job/*",
      "Condition": {
        "ForAllValues:StringLike": {
          "aws:TagKeys": [
            "AmazonDataZoneProject", "AmazonDataZoneDomain",
            "AmazonDataZoneMigratedJob", "AmazonDataZonePreMigrationConnection-*"
          ]
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": "glue:GetConnection",
      "Resource": [
        "arn:aws:glue:<REGION>:<ACCOUNT_ID>:catalog",
        "arn:aws:glue:<REGION>:<ACCOUNT_ID>:connection/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "glue:GetTriggers",
      "Resource": "*",
      "Condition": {"StringEquals": {"aws:RequestedRegion": "<REGION>"}}
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:GetObjectTagging"],
      "Resource": "arn:aws:s3:::<SOURCE_BUCKET>/<SOURCE_PREFIX>/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectTagging"],
      "Resource": [
        "arn:aws:s3:::<PROJECT_BUCKET>/<DOMAIN_ID>/<PROJECT_ID>/shared/jobs/*",
        "arn:aws:s3:::<PROJECT_BUCKET>/<DOMAIN_ID>/<PROJECT_ID>/.migration-snapshots/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::<ACCOUNT_ID>:role/<JOB_ROLE_NAME>",
      "Condition": {"StringEquals": {"iam:PassedToService": "glue.amazonaws.com"}}
    },
    {
      "Effect": "Allow",
      "Action": "iam:GetRole",
      "Resource": "arn:aws:iam::<ACCOUNT_ID>:role/<JOB_ROLE_NAME>"
    },
    {
      "Effect": "Allow",
      "Action": ["iam:GetRolePolicy", "iam:PutRolePolicy"],
      "Resource": "arn:aws:iam::<ACCOUNT_ID>:role/<PROJECT_ROLE_NAME>"
    },
    {
      "Effect": "Allow",
      "Action": [
        "datazone:ListEnvironments", "datazone:GetEnvironment",
        "datazone:ListConnections", "datazone:GetConnection",
        "datazone:CreateConnection", "datazone:DeleteConnection"
      ],
      "Resource": "*",
      "Condition": {"StringEquals": {"aws:RequestedRegion": "<REGION>"}}
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:DescribeSecret",
      "Resource": "arn:aws:secretsmanager:<REGION>:<ACCOUNT_ID>:secret:<SECRET_NAME_PREFIX>*"
    },
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:TagResource", "secretsmanager:UntagResource"],
      "Resource": "arn:aws:secretsmanager:<REGION>:<ACCOUNT_ID>:secret:<SECRET_NAME_PREFIX>*",
      "Condition": {
        "ForAllValues:StringEquals": {
          "aws:TagKeys": [
            "AmazonDataZoneProject", "AmazonDataZoneDomain",
            "for-use-with-all-datazone-projects"
          ]
        }
      }
    }
  ]
}
```

Connection cloning alone needs no S3 access or job-update permissions, and needs
`glue:GetJob` only when using `--job-name`. Job migration uses no Secrets Manager
APIs; its connection/trigger reads are for best-effort snapshots. Job migration
always needs `datazone:ListConnections` and `datazone:GetConnection` to resolve the
project role, including with `--bucket` and on already-migrated jobs.
`datazone:GetEnvironment` is only needed for bucket resolution.
Rollback needs S3 read access to the snapshot plus Glue update/tag permissions.
Tag policies must allow restoration of the prior tag values.

The new caller permissions are `iam:GetRolePolicy` to check the project's grant,
`iam:PutRolePolicy` to create it on apply, and `iam:GetRole` when Glue supplies a
bare job role name. Include role paths in `<JOB_ROLE_NAME>` and
`<PROJECT_ROLE_NAME>` where applicable. Scope policy-write access to the intended
project roles: `iam:PutRolePolicy` permits changing those roles' inline policies.
Dry runs need the reads but not `iam:PutRolePolicy`. Connection cloning and
rollback do not need these additional IAM permissions. The grant does not bypass
permissions boundaries or organization policies, and creation fails if the
project role's inline-policy size quota is exhausted.

These DataZone actions require `Resource: "*"`; they do not support domain ARN
scoping. The examples restrict the requested Region, and project membership
remains required.

For discovery, add these statements. Use `--domain-id` to narrow the discovery
plan; this CLI filter is not an IAM access restriction. Applying matches also
requires the job migration permissions above for every target.

```json
[
  {
    "Effect": "Allow",
    "Action": ["datazone:ListDomains", "glue:GetJobs"],
    "Resource": "*",
    "Condition": {"StringEquals": {"aws:RequestedRegion": "<REGION>"}}
  },
  {
    "Effect": "Allow",
    "Action": ["datazone:ListProjects", "datazone:ListConnections", "datazone:GetConnection"],
    "Resource": "*",
    "Condition": {"StringEquals": {"aws:RequestedRegion": "<REGION>"}}
  }
]
```

Permissions for **runtime consumers** are separate. The job role must read the
copied script, and the project role must access connection secrets, KMS keys and
the data source's network. The migration tool does not grant these permissions.
SSE-KMS script copies require source-key decrypt access and destination-key
decrypt/data-key generation access. VPC connection creation may also require
permissions to manage network interfaces in the configured subnets and security
groups. Project membership remains required even when IAM allows DataZone APIs.

Developer test and CI setup instructions are in
[the Glue test README](../../.github/workflows/glue-migration-tests/README.md).
