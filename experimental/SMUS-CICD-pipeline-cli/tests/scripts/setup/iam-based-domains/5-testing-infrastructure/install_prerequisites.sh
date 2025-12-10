#!/bin/bash

# Install prerequisites for Step 5: Testing Infrastructure and Data
# This script installs all required Python dependencies for the testing data setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_status "=== Installing Prerequisites for Step 5: Testing Infrastructure ==="
echo

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
print_status "Found Python version: $PYTHON_VERSION"

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is not installed. Please install pip3 and try again."
    exit 1
fi

print_status "Installing required Python packages..."

# Core dependencies for setup scripts
CORE_PACKAGES=(
    "boto3>=1.26.0"
    "pandas>=1.5.0"
    "numpy>=1.21.0"
    "PyYAML>=6.0"
    "typer[all]>=0.7.0"
    "jsonschema>=4.0.0"
)

# Test dependencies (optional but recommended)
TEST_PACKAGES=(
    "pytest>=7.0.0"
    "pytest-mock>=3.10.0"
    "pytest-cov>=4.0.0"
    "moto>=4.2.0"
)

# Install core packages
print_status "Installing core packages..."
for package in "${CORE_PACKAGES[@]}"; do
    print_status "Installing $package..."
    if pip3 install "$package" --quiet; then
        print_success "✅ $package installed successfully"
    else
        print_error "❌ Failed to install $package"
        exit 1
    fi
done

echo

# Ask if user wants to install test packages
read -p "Install test packages (pytest, moto, etc.)? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Installing test packages..."
    for package in "${TEST_PACKAGES[@]}"; do
        print_status "Installing $package..."
        if pip3 install "$package" --quiet; then
            print_success "✅ $package installed successfully"
        else
            print_warning "⚠️  Failed to install $package (optional)"
        fi
    done
else
    print_status "Skipping test packages installation"
fi

echo

# Verify installations
print_status "Verifying installations..."

# Test core imports
python3 -c "
import sys
import boto3
import pandas as pd
import numpy as np
import yaml
import typer
import jsonschema
print('✅ All core packages imported successfully')
" 2>/dev/null

if [ $? -eq 0 ]; then
    print_success "✅ All core dependencies verified successfully"
else
    print_error "❌ Some dependencies failed verification"
    exit 1
fi

echo

# Display installed versions
print_status "Installed package versions:"
python3 -c "
import boto3, pandas, numpy, yaml, typer, jsonschema
print(f'  boto3: {boto3.__version__}')
print(f'  pandas: {pandas.__version__}')
print(f'  numpy: {numpy.__version__}')
print(f'  PyYAML: {yaml.__version__}')
print(f'  typer: {typer.__version__}')
print(f'  jsonschema: {jsonschema.__version__}')
"

echo
print_success "=== Prerequisites Installation Complete! ==="
echo
print_status "You can now proceed with Step 5: Testing Infrastructure and Data"
print_status "Run the following commands:"
print_status "  cd testing-infrastructure && ./deploy.sh us-east-1"
print_status "  cd ../testing-data && ./deploy.sh us-east-1"