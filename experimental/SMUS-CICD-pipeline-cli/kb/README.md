# Knowledge Base Management

This directory contains scripts and configuration for the SMUS CLI Knowledge Base.

## Current Architecture (Private Bucket)

**Note:** Using private buckets for now. Will migrate to public bucket after company approval.

```
User's Account:
s3://smus-cli-kb-{account-id}/
├── docs/              # Synced from package docs/
└── examples/          # Synced from package examples/

Bedrock Knowledge Base → Points to user's private bucket
```

## For Users

### Setup Knowledge Base

First time only:

```bash
smus-cli kb setup
```

This creates:
1. S3 bucket: `s3://smus-cli-kb-{your-account-id}/`
2. Syncs docs and examples from the package
3. Creates Bedrock Knowledge Base pointing to your bucket
4. Creates OpenSearch Serverless collection for vectors

### Sync with Latest Docs

After updating the smus-cli package:

```bash
smus-cli kb sync
```

This re-syncs docs/examples from the package to your S3 bucket and triggers KB ingestion.

### Use the Agent

```bash
smus-cli chat
```

The agent automatically uses your Knowledge Base for enhanced search.

## Future: Public Bucket Architecture

After company approval, we'll migrate to:

```
Public S3 (SMUS Team):
s3://smus-cli-public-kb/
├── docs/              # Maintained by SMUS team
└── examples/          # Updated via CI/CD

User's Account:
Bedrock Knowledge Base → Points to public S3 (read-only)
```

Benefits:
- No S3 costs for users
- Always up-to-date docs
- Centrally maintained by SMUS team

## Files

- `sync-public-kb.sh` - Future: SMUS team script (not used yet)
- `templates/` - Jinja2 templates for workflow generation (future)
- `README.md` - This file

## Notes

- Currently each user has their own private S3 bucket
- Docs are synced from the installed package
- No file duplication in repo - docs stay in `docs/`, examples in `examples/`
- KB auto-creates on first `smus-cli chat` run

