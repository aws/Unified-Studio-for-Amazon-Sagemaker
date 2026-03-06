# Account Pool Factory - Security Guide

## Security Architecture

The Account Pool Factory implements three security controls:

1. **Separation of Duties**: Organizations API access isolated in Org Admin account
2. **Confused Deputy Protection**: ExternalId required for cross-account role assumptions
3. **Least Privilege**: Each Lambda has minimum permissions for its function

## Confused Deputy Protection

### The Problem

Without ExternalId, an attacker could trick Pool Manager into provisioning accounts:

```
Attacker → Invokes Pool Manager → Pool Manager assumes role in Org Admin → Creates accounts ✗
```

### The Solution - ExternalId in Trust Policies

Setup Orchestrator uses ExternalId when assuming SMUS-AccountPoolFactory-DomainAccess role in project accounts:

```python
# From setup-orchestrator/lambda_function.py
def get_cross_account_client(service: str, account_id: str, config: Dict[str, Any] = None):
    role_arn = f"arn:aws:iam::{account_id}:role/SMUS-AccountPoolFactory-DomainAccess"
    domain_id = config.get('DomainId', DOMAIN_ID)
    
    assumed_role = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName=f'SetupOrchestrator-{service}',
        ExternalId=domain_id,  # ← ExternalId prevents confused deputy
        DurationSeconds=3600
    )
```

Trust policy in project accounts requires matching ExternalId:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::DOMAIN_ACCOUNT:root"
    },
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {
        "sts:ExternalId": "DOMAIN_ID"
      }
    }
  }]
}
```

**ExternalId Value**: DataZone Domain ID (stored in environment variable)

**Where ExternalId is Used**:
- Setup Orchestrator → SMUS-AccountPoolFactory-DomainAccess role (project accounts)

**Where ExternalId is NOT Used**:
- ProvisionAccount Lambda → OrganizationAccountAccessRole (same account)
- Pool Manager → ProvisionAccount Lambda (resource-based policy instead)

## IAM Roles by Account

### Organization Admin Account

**ProvisionAccount Lambda Role**

Why: Only Lambda with Organizations API access. Isolated to prevent Setup Orchestrator from creating accounts.

Key permissions:
- `organizations:CreateAccount` - Create new AWS accounts
- `organizations:MoveAccount` - Move accounts to target OU
- `sts:AssumeRole` - Assume OrganizationAccountAccessRole in new accounts
- `cloudformation:CreateStackInstances` - Deploy StackSets to new accounts

Invocation control:
```json
{
  "Principal": {
    "AWS": "arn:aws:iam::DOMAIN_ACCOUNT:role/SMUS-AccountPoolFactory-PoolManager-Role"
  },
  "Action": "lambda:InvokeFunction"
}
```

Why no ExternalId: Lambda runs in same account as Organizations API, no cross-account risk.

### Domain Account

**Pool Manager Lambda Role**

Why: Orchestrates pool operations, delegates account creation to ProvisionAccount.

Key permissions:
- `lambda:InvokeFunction` - Invoke ProvisionAccount and SetupOrchestrator
- `dynamodb:Query|PutItem|UpdateItem|DeleteItem` - Manage account state
- `sts:AssumeRole` - Assume OrganizationAccountAccessRole for stack verification only

Why no Organizations API: Delegates to ProvisionAccount Lambda for separation of duties.

**Setup Orchestrator Lambda Role**

Why: Configures project accounts with DataZone resources.

Key permissions:
- `sts:AssumeRole` - Assume SMUS-AccountPoolFactory-DomainAccess with ExternalId
- `dynamodb:Query|PutItem|UpdateItem` - Track setup progress

Why ExternalId required: All project account operations go through SMUS-AccountPoolFactory-DomainAccess role.

**Account Provider Lambda Role**

Why: Returns available accounts to SMUS API.

Key permissions:
- `dynamodb:Query` - Read-only access to account state

Why most restrictive: No cross-account access, no write operations.

### Project Account

**SMUS-AccountPoolFactory-DomainAccess Role**

Created by: ProvisionAccount Lambda via StackSet during provisioning.

Trust policy with ExternalId:
```json
{
  "Principal": {
    "AWS": "arn:aws:iam::DOMAIN_ACCOUNT:root"
  },
  "Action": "sts:AssumeRole",
  "Condition": {
    "StringEquals": {
      "sts:ExternalId": "DOMAIN_ID"
    }
  }
}
```

Key permissions:
- `cloudformation:CreateStack|DescribeStacks|DeleteStack` - Deploy DataZone stacks
- `datazone:*` - Configure DataZone domain access
- `ec2:*` - Create VPC for DataZone environments
- `s3:CreateBucket` - Create blueprint artifact bucket
- `ram:CreateResourceShare` - Share domain with project account
- `iam:CreateRole|PassRole` - Create DataZone service roles

Why ExternalId: Prevents confused deputy - Setup Orchestrator must know secret ExternalId to assume role.

## Related Documentation

- [Architecture Guide](Architecture.md) - System architecture and component interactions
