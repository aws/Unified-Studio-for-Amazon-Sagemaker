#!/bin/bash

# SMUS CI/CD Pipeline Full Lifecycle Demo Script
# Clean demo version - shows only commands and their outputs

set +e  # Don't exit on error - we want to handle them ourselves

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/full-pipeline-example.log"

# Default values
DOMAIN_NAME="cicd-test-domain"
PROJECT_NAME="dev-marketing"
PAUSE_MODE=false

# Function to run command and check exit code
run_command() {
    local cmd="$1"
    echo "$cmd"
    eval "$cmd"
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "✅ SUCCESS: Command completed successfully"
    else
        echo "❌ FAILURE: Command failed with exit code $exit_code"
        return $exit_code
    fi
    echo ""
    return 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN_NAME="$2"
            shift 2
            ;;
        --project)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --pause)
            PAUSE_MODE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --domain DOMAIN_NAME    Domain name (default: cicd-test-domain)"
            echo "  --project PROJECT_NAME  Project name (default: dev-marketing)"
            echo "  --pause                 Pause after each step for demo purposes"
            echo ""
            echo "To capture output to log file:"
            echo "  $0 [options] 2>&1 | tee \"$SCRIPT_DIR/full-pipeline-example.log\""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Function to pause if in pause mode
pause_if_needed() {
    if [ "$PAUSE_MODE" = true ]; then
        echo ""
        read -p "Press Enter to continue..." -r
        echo ""
    fi
}

# Function to resolve domain name to ID
resolve_domain_id() {
    local domain_name="$1"
    local domain_id
    if command -v aws >/dev/null 2>&1; then
        domain_id=$(aws datazone list-domains --query "items[?name=='$domain_name'].id" --output text 2>/dev/null || echo "")
        if [ -z "$domain_id" ] || [ "$domain_id" = "None" ] || [ "$domain_id" = "null" ]; then
            read -p "Enter domain ID for '$domain_name': " -r domain_id
        fi
    else
        read -p "Enter domain ID for '$domain_name': " -r domain_id
    fi
    echo "$domain_id"
}

# Function to resolve project name to ID
resolve_project_id() {
    local domain_id="$1"
    local project_name="$2"
    local project_id
    if command -v aws >/dev/null 2>&1; then
        project_id=$(aws datazone list-projects --domain-identifier "$domain_id" --query "items[?name=='$project_name'].id" --output text 2>/dev/null || echo "")
        if [ -z "$project_id" ] || [ "$project_id" = "None" ] || [ "$project_id" = "null" ]; then
            read -p "Enter project ID for '$project_name': " -r project_id
        fi
    else
        read -p "Enter project ID for '$project_name': " -r project_id
    fi
    echo "$project_id"
}

# Resolve domain and project IDs
DOMAIN_ID=$(resolve_domain_id "$DOMAIN_NAME")
DEV_PROJECT_ID=$(resolve_project_id "$DOMAIN_ID" "$PROJECT_NAME")

# Configuration variables
PIPELINE_NAME="DemoMarketingPipeline"
PIPELINE_FILE="${PIPELINE_NAME}.yaml"

# Step 1: Create pipeline manifest
run_command "smus-cli create --name \"$PIPELINE_NAME\" --domain-id \"$DOMAIN_ID\" --dev-project-id \"$DEV_PROJECT_ID\" --output \"$PIPELINE_FILE\""

pause_if_needed

# Step 2: Validate pipeline configuration
run_command "smus-cli describe --bundle \"$PIPELINE_FILE\" --workflows --connections --connect --output TEXT"

pause_if_needed

# Step 3: Create deployment bundle
run_command "smus-cli bundle --bundle \"$PIPELINE_FILE\" --targets dev --output JSON"

pause_if_needed

# Step 4: Deploy to test environment
run_command "smus-cli deploy --bundle \"$PIPELINE_FILE\" --targets test"

pause_if_needed

# Step 5: Run tests
run_command "smus-cli test --bundle \"$PIPELINE_FILE\" --targets test"

pause_if_needed

# Step 6: Monitor pipeline
run_command "smus-cli monitor --bundle \"$PIPELINE_FILE\" --output TEXT"

pause_if_needed

# Step 7: Execute workflow commands
run_command "smus-cli run --bundle \"$PIPELINE_FILE\" --targets dev --workflow test_dag --command \"dags trigger test_dag\""

pause_if_needed

run_command "smus-cli run --bundle \"$PIPELINE_FILE\" --targets dev --workflow test_dag --command \"tasks list test_dag\""

pause_if_needed

run_command "smus-cli run --bundle \"$PIPELINE_FILE\" --targets dev --workflow test_dag --command \"tasks state test_dag hello_world \$(date -u +'manual__%Y-%m-%dT%H:%M:%S+00:00')\""

pause_if_needed

# Step 8: Cleanup
run_command "smus-cli delete --targets test --bundle \"$PIPELINE_FILE\" --force"

if [ "$PAUSE_MODE" = true ]; then
    echo ""
    read -p "Demo complete. Press Enter to finish..." -r
fi

echo ""
echo "💡 To capture output to log file, run:"
echo "   $0 [options] 2>&1 | tee \"$LOG_FILE\""
echo ""
echo "📄 Log file will be saved to: $LOG_FILE"
