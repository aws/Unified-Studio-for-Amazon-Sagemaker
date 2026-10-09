# PySpark engine version 3 to Apache Spark version 3.5 in Amazon Athena

## Overview

The Athena Spark notebook migration script migrates PySpark engine version 3 notebooks from [Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/what-is.html) workgroups into [Amazon SageMaker Unified Studio (SMUS)](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/what-is-sagemaker-unified-studio.html) projects.

For each notebook, the script:

1. Exports the notebook from Athena — the source notebook is never modified.
2. Clears cell outputs to stay within the SageMaker Unified Studio project import limits, and rewrites `%%sql` magics to `spark.sql(...)`.
3. Stages the Athena Notebook in the project's shared S3 location, imports it into the project, and waits until it is `ACTIVE`.

Before migrating, it checks that your identity can reach the source and destination. It also compares the Athena workgroup execution role with the SageMaker Unified Studio project execution role, and prints any permissions the project role is missing.

After migration, open each notebook in SageMaker Unified Studio and use the Data Agent to finish the upgrade to Apache Spark version 3.5.

## Prerequisites

- A SageMaker Unified Studio **domain** and **project** created and ready. See [Set up your domain as an administrator](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/gs-admin-setup.html).

  > **Note:** You will need both the **domain ID** and **project ID** as required inputs to the migration script. Find these on the Project Overview page. See [View project details](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/view-project-details.html).

- One or more Athena workgroups on **PySpark engine version 3** with notebooks you intend to migrate.

- **Python 3.10 or later** and **boto3 1.43.8 or newer** installed locally. The migration script is built with Python 3.10+ features and uses boto3 for AWS API calls.

- **AWS credentials.** Use `aws configure`, IAM Identity Center/SSO, an instance profile, or a named profile (`--profile`).

- **Project admin.** The identity running the script must be an **admin of the target project**. IAM permissions alone are not enough. Domain owner is not required.

