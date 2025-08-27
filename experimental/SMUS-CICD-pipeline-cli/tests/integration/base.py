"""Base class for integration tests."""
import os
import yaml
import boto3
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from typer.testing import CliRunner
from smus_cicd.cli import app

class IntegrationTestBase:
    """Base class for integration tests with AWS setup and cleanup."""
    
    def _load_config(self) -> Dict[str, Any]:
        """Load integration test configuration."""
        config_path = Path(__file__).parent / "config.local.yaml"
        if not config_path.exists():
            config_path = Path(__file__).parent / "config.yaml"
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def setup_aws_session(self):
        """Set up AWS session with current credentials."""
        # Use current session credentials instead of profile
        aws_config = self.config.get('aws', {})
        
        if aws_config.get('region'):
            os.environ['AWS_DEFAULT_REGION'] = aws_config['region']
        
        # Ensure current role is Lake Formation admin
        self.setup_lake_formation_admin()
    
    def setup_lake_formation_admin(self):
        """Ensure current role is a Lake Formation admin (idempotent)."""
        try:
            import boto3
            
            lf_client = boto3.client('lakeformation', region_name=self.config.get('aws', {}).get('region', 'us-east-1'))
            sts_client = boto3.client('sts', region_name=self.config.get('aws', {}).get('region', 'us-east-1'))
            
            # Get current identity
            identity = sts_client.get_caller_identity()
            assumed_role_arn = identity['Arn']
            
            # Extract the role ARN from assumed role ARN
            # Format: arn:aws:sts::account:assumed-role/RoleName/SessionName
            # We want: arn:aws:iam::account:role/RoleName
            if 'assumed-role' in assumed_role_arn:
                parts = assumed_role_arn.split('/')
                if len(parts) >= 3:
                    account_and_service = parts[0].replace(':sts:', ':iam:').replace(':assumed-role', ':role')
                    role_name = parts[1]
                    role_arn = f"{account_and_service}/{role_name}"
                else:
                    role_arn = assumed_role_arn
            else:
                role_arn = assumed_role_arn
            
            # Get current Lake Formation settings
            try:
                current_settings = lf_client.get_data_lake_settings()
                current_admins = current_settings.get('DataLakeSettings', {}).get('DataLakeAdmins', [])
                
                # Check if role ARN is already an admin
                admin_arns = [admin.get('DataLakePrincipalIdentifier') for admin in current_admins]
                
                if role_arn not in admin_arns:
                    # Add role ARN to existing admins
                    current_admins.append({'DataLakePrincipalIdentifier': role_arn})
                    
                    lf_client.put_data_lake_settings(
                        DataLakeSettings={
                            'DataLakeAdmins': current_admins
                        }
                    )
                    print(f"✅ Added {role_arn} as Lake Formation admin")
                else:
                    print(f"✅ {role_arn} is already a Lake Formation admin")
                    
            except Exception as e:
                print(f"⚠️ Lake Formation admin setup: {e}")
                
        except Exception as e:
            print(f"⚠️ Lake Formation setup failed: {e}")
    
    def setup_test_directory(self):
        """Create temporary test directory."""
        self.test_dir = tempfile.mkdtemp(prefix="smus_integration_test_")
        return self.test_dir
    
    def cleanup_test_directory(self):
        """Clean up temporary test directory."""
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def get_pipeline_path(self, pipeline_file: str) -> str:
        """Get full path to pipeline file."""
        return str(Path(__file__).parent / pipeline_file)
    
    def run_cli_command(self, command: list, expected_exit_code: int = 0) -> Dict[str, Any]:
        """Run CLI command and return result with validation."""
        result = self.runner.invoke(app, command)
        
        return {
            'exit_code': result.exit_code,
            'stdout': result.stdout,
            'output': result.output,
            'success': result.exit_code == expected_exit_code,
            'command': ' '.join(command)
        }
    
    def verify_aws_connectivity(self) -> bool:
        """Verify AWS connectivity and permissions."""
        try:
            # Use current session credentials, not profile-based
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            
            # Basic STS access is sufficient for most tests
            # DataZone access is optional and may not be available in all environments
            try:
                datazone = boto3.client('datazone', region_name=self.config['aws']['region'])
                domains = datazone.list_domains(maxResults=1)
            except Exception as datazone_error:
                # DataZone access not available, but STS works, so continue
                print(f"DataZone access not available (this is OK): {datazone_error}")
            
            return True
        except Exception as e:
            print(f"AWS connectivity check failed: {e}")
            return False
    
    def check_domain_exists(self, domain_name: str) -> bool:
        """Check if DataZone domain exists."""
        try:
            datazone = boto3.client('datazone', region_name=self.config['aws']['region'])
            domains = datazone.list_domains()
            
            for domain in domains.get('items', []):
                if domain.get('name') == domain_name:
                    return True
            return False
        except Exception:
            return False
    
    def check_project_exists(self, domain_name: str, project_name: str) -> bool:
        """Check if DataZone project exists."""
        try:
            from smus_cicd import datazone as dz_utils
            domain_id = dz_utils.get_domain_id_by_name(domain_name, self.config['aws']['region'])
            if not domain_id:
                return False
            
            project_id = dz_utils.get_project_id_by_name(project_name, domain_id, self.config['aws']['region'])
            return project_id is not None
        except Exception:
            return False
    
    def cleanup_resources(self):
        """Clean up created AWS resources if configured."""
        if not self.config.get('test_environment', {}).get('cleanup_after_tests', True):
            return
        
        # Cleanup logic would go here
        # For now, just log what would be cleaned up
        if self.created_resources:
            print(f"Would clean up resources: {self.created_resources}")
    
    def generate_test_report(self, test_name: str, results: list) -> Dict[str, Any]:
        """Generate test report."""
        total_commands = len(results)
        successful_commands = sum(1 for r in results if r['success'])
        
        return {
            'test_name': test_name,
            'total_commands': total_commands,
            'successful_commands': successful_commands,
            'success_rate': successful_commands / total_commands if total_commands > 0 else 0,
            'overall_success': successful_commands == total_commands,
            'results': results
        }
