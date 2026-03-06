---
inclusion: auto
---

# AWS Credentials Management

## Using Isengard CLI

For Amazon internal accounts, use `isengardcli` to get temporary credentials:

```bash
# Domain account (amirbo+3 = 994753223772)
eval $(isengardcli credentials amirbo+3@amazon.com)

# Org Admin account (amirbo+1 = 495869084367)
eval $(isengardcli credentials amirbo+1@amazon.com)

# Test project accounts
eval $(isengardcli credentials amirbo+100@amazon.com)  # 004878717744
eval $(isengardcli credentials amirbo+101@amazon.com)  # 236580259199
```

## Account Mapping

- `amirbo+1` = Org Admin Account (495869084367)
- `amirbo+3` = Domain Account (994753223772)
- `amirbo+100` = Test Project Account 1 (004878717744)
- `amirbo+101` = Test Project Account 2 (236580259199)

## Before Running Scripts

Always verify you're in the correct account:

```bash
aws sts get-caller-identity
```

## Clearing Credentials

To clear temporary credentials:

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
```

## Script Pattern

```bash
#!/bin/bash
# Clear any stale credentials
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

# Get fresh credentials for the account you need
eval $(isengardcli credentials amirbo+3@amazon.com)

# Verify
aws sts get-caller-identity
```
