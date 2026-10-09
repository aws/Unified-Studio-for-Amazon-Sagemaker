"""Shared pytest fixtures for the cross-domain sync unit tests."""

import os
import sys

import pytest

# Make the lambda/ modules importable as top-level modules, mirroring the
# flat layout of the deployment package.
LAMBDA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lambda")
if LAMBDA_DIR not in sys.path:
    sys.path.insert(0, LAMBDA_DIR)

_BASE_ENV = {
    "SOURCE_ACCOUNT_ID": "111111111111",
    "SOURCE_DATABASE": "producer_db",
    "TARGET_DATABASE": "marketplace_db",
    "SOURCE_ROLE_ARN": "arn:aws:iam::111111111111:role/GlueFederationAccessRole",
    "SOURCE_DZ_ROLE_ARN": "arn:aws:iam::111111111111:role/DataZoneReaderRole",
    "SOURCE_DOMAIN_ID": "dzd-source",
    "SOURCE_PROJECT_ID": "prj-source",
    "DOMAIN_ID": "dzd-marketplace",
    "PROJECT_ID": "prj-marketplace",
    "ACCOUNT_ID": "222222222222",
    "PROJECT_ROLE_ARN": "arn:aws:iam::222222222222:role/datazone_usr_role",
}


@pytest.fixture
def base_env(monkeypatch):
    """Set a complete, valid environment for both Lambda modules."""
    for key, value in _BASE_ENV.items():
        monkeypatch.setenv(key, value)
    return dict(_BASE_ENV)
