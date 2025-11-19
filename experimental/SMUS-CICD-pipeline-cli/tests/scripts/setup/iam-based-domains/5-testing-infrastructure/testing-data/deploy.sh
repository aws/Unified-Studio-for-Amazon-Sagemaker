#!/bin/bash

# Deploy test data (ML datasets and COVID data)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${1:-us-east-1}"

echo "=== Deploying Test Data ==="
echo "Region: $REGION"

# Setup ML test data
echo "Setting up ML test data..."
python3 "$SCRIPT_DIR/setup-ml-resources.py" --region "$REGION"

echo "✅ ML test data deployed!"

# COVID data setup (optional - requires DataZone domain)
read -p "Setup COVID-19 test data? (requires DataZone domain) [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Downloading COVID-19 data..."
    python3 "$SCRIPT_DIR/download-covid-data.py"
    
    echo "Setting up COVID-19 data sources..."
    python3 "$SCRIPT_DIR/setup-covid-data.py"
    
    echo "Publishing COVID-19 assets..."
    python3 "$SCRIPT_DIR/publish-all-covid-tables.py"
    
    echo "✅ COVID-19 test data deployed!"
else
    echo "Skipping COVID-19 data setup"
fi

echo "✅ Test data deployment complete!"
