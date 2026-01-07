#!/bin/bash

# Deploy test data (ML datasets and COVID data)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${1:-us-east-1}"

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

echo "=== Deploying Test Data ==="
echo "Region: $REGION"

# Check and install prerequisites
print_status "Checking Python dependencies..."

# Function to check if a Python package is installed
check_python_package() {
    python3 -c "import $1" 2>/dev/null
    return $?
}

# Check required packages
REQUIRED_PACKAGES=("boto3" "pandas" "numpy" "yaml")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! check_python_package "$package"; then
        MISSING_PACKAGES+=("$package")
    fi
done

# If packages are missing, run prerequisite installation
if [ ${#MISSING_PACKAGES[@]} -ne 0 ]; then
    print_warning "Missing required Python packages: ${MISSING_PACKAGES[*]}"
    print_status "Running prerequisite installation..."
    
    PREREQ_SCRIPT="$SCRIPT_DIR/../install_prerequisites.sh"
    
    if [ -f "$PREREQ_SCRIPT" ]; then
        # Run prerequisite script non-interactively
        echo "y" | bash "$PREREQ_SCRIPT"
        
        if [ $? -eq 0 ]; then
            print_success "Prerequisites installed successfully"
        else
            print_error "Failed to install prerequisites"
            exit 1
        fi
    else
        print_error "Prerequisite script not found: $PREREQ_SCRIPT"
        print_status "Please install the following packages manually:"
        print_status "  pip3 install boto3 pandas numpy PyYAML"
        exit 1
    fi
else
    print_success "All required Python packages are installed"
fi

# Setup ML test data
echo "Setting up ML test data..."
python3 "$SCRIPT_DIR/setup-ml-resources.py" --region "$REGION"

echo "✅ ML test data deployed!"

# COVID data setup (optional - requires DataZone domain)
read -p "Setup COVID-19 test data? (requires DataZone domain) [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Setting up COVID-19 test data..."
    
    # Get DataZone domain name automatically
    print_status "Discovering DataZone domain..."
    DOMAIN_NAME=$(aws datazone list-domains --region us-east-2 --query 'items[?starts_with(name, `Default`) && ends_with(name, `Domain`)].name' --output text | head -1)
    
    if [ -z "$DOMAIN_NAME" ] || [ "$DOMAIN_NAME" = "None" ]; then
        print_error "No DataZone domain found matching 'Default*Domain' pattern"
        print_status "Available domains:"
        aws datazone list-domains --region us-east-2 --query 'items[].{Name:name,Id:id}' --output table
        print_status "Skipping COVID-19 data setup"
    else
        print_success "Found DataZone domain: $DOMAIN_NAME"
        
        echo "Downloading COVID-19 data..."
        python3 "$SCRIPT_DIR/download-covid-data.py"
        
        echo "Setting up COVID-19 data sources..."
        python3 "$SCRIPT_DIR/setup-covid-data.py" "$DOMAIN_NAME" --region us-east-2
        
        echo "Publishing COVID-19 assets..."
        python3 "$SCRIPT_DIR/publish-all-covid-tables.py" "$DOMAIN_NAME" --region us-east-2
        
        print_success "✅ COVID-19 test data deployed!"
    fi
else
    print_status "Skipping COVID-19 data setup"
fi

echo "✅ Test data deployment complete!"
