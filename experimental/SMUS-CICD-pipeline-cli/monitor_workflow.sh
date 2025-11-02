#!/bin/bash

PIPELINE=$1
TARGET=$2
RUN_ID=$3

if [ -z "$PIPELINE" ] || [ -z "$TARGET" ]; then
    echo "Usage: $0 <pipeline.yaml> <target> [run_id]"
    exit 1
fi

LAST_STATUS=""
STATUS_START_TIME=""

echo "🔍 Monitoring workflow: $PIPELINE (target: $TARGET)"
[ -n "$RUN_ID" ] && echo "   Run ID: $RUN_ID"
echo ""

while true; do
    OUTPUT=$(python -m smus_cicd.cli monitor -p "$PIPELINE" -t "$TARGET" 2>&1)
    
    if [ -n "$RUN_ID" ]; then
        CURRENT_STATUS=$(echo "$OUTPUT" | grep "$RUN_ID" | awk '{print $6}')
    else
        CURRENT_STATUS=$(echo "$OUTPUT" | grep -A 1 "Run Status" | tail -1 | awk '{print $6}')
    fi
    
    if [ -z "$CURRENT_STATUS" ]; then
        echo "⚠️  Could not detect workflow status"
        sleep 5
        continue
    fi
    
    CURRENT_TIME=$(date +%s)
    
    if [ "$CURRENT_STATUS" != "$LAST_STATUS" ]; then
        if [ -n "$LAST_STATUS" ]; then
            DURATION=$((CURRENT_TIME - STATUS_START_TIME))
            echo "   ⏱️  Stayed in $LAST_STATUS for ${DURATION}s"
        fi
        echo "📊 Status changed: $LAST_STATUS → $CURRENT_STATUS ($(date '+%H:%M:%S'))"
        LAST_STATUS="$CURRENT_STATUS"
        STATUS_START_TIME=$CURRENT_TIME
    fi
    
    if [ "$CURRENT_STATUS" = "FAILED" ] || [ "$CURRENT_STATUS" = "SUCCESS" ] || [ "$CURRENT_STATUS" = "SUCCEEDED" ]; then
        TOTAL_DURATION=$((CURRENT_TIME - STATUS_START_TIME))
        echo "✅ Workflow finished: $CURRENT_STATUS (total time in final state: ${TOTAL_DURATION}s)"
        break
    fi
    
    sleep 10
done
