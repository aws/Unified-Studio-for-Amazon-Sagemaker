# Account Pool Factory - AI Rules

## AWS Account Mapping

| Alias | Account | Role |
|-------|---------|------|
| amirbo+1 | 495869084367 | Org Admin (AWS Organizations) |
| amirbo+3 | 994753223772 | Domain (DataZone / SageMaker Unified Studio) |

## Credential Switching

Use Isengard CLI to switch between accounts:
```bash
# Org Admin account
eval $(isengardcli credentials amirbo+1@amazon.com)

# Domain account
eval $(isengardcli credentials amirbo+3@amazon.com)
```

## Key Resource IDs

- DataZone Domain ID: `dzd-4h7jbz76qckoh5`
- Root Domain Unit ID: `bsmdc8e4dwye5l`
- Region: `us-east-2`
- DynamoDB table: `AccountPoolFactory-AccountState` (composite key: accountId + timestamp)
- AccountProvider Lambda handler: `lambda_function_prod.lambda_handler`

## Development Rules

- Don't make assumptions — read the code first and understand how it's done
- Don't put text on console — use script files
- Check what already exists before creating new scripts
- Only update IAM roles through CloudFormation templates, not directly
- Create throwaway/debug scripts in `/tmp`, not in the project
- macOS ships with bash 3 — don't use `declare -A` (associative arrays), use temp files instead
- Template 03 (domain-access-stackset.yaml) is a StackSet template body referenced by deploy script 02, not a standalone CF stack
- Explain your plan before executing
- if you working on AccountPoolFactory use experimental/AccountPoolFactory/.kiro for your specs and steering files. 
