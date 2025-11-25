"""Unit tests for QuickSight schema validation."""

import unittest
from pathlib import Path

import yaml
from jsonschema import validate, ValidationError


class TestQuickSightSchemaValidation(unittest.TestCase):
    """Test QuickSight schema validation for assets field."""

    def setUp(self):
        """Load schema before each test."""
        schema_path = (
            Path(__file__).parent.parent.parent
            / "src/smus_cicd/application/application-manifest-schema.yaml"
        )
        with open(schema_path) as f:
            self.schema = yaml.safe_load(f)

    def test_quicksight_assets_field_valid(self):
        """Test that 'assets' field is accepted in quicksight deployment_configuration."""
        manifest = {
            "applicationName": "TestApp",
            "content": {},
            "stages": {
                "test": {
                    "stage": "TEST",
                    "domain": {"region": "us-east-1"},
                    "project": {"name": "test-project"},
                    "deployment_configuration": {
                        "quicksight": {
                            "assets": [
                                {
                                    "name": "TotalDeathByCountry",
                                    "owners": ["arn:aws:quicksight:us-east-1:123:user/default/Admin/*"],
                                    "viewers": ["arn:aws:quicksight:us-east-1:123:user/default/User/*"],
                                }
                            ]
                        }
                    },
                }
            },
        }

        # This should NOT raise ValidationError
        try:
            validate(instance=manifest, schema=self.schema)
        except ValidationError as e:
            self.fail(f"Schema validation failed for 'assets' field: {e.message}")

    def test_quicksight_items_field_invalid(self):
        """Test that 'items' field is rejected (old field name)."""
        manifest = {
            "applicationName": "TestApp",
            "content": {},
            "stages": {
                "test": {
                    "stage": "TEST",
                    "domain": {"region": "us-east-1"},
                    "project": {"name": "test-project"},
                    "deployment_configuration": {
                        "quicksight": {
                            "items": [
                                {
                                    "name": "TotalDeathByCountry",
                                    "owners": ["arn:aws:quicksight:us-east-1:123:user/default/Admin/*"],
                                }
                            ]
                        }
                    },
                }
            },
        }

        # This SHOULD raise ValidationError
        with self.assertRaises(ValidationError) as context:
            validate(instance=manifest, schema=self.schema)

        self.assertIn("items", str(context.exception))


if __name__ == "__main__":
    unittest.main()
