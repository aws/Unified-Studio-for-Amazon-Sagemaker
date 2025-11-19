#!/bin/bash
# Trigger specific analytics workflows by updating their .test-trigger.txt files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$SCRIPT_DIR/../examples/analytic-workflow"

# Parse arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <workflow1> [workflow2] ..."
    echo ""
    echo "Available workflows:"
    echo "  genai"
    echo "  data-notebooks"
    echo "  ml-training"
    echo "  ml-deployment"
    echo "  dashboard-glue-quick"
    echo "  all (triggers all workflows)"
    echo ""
    echo "Example: $0 ml-training ml-deployment"
    exit 1
fi

# Function to get workflow directory
get_workflow_dir() {
    case "$1" in
        genai) echo "genai" ;;
        data-notebooks) echo "data-notebooks" ;;
        ml-training) echo "ml/training" ;;
        ml-deployment) echo "ml/deployment" ;;
        dashboard-glue-quick) echo "dashboard-glue-quick" ;;
        *) echo "" ;;
    esac
}

# Collect workflows to trigger
if [ "$1" = "all" ]; then
    WORKFLOWS=(genai data-notebooks ml-training ml-deployment dashboard-glue-quick)
else
    WORKFLOWS=("$@")
fi

# Update trigger files
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
for workflow in "${WORKFLOWS[@]}"; do
    WORKFLOW_DIR=$(get_workflow_dir "$workflow")
    if [ -z "$WORKFLOW_DIR" ]; then
        echo "❌ Unknown workflow: $workflow"
        exit 1
    fi
    
    TRIGGER_FILE="$EXAMPLES_DIR/$WORKFLOW_DIR/.test-trigger.txt"
    if [ ! -f "$TRIGGER_FILE" ]; then
        echo "❌ Trigger file not found: $TRIGGER_FILE"
        exit 1
    fi
    
    echo "Trigger: $TIMESTAMP" > "$TRIGGER_FILE"
    echo "✓ Updated trigger for: $workflow"
done

# Commit and push
cd "$SCRIPT_DIR/.."
git add examples/analytic-workflow/*/.test-trigger.txt examples/analytic-workflow/ml/*/.test-trigger.txt
git commit -m "Trigger workflows: ${WORKFLOWS[*]}"
git push origin test

echo ""
echo "✅ Triggered ${#WORKFLOWS[@]} workflow(s): ${WORKFLOWS[*]}"
echo "Monitor: gh run list --branch test --limit 10"
