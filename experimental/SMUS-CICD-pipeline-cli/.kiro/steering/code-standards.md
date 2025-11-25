# Code Standards and Best Practices

## PEP 8 Style Guide

**Follow PEP 8**: https://peps.python.org/pep-0008/
- Imports should be at the top of the file (after docstrings, before code)
- Use proper whitespace around operators
- Avoid unused imports and variables
- Use regular strings instead of f-strings when no placeholders are needed

## Linting Commands

**Always run linting checks after code changes:**
```bash
# Check code formatting and imports
flake8 src/smus_cicd/ --config=setup.cfg
black --check src/smus_cicd/
isort --check-only src/smus_cicd/

# Auto-fix formatting issues
black src/smus_cicd/
isort src/smus_cicd/
```

## DataZone API Patterns

- **Exception Handling**: DataZone helper functions should raise exceptions instead of returning None/False to ensure proper CLI exit codes
- **Pagination**: Always handle pagination when searching/listing resources - check for `nextToken` and iterate through all pages
- **Field Compatibility**: Handle both new and legacy API fields (e.g., `rolePrincipalArn` vs `groupName` for IAM role groups)
- boto3 DataZone client may use older service models missing newer fields

## Exception Handling

- Don't swallow exceptions - if an error is thrown, it must be logged or handled
- Ensure proper CLI exit codes for all error conditions

## Hardcoded Values Check

**Before committing, run:**
```bash
./tests/scripts/check-hardcoded-values.sh
```

**This checks for:**
- AWS Account IDs (12-digit numbers)
- Hardcoded AWS regions in code
- Hardcoded AWS endpoints
- IP addresses
- IAM role ARNs with account IDs
- S3 bucket names with account IDs
- Internal hostnames
- Email addresses

**How to fix issues:**
```python
# ❌ Bad - Hardcoded account ID
account_id = "123456789012"

# ✅ Good - Dynamic lookup
account_id = boto3.client('sts').get_caller_identity()['Account']

# ❌ Bad - Hardcoded region
region = "us-east-1"

# ✅ Good - Environment variable with default
region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

# ❌ Bad - Hardcoded endpoint
endpoint = "https://airflow-serverless.us-east-1.api.aws/"

# ✅ Good - Environment variable
endpoint = os.environ.get('AIRFLOW_SERVERLESS_ENDPOINT', 
                         f'https://airflow-serverless.{region}.api.aws/')
```
