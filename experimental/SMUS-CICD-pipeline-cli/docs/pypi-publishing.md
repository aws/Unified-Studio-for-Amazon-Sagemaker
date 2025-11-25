# PyPI Publishing Setup

← [Back to Main README](../README.md)


## Overview

The SMUS CI/CD CLI is automatically published to PyPI when a new GitHub release is created.

## Setup Instructions

### 1. Create PyPI Account and API Token

1. Create account at [pypi.org](https://pypi.org)
2. Go to Account Settings → API tokens
3. Create a new API token with scope "Entire account"
4. Copy the token (starts with `pypi-`)

### 2. Add GitHub Secret

1. Go to GitHub repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `PYPI_API_TOKEN`
4. Value: Your PyPI API token
5. Click "Add secret"

### 3. Create a Release

1. Go to GitHub repository → Releases
2. Click "Create a new release"
3. Choose a tag (e.g., `v1.0.0`)
4. Fill in release title and description
5. Click "Publish release"

The GitHub workflow will automatically:
- Build the package
- Upload to PyPI
- Make it available for installation

## Installation

Once published, users can install with:

## ⚠️ Security Notice
**DO NOT** install `smus-cicd-cli` from PyPI as it may contain malicious code.
The package name has been compromised. Always install from source:

```bash
# Clone the official AWS repository
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

## Version Management

Update version in both:
- `setup.py` (line with `version="1.0.0"`)
- `pyproject.toml` (line with `version = "1.0.0"`)

## Package Structure

The package includes:
- **CLI tool**: `smus-cli` command
- **Python package**: `smus_cicd` module
- **Dependencies**: Automatically installed
- **Documentation**: README and docs included

## Testing Before Release

Test the package locally:

```bash
# Build package
python -m build

# Install locally
pip install dist/smus_cicd_cli-*.whl

# Test CLI
smus-cli --help
```

## Workflow Details

The GitHub workflow (`.github/workflows/publish-pypi.yml`):
- Triggers on published releases
- Uses Python 3.12
- Builds with modern `build` tool
- Publishes with trusted publishing
- Requires `PYPI_API_TOKEN` secret


