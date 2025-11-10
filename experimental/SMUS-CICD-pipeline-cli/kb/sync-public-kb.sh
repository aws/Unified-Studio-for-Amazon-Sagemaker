#!/bin/bash
# SMUS Team: Sync KB content to public S3 bucket
# Run this after updating docs or examples

set -e

PUBLIC_BUCKET="smus-cli-public-kb"
REGION="us-east-1"

echo "🔄 Syncing to public KB bucket: s3://${PUBLIC_BUCKET}/"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Sync docs
echo "📚 Syncing documentation..."
aws s3 sync docs/ "s3://${PUBLIC_BUCKET}/docs/" \
  --exclude "development.md" \
  --acl public-read \
  --delete \
  --region "$REGION"

# Sync examples
echo "📦 Syncing examples..."
aws s3 sync examples/ "s3://${PUBLIC_BUCKET}/examples/" \
  --exclude "**/test_*.py" \
  --exclude "**/__pycache__/*" \
  --exclude "**/.ipynb_checkpoints/*" \
  --acl public-read \
  --delete \
  --region "$REGION"

# Sync templates
echo "📝 Syncing templates..."
if [ -d "kb/templates" ]; then
  aws s3 sync kb/templates/ "s3://${PUBLIC_BUCKET}/templates/" \
    --acl public-read \
    --delete \
    --region "$REGION"
fi

echo ""
echo "✅ Public KB updated!"
echo "📊 Users will get updates on their next KB sync"
echo ""
echo "To verify:"
echo "  aws s3 ls s3://${PUBLIC_BUCKET}/ --recursive --human-readable"
