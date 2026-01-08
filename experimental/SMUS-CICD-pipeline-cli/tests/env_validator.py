#!/usr/bin/env python3
"""Environment variable validation for integration tests."""

import os
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class EnvVarRequirement:
    """Represents an environment variable requirement."""
    name: str
    description: str
    required: bool = True
    default: Optional[str] = None
    validation_func: Optional[callable] = None


class EnvironmentValidator:
    """Validates environment variables for integration tests."""
    
    # Core AWS configuration
    REQUIRED_ENV_VARS = [
        EnvVarRequirement(
            "AWS_ACCOUNT_ID",
            "AWS Account ID (12-digit number)",
            validation_func=lambda x: x.isdigit() and len(x) == 12
        ),
        EnvVarRequirement(
            "AWS_DEFAULT_REGION",
            "Default AWS region (e.g., us-east-1, us-east-2)",
            default="us-east-1"
        ),
        EnvVarRequirement(
            "DEV_DOMAIN_REGION", 
            "DataZone domain region for dev environment",
            default="us-east-2"
        ),
        EnvVarRequirement(
            "TEST_DOMAIN_REGION",
            "DataZone domain region for test environment", 
            default="us-east-2"
        ),
    ]
    
    # DataZone configuration
    DATAZONE_ENV_VARS = [
        EnvVarRequirement(
            "DATAZONE_DOMAIN_NAME",
            "DataZone domain name (e.g., Default_12022025_Domain)"
        ),
        EnvVarRequirement(
            "DATAZONE_DOMAIN_ID", 
            "DataZone domain ID (e.g., dzd_abc123def456)",
            required=False  # Can be derived from domain name
        ),
        EnvVarRequirement(
            "DATAZONE_PROJECT_NAME_DEV",
            "DataZone project name for dev environment",
            default="dev-marketing"
        ),
        EnvVarRequirement(
            "DATAZONE_PROJECT_NAME_TEST", 
            "DataZone project name for test environment",
            default="test-marketing"
        ),
        EnvVarRequirement(
            "DATAZONE_PROJECT_ID_DEV",
            "DataZone project ID for dev environment",
            required=False  # Can be derived from project name
        ),
        EnvVarRequirement(
            "DATAZONE_PROJECT_ID_TEST",
            "DataZone project ID for test environment", 
            required=False  # Can be derived from project name
        ),
    ]
    
    # MLflow configuration
    MLFLOW_ENV_VARS = [
        EnvVarRequirement(
            "MLFLOW_TRACKING_SERVER_NAME",
            "MLflow tracking server name (e.g., smus-integration-mlflow-use2)"
        ),
    ]
    
    # Optional AWS service endpoints
    OPTIONAL_ENV_VARS = [
        EnvVarRequirement(
            "DATAZONE_ENDPOINT_URL",
            "Custom DataZone endpoint URL",
            required=False
        ),
        EnvVarRequirement(
            "AWS_ENDPOINT_URL_DATAZONE", 
            "AWS DataZone endpoint URL",
            required=False
        ),
        EnvVarRequirement(
            "AIRFLOW_SERVERLESS_ENDPOINT",
            "Airflow Serverless endpoint URL",
            required=False
        ),
    ]
    
    @classmethod
    def get_all_requirements(cls) -> List[EnvVarRequirement]:
        """Get all environment variable requirements."""
        return (
            cls.REQUIRED_ENV_VARS + 
            cls.DATAZONE_ENV_VARS + 
            cls.MLFLOW_ENV_VARS + 
            cls.OPTIONAL_ENV_VARS
        )
    
    @classmethod
    def validate_environment(cls, strict: bool = True) -> Tuple[bool, List[str], List[str]]:
        """
        Validate environment variables.
        
        Args:
            strict: If True, fail on any missing required variables
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check AWS credentials first
        aws_creds_valid, aws_errors = cls._validate_aws_credentials()
        if not aws_creds_valid:
            errors.extend(aws_errors)
        
        # Validate all environment variables
        for req in cls.get_all_requirements():
            value = os.environ.get(req.name)
            
            if value is None:
                if req.required:
                    if req.default:
                        warnings.append(
                            f"⚠️  {req.name} not set, using default: {req.default}"
                        )
                        os.environ[req.name] = req.default
                    else:
                        errors.append(
                            f"❌ Missing required environment variable: {req.name}\n"
                            f"   Description: {req.description}"
                        )
                else:
                    warnings.append(
                        f"ℹ️  Optional variable {req.name} not set: {req.description}"
                    )
            else:
                # Validate value if validation function provided
                if req.validation_func and not req.validation_func(value):
                    errors.append(
                        f"❌ Invalid value for {req.name}: {value}\n"
                        f"   Description: {req.description}"
                    )
        
        is_valid = len(errors) == 0 or not strict
        return is_valid, errors, warnings
    
    @classmethod
    def _validate_aws_credentials(cls) -> Tuple[bool, List[str]]:
        """Validate AWS credentials are available."""
        errors = []
        
        # Check for AWS credentials
        has_profile = bool(os.environ.get("AWS_PROFILE"))
        has_keys = bool(
            os.environ.get("AWS_ACCESS_KEY_ID") and 
            os.environ.get("AWS_SECRET_ACCESS_KEY")
        )
        
        if not (has_profile or has_keys):
            errors.append(
                "❌ No AWS credentials found. Set either:\n"
                "   - AWS_PROFILE environment variable, or\n" 
                "   - AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
            )
        
        # Try to validate credentials with STS
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            sts = boto3.client("sts")
            identity = sts.get_caller_identity()
            
            # Extract account ID and set if not already set
            account_id = identity.get("Account")
            if account_id and not os.environ.get("AWS_ACCOUNT_ID"):
                os.environ["AWS_ACCOUNT_ID"] = account_id
                
        except (ClientError, NoCredentialsError) as e:
            errors.append(f"❌ AWS credential validation failed: {str(e)}")
        except Exception as e:
            errors.append(f"❌ Unexpected error validating AWS credentials: {str(e)}")
        
        return len(errors) == 0, errors
    
    @classmethod
    def print_validation_report(cls, errors: List[str], warnings: List[str]) -> None:
        """Print a formatted validation report."""
        print("\n" + "=" * 80)
        print("🔍 ENVIRONMENT VARIABLE VALIDATION REPORT")
        print("=" * 80)
        
        if errors:
            print(f"\n❌ ERRORS ({len(errors)}):")
            for error in errors:
                print(f"  {error}")
        
        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for warning in warnings:
                print(f"  {warning}")
        
        if not errors and not warnings:
            print("\n✅ All environment variables are properly configured!")
        
        print("\n" + "=" * 80)
    
    @classmethod
    def generate_env_template(cls, output_file: str = "env-template.env") -> None:
        """Generate an environment template file."""
        with open(output_file, "w") as f:
            f.write("# Environment variables for SMUS CI/CD Integration Tests\n")
            f.write("# Copy this file to env-local.env and customize for your account\n\n")
            
            # Group variables by category
            categories = [
                ("AWS Configuration", cls.REQUIRED_ENV_VARS),
                ("DataZone Configuration", cls.DATAZONE_ENV_VARS), 
                ("MLflow Configuration", cls.MLFLOW_ENV_VARS),
                ("Optional Service Endpoints", cls.OPTIONAL_ENV_VARS),
            ]
            
            for category_name, vars_list in categories:
                f.write(f"# {category_name}\n")
                for req in vars_list:
                    if req.default:
                        f.write(f"export {req.name}={req.default}  # {req.description}\n")
                    else:
                        f.write(f"export {req.name}=  # {req.description}\n")
                f.write("\n")
            
            f.write("# Usage:\n")
            f.write("# source env-local.env\n")
            f.write("# python tests/run_tests.py --type integration\n")


def main():
    """CLI entry point for environment validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate environment variables for integration tests")
    parser.add_argument("--strict", action="store_true", help="Fail on any missing required variables")
    parser.add_argument("--generate-template", help="Generate environment template file")
    parser.add_argument("--quiet", action="store_true", help="Only show errors")
    
    args = parser.parse_args()
    
    if args.generate_template:
        EnvironmentValidator.generate_env_template(args.generate_template)
        print(f"✅ Environment template generated: {args.generate_template}")
        return 0
    
    is_valid, errors, warnings = EnvironmentValidator.validate_environment(strict=args.strict)
    
    if not args.quiet:
        EnvironmentValidator.print_validation_report(errors, warnings)
    
    if not is_valid:
        if not args.quiet:
            print("\n💡 To fix these issues:")
            print("1. Run: python tests/env_validator.py --generate-template env-local.env")
            print("2. Edit env-local.env with your account-specific values")
            print("3. Run: source env-local.env")
            print("4. Re-run the tests")
        return 1
    
    if not args.quiet:
        print("\n✅ Environment validation passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())