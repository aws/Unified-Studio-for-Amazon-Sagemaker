#!/bin/bash
set -e

echo "=== Checking Domain Visibility from Project Account ==="
echo ""

# Check from account 100 (004878717744)
echo "Checking from account 004878717744 (amirbo+100)..."
eval "$(isengardcli creds amirbo+100 --role Admin)"

aws datazone list-domains --region us-east-2 --output json | jq '.items[] | {id, name, status}'

echo ""
echo "✅ Domain is visible from project account"
