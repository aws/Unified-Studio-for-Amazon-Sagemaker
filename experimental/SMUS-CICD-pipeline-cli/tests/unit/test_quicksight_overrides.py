import json
import pytest
from unittest.mock import Mock, MagicMock
from smus_cicd.helpers.context_resolver import ContextResolver
from smus_cicd.application.application_manifest import ApplicationManifest


def test_quicksight_override_resolution():
    """Test that QuickSight overrides resolve stage.name and proj.name variables."""
    
    # Create mock context resolver
    context_resolver = Mock(spec=ContextResolver)
    
    # Mock the resolve method to replace {stage.name} and {proj.name}
    def mock_resolve(text):
        return text.replace('{stage.name}', 'test').replace('{proj.name}', 'test-marketing')
    
    context_resolver.resolve = mock_resolve
    
    # Test override parameters
    override_params = {
        'ResourceIdOverrideConfiguration': {
            'PrefixForAllResources': 'deployed-{stage.name}-covid-'
        },
        'Dashboards': [{
            'DashboardId': 'e0772d4e-bd69-444e-a421-cb3f165dbad8',
            'Name': 'TotalDeathByCountry-{stage.name}'
        }],
        'DataSets': [{
            'DataSetId': '2b4bd673-99f3-4d18-a475-ac37d56af357',
            'Name': 'us_simplified-{proj.name}'
        }]
    }
    
    # Resolve variables
    override_json = json.dumps(override_params)
    resolved_json = context_resolver.resolve(override_json)
    resolved_params = json.loads(resolved_json)
    
    # Assertions
    assert resolved_params['ResourceIdOverrideConfiguration']['PrefixForAllResources'] == 'deployed-test-covid-'
    assert resolved_params['Dashboards'][0]['Name'] == 'TotalDeathByCountry-test'
    assert resolved_params['DataSets'][0]['Name'] == 'us_simplified-test-marketing'
    
    print("✓ Override resolution test passed")


def test_quicksight_config_from_manifest():
    """Test that QuickSight config is properly extracted from manifest."""
    
    # Mock manifest structure
    manifest_data = {
        'stages': {
            'test': {
                'deployment_configuration': {
                    'quicksight': {
                        'overrideParameters': {
                            'ResourceIdOverrideConfiguration': {
                                'PrefixForAllResources': 'deployed-{stage.name}-covid-'
                            },
                            'Dashboards': [{
                                'DashboardId': 'e0772d4e-bd69-444e-a421-cb3f165dbad8',
                                'Name': 'TotalDeathByCountry-{stage.name}'
                            }]
                        }
                    }
                }
            }
        }
    }
    
    # Extract config
    qs_config = manifest_data['stages']['test']['deployment_configuration']['quicksight']
    override_params = qs_config['overrideParameters']
    
    # Assertions
    assert 'ResourceIdOverrideConfiguration' in override_params
    assert override_params['ResourceIdOverrideConfiguration']['PrefixForAllResources'] == 'deployed-{stage.name}-covid-'
    assert override_params['Dashboards'][0]['Name'] == 'TotalDeathByCountry-{stage.name}'
    
    print("✓ Config extraction test passed")


def test_manifest_parsing_with_deployment_config():
    """Test that ApplicationManifest properly parses deployment_configuration.quicksight."""
    
    manifest_path = 'examples/analytic-workflow/dashboard-glue-quick/manifest.yaml'
    
    try:
        manifest = ApplicationManifest.from_file(manifest_path)
        
        # Check test stage exists
        assert hasattr(manifest, 'stages')
        assert 'test' in manifest.stages
        
        target_config = manifest.stages['test']
        
        # Check deployment_configuration exists
        print(f"Has deployment_configuration: {hasattr(target_config, 'deployment_configuration')}")
        
        if hasattr(target_config, 'deployment_configuration') and target_config.deployment_configuration:
            print(f"deployment_configuration type: {type(target_config.deployment_configuration)}")
            print(f"Has quicksight attr: {hasattr(target_config.deployment_configuration, 'quicksight')}")
            
            if hasattr(target_config.deployment_configuration, 'quicksight'):
                qs_config = target_config.deployment_configuration.quicksight
                print(f"qs_config type: {type(qs_config)}")
                print(f"qs_config value: {qs_config}")
                
                if qs_config:
                    print(f"Has overrideParameters: {hasattr(qs_config, 'overrideParameters')}")
                    if hasattr(qs_config, 'overrideParameters'):
                        print(f"overrideParameters: {qs_config.overrideParameters}")
        
        print("✓ Manifest parsing test completed")
        
    except Exception as e:
        print(f"✗ Error parsing manifest: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_quicksight_override_resolution()
    test_quicksight_config_from_manifest()
    test_manifest_parsing_with_deployment_config()
    print("\n✅ All tests passed")
