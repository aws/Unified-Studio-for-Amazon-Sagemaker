#!/bin/bash
set -e

# Check prerequisites for Account Pool Factory deployment

echo "🔍 Checking prerequisites..."
echo ""

MISSING_TOOLS=()

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    MISSING_TOOLS+=("aws-cli")
    echo "❌ AWS CLI not found"
else
    AWS_VERSION=$(aws --version 2>&1 | awk '{print $1}')
    echo "✅ AWS CLI: $AWS_VERSION"
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    MISSING_TOOLS+=("python3")
    echo "❌ Python 3 not found"
else
    PYTHON_VERSION=$(python3 --version)
    echo "✅ $PYTHON_VERSION"
fi

# Check jq
if ! command -v jq &> /dev/null; then
    MISSING_TOOLS+=("jq")
    echo "❌ jq not found"
else
    JQ_VERSION=$(jq --version)
    echo "✅ jq: $JQ_VERSION"
fi

# All required tools checked

echo ""

if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
    echo "❌ Missing required tools: ${MISSING_TOOLS[*]}"
    echo ""
    echo "Please install missing tools:"
    for tool in "${MISSING_TOOLS[@]}"; do
        case "$tool" in
            aws-cli)
                echo "   AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
                ;;
            python3)
                echo "   Python 3: https://www.python.org/downloads/"
                ;;
            jq)
                echo "   jq: https://stedolan.github.io/jq/download/"
                ;;
        esac
    done
    exit 1
fi

# Check AWS credentials
echo "🔐 Checking AWS credentials..."
if aws sts get-caller-identity &> /dev/null; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    IDENTITY=$(aws sts get-caller-identity --query Arn --output text)
    echo "✅ AWS credentials configured"
    echo "   Account: $ACCOUNT_ID"
    echo "   Identity: $IDENTITY"
else
    echo "❌ AWS credentials not configured or invalid"
    echo ""
    echo "Please configure AWS credentials using your organization's method."
    echo "For example:"
    echo "   aws configure"
    echo "   export AWS_PROFILE=your-profile"
    exit 1
fi

echo ""
echo "✅ All prerequisites met!"
