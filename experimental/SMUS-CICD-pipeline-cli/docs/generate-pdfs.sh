#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TMP_DIR="/tmp/smus-pdf-$$"

mkdir -p "$TMP_DIR"
trap "rm -rf $TMP_DIR" EXIT

echo "🔄 Generating PDFs..."

# 1. Databricks Comparison PDF
echo "📊 Creating Databricks comparison PDF..."
pandoc "$PROJECT_DIR/q-tasks/Q-databricks-comparison.md" \
    -o "$TMP_DIR/comparison.html" --standalone
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --headless --disable-gpu --print-to-pdf="$SCRIPT_DIR/Q-databricks-comparison.pdf" \
    "$TMP_DIR/comparison.html" 2>/dev/null

# 2. Complete Documentation PDF
echo "📚 Creating complete documentation PDF..."
pandoc "$PROJECT_DIR/README.md" \
    "$SCRIPT_DIR"/cli-commands.md \
    "$SCRIPT_DIR"/pipeline-manifest.md \
    "$SCRIPT_DIR"/substitutions-and-variables.md \
    "$SCRIPT_DIR"/monitoring.md \
    "$SCRIPT_DIR"/github-actions-integration.md \
    "$SCRIPT_DIR"/airflow-aws-operators.md \
    -o "$TMP_DIR/complete.html" --standalone
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --headless --disable-gpu --print-to-pdf="$SCRIPT_DIR/SMUS-CICD-Complete.pdf" \
    "$TMP_DIR/complete.html" 2>/dev/null

echo "✅ PDFs generated in docs/ folder:"
ls -lh "$SCRIPT_DIR"/*.pdf
