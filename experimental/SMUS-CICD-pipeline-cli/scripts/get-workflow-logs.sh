#!/bin/bash
# Get logs from latest workflow runs
# Usage: ./get-workflow-logs.sh                    (gets latest runs - DEFAULT)
#        ./get-workflow-logs.sh "commit pattern"   (filter by commit message)

set -e

OUTPUT_DIR="/tmp/workflow-logs"

if [ -z "$1" ]; then
  echo "🔍 Finding latest workflow runs (all workflows)"
  # Get latest run for each unique workflow name
  RUNS=$(gh run list --limit 50 --json databaseId,status,conclusion,name,displayTitle,createdAt | \
    jq -r 'group_by(.name) | map(sort_by(.createdAt) | reverse | .[0]) | .[] | "\(.name)|\(.databaseId)|\(.conclusion)"')
else
  COMMIT_PATTERN="$1"
  echo "🔍 Finding workflows matching: $COMMIT_PATTERN"
  # Get latest run for each workflow matching the pattern
  RUNS=$(gh run list --limit 50 --json databaseId,status,conclusion,name,displayTitle,createdAt | \
    jq -r "group_by(.name) | map(sort_by(.createdAt) | reverse | map(select(.displayTitle | contains(\"$COMMIT_PATTERN\"))) | .[0]) | .[] | select(. != null) | \"\(.name)|\(.databaseId)|\(.conclusion)\"")
fi

if [ -z "$RUNS" ]; then
  echo "❌ No workflows found"
  exit 1
fi

echo "Found workflows (latest per workflow name):"
echo "$RUNS"
echo ""

mkdir -p "$OUTPUT_DIR"

# Process each workflow
echo "$RUNS" | while IFS='|' read -r name run_id conclusion; do
  echo "=== Processing: $name (Run $run_id) ==="
  
  # Get job ID from gh run view
  job_id=$(gh run view "$run_id" 2>&1 | grep -E "^X.*\(ID" | sed 's/.*ID //' | sed 's/)//' | head -1)
  
  if [ -z "$job_id" ]; then
    echo "  ⚠️  No failed job found (conclusion: $conclusion)"
    continue
  fi
  
  echo "  Job ID: $job_id"
  
  # Download logs
  log_file="$OUTPUT_DIR/${name// /_}_${run_id}.log"
  gh api "/repos/aws/Unified-Studio-for-Amazon-Sagemaker/actions/jobs/$job_id/logs" 2>&1 > "$log_file"
  
  # Extract errors
  echo "  Errors found:"
  grep -E "(⚠️|❌)" "$log_file" | tail -5 | sed 's/^/    /'
  echo ""
done

echo "✅ Logs saved to: $OUTPUT_DIR"
echo ""
echo "To view all errors:"
echo "  grep -E '(⚠️|❌)' $OUTPUT_DIR/*.log"