- **IAM permissions.** The IAM user/role running the script must have the permissions listed in [IAM permissions](#iam-permissions).

- **Execution role.** The **SageMaker Unified Studio project execution role** must have the same data-access permissions (S3, Glue, Lake Formation, KMS) as your Athena workgroup execution role, because migrated notebooks run as the project role. The script checks identity policies for you; see [Execution role check](#execution-role-check).

## IAM permissions

The identity running the script needs the policy below. Replace the placeholders, and list each workgroup you migrate.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": "athena:ListWorkGroups", "Resource": "*"},
    {"Effect": "Allow",
     "Action": ["athena:GetWorkGroup", "athena:ListNotebookMetadata", "athena:ExportNotebook"],
     "Resource": ["arn:aws:athena:<region>:<account>:workgroup/<workgroup-name>"]},
    {"Effect": "Allow", "Action": "datazone:GetDomain",
     "Resource": "arn:aws:datazone:<region>:<account>:domain/<domain-id>"},
    {"Effect": "Allow",
     "Action": ["datazone:GetProject", "datazone:ListEnvironments", "datazone:GetEnvironment",
                "datazone:ListNotebooks", "datazone:GetNotebook", "datazone:StartNotebookImport",
                "datazone:DeleteNotebook", "datazone:ListConnections", "datazone:GetConnection"],
     "Resource": "*"},
    {"Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject"],
     "Resource": "arn:aws:s3:::amazon-sagemaker-<account>-<region>-<project-id>/shared/athena-migration/*"},
    {"Effect": "Allow",
     "Action": ["iam:ListRolePolicies", "iam:GetRolePolicy", "iam:ListAttachedRolePolicies",
                "iam:GetPolicy", "iam:GetPolicyVersion"],
     "Resource": "*"},
    {"Effect": "Allow", "Action": "sts:GetCallerIdentity", "Resource": "*"}
  ]
}
```

| Permission | Why |
|---|---|
| `athena:*` on the workgroups | Read and export the source notebooks. For `--all-workgroups`, use `workgroup/*`. |
| `datazone:*` | Validate the domain and project, find the staging bucket, import notebooks. `DeleteNotebook` is used by `--overwrite`; without it, overwrite leaves the old copy as a duplicate. `ListConnections` / `GetConnection` fill in the Spark workgroup in the banner. |
| `s3:PutObject`, `s3:GetObject` | Stage the notebook. `GetObject` is required because the import reads the staged file with your credentials. |
| `iam:List*` / `Get*` | Execution role check only (optional; the check is skipped without them). |
| `sts:GetCallerIdentity` | Confirm credentials before starting. |

This base policy covers one workgroup into one project. Each migration mode below shows the additional permissions it needs, if any.

## Usage

View all options:

```bash
python3 athena_notebook_migration.py -h
```

```text
usage: athena_notebook_migration.py [-h] [--domain-id DOMAIN_ID] [--project-id PROJECT_ID]
                                    [--workgroups WORKGROUPS [WORKGROUPS ...]] [--all-workgroups] [--config CONFIG]
                                    --region REGION [--profile PROFILE] [--role-arn ROLE_ARN]
                                    [--source-profile SOURCE_PROFILE] [--source-role-arn SOURCE_ROLE_ARN]
                                    [--source-region SOURCE_REGION] [--dry-run] [--overwrite] [--yes]
                                    [--concurrency CONCURRENCY] [--resume REPORT_JSON] [--name-filter NAME_FILTER]
                                    [--notebooks NOTEBOOKS] [--since SINCE]
                                    [--exclude-workgroups EXCLUDE_WORKGROUPS [EXCLUDE_WORKGROUPS ...]] [--inventory]
                                    [--log-level {DEBUG,INFO,WARNING,ERROR}] [--output-dir OUTPUT_DIR]
                                    [--log-file LOG_FILE] [--report-file REPORT_FILE]

Migrates notebooks from Amazon Athena PySpark engine version 3 workgroups to Amazon SageMaker Unified Studio projects.

options:
  -h, --help            show this help message and exit
  --domain-id DOMAIN_ID
                        SageMaker Unified Studio domain ID (e.g. dzd-xxxxx)
  --project-id PROJECT_ID
                        Target SageMaker Unified Studio project ID
  --workgroups WORKGROUPS [WORKGROUPS ...]
                        Athena workgroup name(s) to migrate
  --all-workgroups      Auto-discover and migrate ALL PySpark engine version 3 workgroups
  --config CONFIG       JSON config file mapping workgroups to project IDs (workgroup_project_map)
  --region REGION       Destination (SageMaker Unified Studio) region (required)
  --profile PROFILE     AWS profile for destination account
  --role-arn ROLE_ARN   IAM role ARN to assume for destination account
  --source-profile SOURCE_PROFILE
                        AWS profile for source (Athena) account
  --source-role-arn SOURCE_ROLE_ARN
                        IAM role ARN to assume for source account
  --source-region SOURCE_REGION
                        Source (Athena) region (defaults to --region)
  --dry-run             Preview only — no S3 writes, no imports
  --overwrite           Re-import notebooks that already exist in the project; the old copy is deleted only after the
                        new import succeeds
  --yes                 Skip interactive confirmation prompt
  --concurrency CONCURRENCY
                        Parallel notebook imports (default: 1, max: 10)
  --resume REPORT_JSON  Continue from a prior report JSON: skip notebooks it shows as migrated (if they still exist in
                        the project), retry the rest
  --name-filter NAME_FILTER
                        Case-insensitive notebook name filter: a substring (e.g. 'sales'), or a glob when it contains
                        * ? [ ] (e.g. 'retail*'). Not a regex.
  --notebooks NOTEBOOKS
                        Comma-separated Athena notebook IDs or exact notebook names to include
  --since SINCE         Only notebooks modified on/after this date (YYYY-MM-DD)
  --exclude-workgroups EXCLUDE_WORKGROUPS [EXCLUDE_WORKGROUPS ...]
                        Workgroup names to exclude
  --inventory           List workgroups and notebooks only; do not migrate
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Log verbosity (default: INFO)
  --output-dir OUTPUT_DIR
                        Directory for logs and reports (default: .)
  --log-file LOG_FILE   Override log file path
  --report-file REPORT_FILE
                        Override report base path

examples:
  # Discover what needs to be migrated
  athena_notebook_migration.py --inventory --region us-west-2

  # Preview migration (no changes made)
  athena_notebook_migration.py --dry-run --workgroups my-workgroup --domain-id dzd-xxx --project-id abc123 --region us-west-2

  # Migrate a single workgroup
  athena_notebook_migration.py --workgroups my-workgroup --domain-id dzd-xxx --project-id abc123 --region us-west-2

  # Migrate all workgroups in the account
  athena_notebook_migration.py --all-workgroups --domain-id dzd-xxx --project-id abc123 --region us-west-2

  # Multi-project migration via config file
  athena_notebook_migration.py --config map.json --region us-west-2
```

## Options

Type flag names in full, exactly as listed (for example `--notebooks`, `--overwrite`). Abbreviated prefixes like `--over` are not accepted.

**Required:**

| Flag | Description |
|---|---|
| `--domain-id DOMAIN_ID` | The SageMaker Unified Studio (DataZone) domain identifier. This is the `dzd-` prefixed ID shown on the Project Overview page. |
| `--project-id PROJECT_ID` | The target project within the SageMaker Unified Studio domain where notebooks will be imported. Find this in the Project Overview page. |
| `--workgroups NAME [NAME ...]` | One or more Athena Spark workgroup names to migrate. You can specify multiple names separated by spaces (e.g., `--workgroups analytics-wg ml-wg`). |
| `--region REGION` | The AWS Region where the destination SageMaker Unified Studio domain exists (e.g., `us-east-1`). |

> Instead of `--domain-id`, `--project-id`, and `--workgroups`, you can provide `--config FILE` to map multiple workgroups to different projects (see [Config file format](#config-file-format)).

**Optional:**

| Flag | Description |
|---|---|
| `--all-workgroups` | Automatically discovers and migrates all PySpark engine version 3 workgroups in the account. Workgroups the caller cannot access are skipped with a warning. |
| `--config FILE` | JSON file that maps workgroups to projects. Replaces `--project-id` and `--workgroups`, and `--domain-id` if the file sets `domain_id`. See [Config file format](#config-file-format). |
| `--profile PROFILE` | AWS named profile for the destination (SageMaker Unified Studio) account. Uses the default credential chain if not specified. |
| `--role-arn ROLE_ARN` | IAM role ARN to assume for destination (SageMaker Unified Studio) account operations. Use this for cross-account migrations where the domain is in a different account. |
| `--source-profile PROFILE` | AWS named profile for the source (Athena) account. Only needed when migrating across accounts. |
| `--source-role-arn ROLE_ARN` | IAM role ARN to assume for source (Athena) account operations. Use alongside `--role-arn` for full cross-account role chaining. |
| `--source-region REGION` | AWS Region where the source Athena workgroups reside. Defaults to `--region` if not specified. Required for cross-region migrations. |
| `--dry-run` | Validates credentials, permissions, and migration scope without actually exporting or importing anything. Use this to confirm everything is configured correctly before running the real migration. |
| `--overwrite` | Re-import notebooks that already exist in the project. The new copy is imported first, and the old copy is deleted only after the new one is `ACTIVE`. If the re-import fails, the old copy is kept. |
| `--yes` | Suppresses the interactive confirmation prompt before migration begins. Required for CI/CD pipelines and unattended execution. |
| `--resume FILE` | Path to a JSON report from a previous migration run. Skips notebooks the report shows as migrated (if they still exist in the project) and retries the rest. |
| `--name-filter TEXT` | Case-insensitive notebook name filter: a substring (e.g. `sales`), or a glob when it contains `*` `?` `[…]` (e.g. `retail*`). It is **not** a regular expression: `.` is a literal dot. If the value looks like a regex (`^`, `$`, `.*`), the script warns and suggests the matching `--notebooks` or glob form. |
| `--notebooks LIST` | Comma-separated Athena notebook **IDs or exact names** to include. Values that match nothing are listed as a warning. |
| `--since YYYY-MM-DD` | Only migrates notebooks last modified on or after this date. Useful for incremental migrations or recent-only transfers. |
| `--exclude-workgroups NAME [NAME ...]` | Workgroup names to exclude from migration. Most useful in combination with `--all-workgroups` to skip test or sandbox workgroups. |
| `--concurrency N` | Number of parallel notebook imports to run simultaneously (default: 1, max: 10). Higher values speed up large migrations but consume more API quota. |
| `--inventory` | Discovery-only mode. Lists all PySpark engine version 3 workgroups and their notebooks without performing any migration. Nothing is created or modified. |
| `--log-level LEVEL` | Logging verbosity: `DEBUG`, `INFO` (default), `WARNING`, or `ERROR`. Use `DEBUG` for troubleshooting failed imports. |
| `--output-dir PATH` | Directory where the script writes log files and JSON migration reports (default: current working directory). |
| `--log-file PATH` | Override log file path. |
| `--report-file PATH` | Override report base path (without `.json`). |

### Config file format

Map each Athena workgroup to its target project:

```json
{
  "domain_id": "<domain-id>",
  "workgroup_project_map": {
    "<workgroup-1>": "<project-id-1>",
    "<workgroup-2>": "<project-id-2>",
    "<workgroup-3>": "<project-id-1>"
  }
}
```

## Steps

### 1. Set up

```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -c "import boto3; print(boto3.__version__)"   # must be 1.43.8 or later

# Credentials for the account that owns the Athena workgroups and the SageMaker Unified Studio domain
aws sso login --profile <profile>           # or: aws configure / instance profile
aws sts get-caller-identity --profile <profile>   # optional: confirm the identity
```

Create (or pick) the SageMaker Unified Studio domain and project, note their IDs, and make sure your identity is an admin of the project. See [Prerequisites](#prerequisites).

### 2. Discover notebooks

List all Athena PySpark engine version 3 workgroups and their notebooks (read-only):

```bash
python3 athena_notebook_migration.py --inventory --region <region> --profile <profile>
```

<details>
<summary>IAM permissions for inventory mode</summary>

Only `athena:ListWorkGroups`, `athena:ListNotebookMetadata` and `sts:GetCallerIdentity`. To see **every** workgroup's notebooks, allow `athena:ListNotebookMetadata` on `workgroup/*`:

```json
{
  "Effect": "Allow",
  "Action": "athena:ListNotebookMetadata",
  "Resource": "arn:aws:athena:<region>:<account>:workgroup/*"
}
```

</details>

### 3. Preview the migration

Validate access, check the execution roles and show the plan, without making any changes:

```bash
python3 athena_notebook_migration.py --dry-run \
  --domain-id <domain-id> --project-id <project-id> \
  --workgroups <workgroup-name> --region <region> --profile <profile>
```

### 4. Migrate

#### Single workgroup into one project

Migrates every notebook in the workgroup. You're asked to confirm first; `--yes` skips the prompt.

```bash
python3 athena_notebook_migration.py \
  --domain-id <domain-id> --project-id <project-id> \
  --workgroups <workgroup-name> --region <region> --profile <profile> \
  --output-dir <output-dir>
```
---

#### Several workgroups into one project

```bash
python3 athena_notebook_migration.py --region <region> --domain-id <domain-id> --project-id <project-id> \
  --workgroups <workgroup-1> <workgroup-2>
```

<details>
<summary>Additional IAM permissions</summary>

List every workgroup in the Athena statement:

```json
{
  "Effect": "Allow",
  "Action": ["athena:GetWorkGroup", "athena:ListNotebookMetadata", "athena:ExportNotebook"],
  "Resource": [
    "arn:aws:athena:<region>:<account>:workgroup/<workgroup-1>",
    "arn:aws:athena:<region>:<account>:workgroup/<workgroup-2>"
  ]
}
```

</details>

---

#### All workgroups into one project

```bash
python3 athena_notebook_migration.py --region <region> --domain-id <domain-id> --project-id <project-id> \
  --all-workgroups --exclude-workgroups <excluded-workgroup-1> <excluded-workgroup-2> --yes
```

<details>
<summary>Additional IAM permissions</summary>

Allow every workgroup in the Athena statement:

```json
{
  "Effect": "Allow",
  "Action": ["athena:GetWorkGroup", "athena:ListNotebookMetadata", "athena:ExportNotebook"],
  "Resource": "arn:aws:athena:<region>:<account>:workgroup/*"
}
```

</details>

---

#### Different workgroups into different projects (config file)

```bash
python3 athena_notebook_migration.py --config <config-file> --region <region> --yes --output-dir <output-dir>
```

<details>
<summary>Additional IAM permissions</summary>

- **Athena:** each mapped workgroup in the Athena statement, as in [Several workgroups](#several-workgroups-into-one-project).
- **S3:** each project's staging bucket, because notebooks are staged in their own project's bucket.
- **Project admin:** your identity must be an admin of every target project.

```json
{
  "Effect": "Allow",
  "Action": ["s3:PutObject", "s3:GetObject"],
  "Resource": [
    "arn:aws:s3:::amazon-sagemaker-<account>-<region>-<project-id-1>/shared/athena-migration/*",
    "arn:aws:s3:::amazon-sagemaker-<account>-<region>-<project-id-2>/shared/athena-migration/*"
  ]
}
```

</details>

---

#### Only some notebooks (name, exact name or ID, date)

```bash
# Substring / glob filter
python3 athena_notebook_migration.py --region <region> --domain-id <domain-id> --project-id <project-id> \
  --workgroups <workgroup-name> --name-filter "<substring-or-glob>"

# Exact notebook IDs or names
python3 athena_notebook_migration.py --region <region> --domain-id <domain-id> --project-id <project-id> \
  --workgroups <workgroup-name> --notebooks "<notebook-name>,<notebook-id>"

# Date filter
python3 athena_notebook_migration.py --region <region> --domain-id <domain-id> --project-id <project-id> \
  --workgroups <workgroup-name> --since <YYYY-MM-DD>
```
---

#### Run imports in parallel

```bash
python3 athena_notebook_migration.py --region <region> --domain-id <domain-id> --project-id <project-id> \
  --workgroups <workgroup-name> --concurrency <1-10> --yes
```
---

#### Replace notebooks that were already migrated

```bash
python3 athena_notebook_migration.py --region <region> --domain-id <domain-id> --project-id <project-id> \
  --workgroups <workgroup-name> --overwrite
```
---

#### Cross-Region (Athena in one Region, SageMaker Unified Studio in another, same account)

```bash
python3 athena_notebook_migration.py --source-region <source-region> --region <region> \
  --domain-id <domain-id> --project-id <project-id> --workgroups <workgroup-name>
```

<details>
<summary>Additional IAM permissions</summary>

Use the **source** Region in the Athena workgroup ARNs:

```json
{
  "Effect": "Allow",
  "Action": ["athena:GetWorkGroup", "athena:ListNotebookMetadata", "athena:ExportNotebook"],
  "Resource": "arn:aws:athena:<source-region>:<account>:workgroup/<workgroup-name>"
}
```

</details>

---

#### Cross-account with named profiles

```bash
python3 athena_notebook_migration.py --source-profile <athena-account> --profile <smus-account> \
  --source-region <source-region> --region <region> \
  --domain-id <domain-id> --project-id <project-id> --workgroups <workgroup-name>
```

<details>
<summary>Additional IAM permissions</summary>

Split the [base policy](#iam-permissions) between the two accounts:
- **Source account identity (`--source-profile`):** the Athena statements, the IAM-read statement and `sts:GetCallerIdentity`.
- **Destination account identity (`--profile`):** the DataZone and S3 statements, the IAM-read statement and `sts:GetCallerIdentity`.

</details>

---

#### Cross-account with role assumption

```bash
python3 athena_notebook_migration.py \
  --source-role-arn arn:aws:iam::<source-account>:role/AthenaReadRole --source-region <source-region> \
  --role-arn arn:aws:iam::<dest-account>:role/SmusMigrateRole --region <region> \
  --domain-id <domain-id> --project-id <project-id> --workgroups <workgroup-name>
```

<details>
<summary>Additional IAM permissions</summary>

- **The two roles:** give `AthenaReadRole` the source statements and `SmusMigrateRole` the destination statements, as in the profiles example above.
- **The identity running the script:** needs `sts:AssumeRole` on both roles, and each role's trust policy must allow that identity.

```json
{
  "Effect": "Allow",
  "Action": "sts:AssumeRole",
  "Resource": [
    "arn:aws:iam::<source-account>:role/AthenaReadRole",
    "arn:aws:iam::<dest-account>:role/SmusMigrateRole"
  ]
}
```

</details>

---

#### SSE-KMS encrypted project bucket (any mode)

<details>
<summary>Additional IAM permissions</summary>

```json
{
  "Effect": "Allow",
  "Action": ["kms:GenerateDataKey", "kms:Decrypt"],
  "Resource": "arn:aws:kms:<region>:<account>:key/<project-bucket-key-id>"
}
```

</details>

### 5. Verify (and resume if needed)

- **Summary:** each notebook is shown as `✓ Success`, `Skip` or `✗ Fail`, followed by the report and log paths. The JSON report is also written to `--output-dir`.
- **Check the project:** open it in SageMaker Unified Studio and confirm the notebooks are listed.
- **Re-running is safe:** notebooks already in the project are skipped.
- **Resume:** if some notebooks failed or the run was interrupted, rerun the same command with the report it printed:

```bash
python3 athena_notebook_migration.py \
  --domain-id <domain-id> --project-id <project-id> \
  --workgroups <workgroup-name> --region <region> --profile <profile> \
  --resume <output-dir>/athena-smus-migration-report-<timestamp>.json
```

### 6. Upgrade the notebooks in SageMaker Unified Studio

Once the notebooks are imported into SageMaker Unified Studio, open each one and use the [Data Agent](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/sagemaker-data-agent.html) to fix and upgrade it so that it is compatible with Apache Spark version 3.5. The banner cell at the top of each imported notebook has a suggested prompt.

## What changes in the migrated notebook

- **Cell outputs:** outputs and execution counts are removed, so large notebooks stay within the [SageMaker Unified Studio import limits](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/export-share-notebooks.html). Code and markdown are unchanged, and outputs come back when you run the notebook.
- **`%%sql` cells:** a code cell that starts with the `%%sql` magic becomes `spark.sql("""<query>""").show()`, because SageMaker Unified Studio notebooks don't support Athena's `%%sql` magic. Empty cells, and cells whose query contains `"""`, are left as they are.
- **Other magics:** `%table`, `%matplot` and `%plotly` are left for the Data Agent to upgrade.
- **Migration banner:** a markdown cell (tagged `athena-smus-migration-banner`) is added at the top. It lists:
  - the source workgroup and target project;
  - the project's Athena Spark workgroup;
  - the source notebook ID and migration time;
  - a suggested Data Agent prompt for upgrading the notebook.

## Execution role check

Migration copies notebook **content only, not IAM**. In SageMaker Unified Studio the notebook runs as the **project execution role**. Anything the notebook used through the Athena workgroup role (S3 buckets, Glue tables, KMS keys) must also be allowed for the project role, or cells fail with `AccessDenied` when run.

Before migrating, the script compares the identity policies of the Athena PySpark engine version 3 workgroup execution role and the SageMaker Unified Studio project execution role. For example:

```text
⚠ Additional permissions required for SMUS project execution role (AmazonSageMakerUserIAMExecutionRole_abc123)

   The Athena workgroup execution role (AthenaSparkExecutionRole) used by
   workgroup(s) analytics-wg has the following permissions that the
   SMUS project execution role does not:

   Missing actions:
     ─ s3:GetObject
     ─ s3:PutObject
   On resources:
     ─ arn:aws:s3:::my-data-bucket/*

   To fix, run the following command (as the SMUS project admin):

     ┌──────────────────────────────────────────────────────────────┐
     │ aws iam put-role-policy \                                    │
     │   --role-name AmazonSageMakerUserIAMExecutionRole_abc123 \  │
     │   --policy-name athena-smus-migration-access \              │
     │   --policy-document '{ … }'                                 │
     └──────────────────────────────────────────────────────────────┘
```

- **Never blocking:** the check never blocks the migration. A reminder is repeated in the final summary.
- **Missing IAM read permission:** if your identity can't read the roles' policies, the check is skipped and the migration continues.
- **Scope:** it compares **identity policies only**. It does not see S3 bucket policies, KMS key policies or Lake Formation grants; check those separately.

## Reports and resume

Every run writes two files to `--output-dir`. Both paths are printed at the end of the run.

| File | Contents |
|---|---|
| `athena-smus-migration-report-<timestamp>.json` | One row per notebook: workgroup, Athena ID, SageMaker Unified Studio notebook ID, status, error detail, duration. **Rewritten after every notebook**, so it's usable even if the run is interrupted (`"complete": false`). |
| `athena-smus-migration-<timestamp>.log` | Detailed log of every step, including AWS error codes and request IDs. |

To continue after failures or an interruption (Ctrl-C, expired credentials, network loss), rerun the same command with the latest report:

```shell
python3 athena_notebook_migration.py <same options> --resume <output-dir>/athena-smus-migration-report-<timestamp>.json
```

- **Skipped:** notebooks the report shows as migrated, **as long as they still exist in the project**.
- **Migrated again:** notebooks deleted from SageMaker Unified Studio since the earlier run, failed notebooks, and notebooks never tried.
- **Resume chains:** you can resume from a report written by a resumed run.
- **Same-name notebooks:** a notebook that already exists in the project under the same name is always skipped, unless you pass `--overwrite`.
- **Interrupted `--overwrite`:** if you stop an `--overwrite` run while a notebook is importing, the project can end up with two copies of it (the new one imported, the old one not yet deleted). The next run lists these as `skip (exists, 2 copies)` with a warning; run again with `--overwrite` to keep a single fresh copy.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `AttributeError: 'DataZone' object has no attribute 'list_notebooks'` | boto3 version is too old. | Upgrade: `pip install 'boto3>=1.43.8'` |
| `AccessDeniedException` on `GetDomain` (HTTP 403) | Wrong `--region`. DataZone domains are regional resources. | Re-run with `--region` set to the domain's actual Region. |
| `ExpiredTokenException` or `InvalidClientTokenId` | AWS credentials have expired. | Run `aws sso login` (or refresh your credentials) and re-run. Add `--resume <report>.json` to continue from where you left off. |
| `AccessDeniedException` on `ExportNotebook` | Missing `athena:ExportNotebook` permission. | Add the workgroup ARN to your Athena IAM statement. |
| `AccessDeniedException` on `StartNotebookImport` | Not an admin of the target project. | Add your identity as a project admin in the SageMaker Unified Studio console. |
| `ERROR:AttributeError` during migration | Notebook content is not valid `.ipynb` JSON. | Skip the malformed notebook with `--notebooks` (exclude it) or fix it in Athena first. |
| Console garbled or logs show encoding errors (Windows) | Non-ASCII notebook names on Windows. | Set `PYTHONUTF8=1` before running. |
| Import stuck, then `TIMEOUT` | Import took longer than 120 seconds to reach `ACTIVE`. | Re-run with `--resume`. The notebook may still become `ACTIVE` asynchronously; re-running skips it once it does. |
| `--overwrite` reports success but old copy remains | Missing `datazone:DeleteNotebook` permission. | Grant the permission, or manually delete the duplicate from the SageMaker Unified Studio console. |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success, or nothing to do |
| `1` | One or more notebooks failed, or pre-migration validation failed |
| `2` | Invalid arguments or config file |
| `3` | Declined at the prompt, or interrupted |

## Known limitations

- **Same notebook name in two workgroups:** if both are migrated into one project, both are imported under the **same name**. Later runs can't tell them apart: both show `skip (exists)`, and `--overwrite` replaces them unpredictably. Route those workgroups to different projects.
- **Staging files are not deleted.** Remove them when you're done:
  ```shell
  aws s3 rm s3://amazon-sagemaker-<account>-<region>-<project-id>/shared/athena-migration/ --recursive
  ```
- **Malformed notebooks:** a notebook whose content isn't valid `.ipynb` fails with `ERROR:AttributeError`.
- **Overwrite without `datazone:DeleteNotebook`:** the old copy is kept as a duplicate, but the run still reports success; check the report's `detail` column.
- **No rollback:** delete migrated notebooks from the SageMaker Unified Studio project manually if needed.

## FAQ

**Are my Athena notebooks changed or deleted?**
No. The script only reads from Athena.

**Can I run it again safely?**
Yes. Notebooks already in the project are skipped, so re-running creates no duplicates. Use `--overwrite` to replace them with fresh copies.

**My run stopped halfway. What now?**
Rerun the same command with `--resume <latest report>.json`.

**Can I run it in CI/CD?**
Yes. Use `--yes` to skip the prompt, and `--config` to describe which workgroups go to which project.

**How long does each notebook take?**
Typically a few seconds per notebook. The script waits up to 120 seconds for each import to reach `ACTIVE` status, polling every 4 seconds.

**What if the same notebook name exists in two workgroups I'm migrating to one project?**
Both are imported under the same name. To avoid confusion, route them to different projects using `--config`.

## Related documentation

- [Amazon SageMaker Unified Studio](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/what-is-sagemaker-unified-studio.html)
- [Working with SageMaker Notebooks](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/notebooks.html)
- [Using the Data Agent](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/sagemaker-data-agent.html)
- [Use Apache Spark in Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/notebooks-spark.html)
- [Athena Spark release versions and properties](https://docs.aws.amazon.com/athena/latest/ug/notebooks-spark-release-versions.html)
- [Import and export notebooks](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/export-share-notebooks.html)
- [PySpark migration guide](https://spark.apache.org/docs/latest/api/python/migration_guide/pyspark_upgrade.html)
- [Spark SQL migration guide](https://spark.apache.org/docs/latest/sql-migration-guide.html)
