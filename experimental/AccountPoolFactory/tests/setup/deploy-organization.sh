#!/bin/bash
#
# Deploy AWS Organization Structure using CloudFormation
#
# Prerequisites:
#   1. Ensure config.yaml exists with your configuration
#   2. Ensure AWS credentials are configured
#   3. Install yq for YAML parsing: brew install yq (or apt-get install yq)
#
# Usage: ./deploy-organization.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_SETUP_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$(dirname "$TESTS_SETUP_DIR")")"
TEMPLATE_FILE="${TESTS_SETUP_DIR}/templates/organization-structure.yaml"
CONFIG_FILE="${PROJECT_ROOT}/config.yaml"

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Read configuration from YAML
read_config() {
    local key="$1"
    
    # Try using yq if available
    if command -v yq &> /dev/null; then
        yq eval "$key" "$CONFIG_FILE" 2>/dev/null
    else
        # Fallback to grep/sed for simple key extraction
        grep -A 1 "^  ${key##*.}:" "$CONFIG_FILE" | tail -1 | sed 's/.*: //' | tr -d '"' | tr -d "'"
    fi
}

# Load configuration
load_config() {
    log_info "Loading configuration from: $CONFIG_FILE"
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        log_info "Copy config.yaml.template to config.yaml and customize it"
        exit 1
    fi
    
    # Read values from config.yaml
    REGION=$(read_config ".aws.region")
    STACK_NAME=$(read_config ".stacks.organization")
    
    # Fallback to defaults if parsing fails
    REGION="${REGION:-us-east-2}"
    STACK_NAME="${STACK_NAME:-AccountPoolFactory-Organization-Test}"
    
    log_info "Region: $REGION"
    log_info "Stack Name: $STACK_NAME"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check config file
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        log_info "Copy config.yaml.template to config.yaml and customize it"
        exit 1
    fi
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity --region "$REGION" &> /dev/null; then
        log_error "AWS credentials not configured or expired"
        log_info "Configure credentials using one of:"
        log_info "  - AWS CLI: aws configure"
        log_info "  - Environment: export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=..."
        log_info "  - AWS SSO: aws sso login --profile your-profile"
        exit 1
    fi
    
    # Check template file exists
    if [[ ! -f "$TEMPLATE_FILE" ]]; then
        log_error "CloudFormation template not found: $TEMPLATE_FILE"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Get organization root ID
get_root_id() {
    log_info "Getting organization root ID..." >&2
    
    ROOT_ID=$(aws organizations list-roots \
        --region "$REGION" \
        --query 'Roots[0].Id' \
        --output text)
    
    if [[ -z "$ROOT_ID" ]]; then
        log_error "Failed to get organization root ID" >&2
        exit 1
    fi
    
    log_info "Organization Root ID: $ROOT_ID" >&2
    echo "$ROOT_ID"
}

# Check if stack exists
stack_exists() {
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" &> /dev/null
}

# Deploy CloudFormation stack
deploy_stack() {
    local root_id="$1"
    
    log_info "Deploying CloudFormation stack: $STACK_NAME"
    
    if stack_exists; then
        log_info "Stack exists, updating..."
        
        aws cloudformation update-stack \
            --stack-name "$STACK_NAME" \
            --template-body "file://${TEMPLATE_FILE}" \
            --parameters ParameterKey=RootId,ParameterValue="$root_id" \
            --region "$REGION" \
            --capabilities CAPABILITY_NAMED_IAM || {
                if [[ $? -eq 254 ]]; then
                    log_warning "No updates to be performed"
                    return 0
                else
                    log_error "Stack update failed"
                    return 1
                fi
            }
        
        log_info "Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION"
        
        log_success "Stack updated successfully"
    else
        log_info "Creating new stack..."
        
        aws cloudformation create-stack \
            --stack-name "$STACK_NAME" \
            --template-body "file://${TEMPLATE_FILE}" \
            --parameters ParameterKey=RootId,ParameterValue="$root_id" \
            --region "$REGION" \
            --capabilities CAPABILITY_NAMED_IAM
        
        log_info "Waiting for stack creation to complete..."
        aws cloudformation wait stack-create-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION"
        
        log_success "Stack created successfully"
    fi
}

# Get stack outputs
get_stack_outputs() {
    log_info "Retrieving stack outputs..."
    
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs' \
        --output json > "${PROJECT_ROOT}/ou-ids.json"
    
    log_success "Stack outputs saved to: ou-ids.json"
}

# Display organization structure
display_structure() {
    log_info ""
    log_info "=== Organization Structure ==="
    cat << 'EOF'

Root
├── RetailBanking (Retail Banking Operations)
│   ├── CustomerAnalytics ⭐ (Account Pool Target)
│   │   └── Customer insights and analytics workloads
│   └── RiskAnalytics ⭐ (Account Pool Target)
│       └── Risk assessment and compliance analytics
│
└── CommercialBanking (Commercial Banking & Business Lending)

⭐ = Target OUs for Account Pool Factory
    Analytics project accounts will be created in these OUs

Total OUs: 4 (banking business structure)

EOF
}

# Update config file
update_config() {
    log_info "Updating config.yaml with OU information..."
    
    # Get outputs
    TARGET_OU_ID=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`TargetOUId`].OutputValue' \
        --output text)
    
    ROOT_ID=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`RootId`].OutputValue' \
        --output text)
    
    # Check if organization section already exists
    if grep -q "^organization:" "$CONFIG_FILE" 2>/dev/null; then
        log_warning "Organization section already exists in config.yaml"
        log_info "Please update manually if needed"
    else
        # Add to config.yaml
        cat >> "$CONFIG_FILE" << EOF

# Organization Structure (added by deploy-organization.sh)
organization:
  stack_name: $STACK_NAME
  root_id: $ROOT_ID
  target_ou_id: $TARGET_OU_ID
  target_ou_name: RetailBanking/CustomerAnalytics
  target_ou_path: /RetailBanking/CustomerAnalytics
  description: Customer analytics accounts for Retail Banking business unit
  
# Stack outputs saved to ou-ids.json
EOF
        log_success "Config file updated"
    fi
}

# Main execution
main() {
    echo ""
    echo "=========================================="
    echo "  Deploy Organization Structure"
    echo "  Account Pool Factory Testing"
    echo "=========================================="
    echo ""
    
    load_config
    
    check_prerequisites
    
    ROOT_ID=$(get_root_id)
    
    deploy_stack "$ROOT_ID"
    
    get_stack_outputs
    
    display_structure
    
    update_config
    
    echo ""
    log_success "Organization deployment complete!"
    echo ""
    log_info "Next steps:"
    echo "  1. Review stack outputs: cat ou-ids.json"
    echo "  2. Verify in AWS Console: https://console.aws.amazon.com/cloudformation"
    echo "  3. View OUs: https://console.aws.amazon.com/organizations"
    echo "  4. Update TESTING_MANUAL.md with Step 1.3 completion"
    echo "  5. Proceed to next testing step"
    echo ""
}

# Run main function
main "$@"
