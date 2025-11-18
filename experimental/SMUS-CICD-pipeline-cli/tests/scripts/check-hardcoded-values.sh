#!/bin/bash
# Check for hardcoded AWS account IDs, regions, endpoints, and other sensitive values
# Usage: ./tests/scripts/check-hardcoded-values.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🔍 Checking for hardcoded values in code and documentation..."
echo "Project root: $PROJECT_ROOT"
echo ""

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

ISSUES_FOUND=0

# Directories to check
DIRS_TO_CHECK=(
    "src"
    "tests"
    "examples"
    "docs"
)

# Directories to exclude
EXCLUDE_DIRS=(
    "venv"
    "node_modules"
    ".git"
    "__pycache__"
    ".pytest_cache"
    "test-outputs"
    "test-output"
    "bundles"
)

# Build exclude pattern for grep
EXCLUDE_PATTERN=""
for dir in "${EXCLUDE_DIRS[@]}"; do
    EXCLUDE_PATTERN="$EXCLUDE_PATTERN --exclude-dir=$dir"
done

# Function to search and report
search_pattern() {
    local pattern="$1"
    local description="$2"
    local exclude_files="$3"
    
    echo "Checking for: $description"
    
    # Build exclude file pattern
    local exclude_file_pattern=""
    if [ -n "$exclude_files" ]; then
        exclude_file_pattern="--exclude=$exclude_files"
    fi
    
    local results=$(grep -r -n -E "$pattern" "${DIRS_TO_CHECK[@]}" \
        $EXCLUDE_PATTERN \
        $exclude_file_pattern \
        2>/dev/null || true)
    
    if [ -n "$results" ]; then
        echo -e "${RED}✗ Found hardcoded values:${NC}"
        echo "$results" | while IFS= read -r line; do
            echo "  $line"
        done
        echo ""
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    else
        echo -e "${GREEN}✓ No issues found${NC}"
    fi
    echo ""
}

cd "$PROJECT_ROOT"

# 1. Check for AWS Account IDs (12-digit numbers)
# Exclude common false positives like timestamps, version numbers
search_pattern '\b[0-9]{12}\b' \
    "AWS Account IDs (12-digit numbers)" \
    "*.log"

# 2. Check for hardcoded AWS regions in code (not in config/examples)
# This checks for regions used as string literals in Python code
search_pattern "region['\"]?\s*[:=]\s*['\"]us-|region['\"]?\s*[:=]\s*['\"]eu-|region['\"]?\s*[:=]\s*['\"]ap-" \
    "Hardcoded AWS regions in code" \
    "*.yaml,*.yml,*.md"

# 3. Check for hardcoded endpoints
search_pattern 'https?://[a-zA-Z0-9-]+\.amazonaws\.com' \
    "Hardcoded AWS endpoints" \
    "*.md"

# 4. Check for IP addresses (excluding common patterns like 0.0.0.0, 127.0.0.1)
search_pattern '\b(?!0\.0\.0\.0|127\.0\.0\.1|255\.255\.255\.)[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\b' \
    "IP addresses" \
    "*.log"

# 5. Check for hardcoded IAM role ARNs with account IDs
search_pattern 'arn:aws:iam::[0-9]{12}:role/' \
    "IAM role ARNs with hardcoded account IDs" \
    "*.yaml,*.yml,*.md"

# 6. Check for hardcoded S3 bucket names with account IDs
search_pattern 's3://[a-z0-9-]*[0-9]{12}[a-z0-9-]*' \
    "S3 bucket names with account IDs" \
    "*.log"

# 7. Check for common hostnames/domains
search_pattern '\b[a-z0-9-]+\.(internal|corp|local)\b' \
    "Internal hostnames" \
    "*.md"

# 8. Check for email addresses (potential PII)
search_pattern '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b' \
    "Email addresses" \
    "*.md,*.yaml,*.yml"

# Summary
echo "================================================"
if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}✅ No hardcoded values found!${NC}"
    exit 0
else
    echo -e "${RED}❌ Found $ISSUES_FOUND types of hardcoded values${NC}"
    echo ""
    echo "Please fix these issues:"
    echo "  1. Replace AWS account IDs with: boto3.client('sts').get_caller_identity()['Account']"
    echo "  2. Replace regions with: os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')"
    echo "  3. Replace endpoints with environment variables or dynamic lookup"
    echo "  4. Mask email addresses in examples: user@example.com"
    echo "  5. Use placeholders: 123456789012 → ACCOUNT_ID"
    exit 1
fi
