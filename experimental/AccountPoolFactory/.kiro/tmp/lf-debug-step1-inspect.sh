#!/bin/bash
# Step 1: Inspect current LF state in both accounts for project 5237hturzpp5ih
# Project account: 261399254793
# Domain account: 994753223772
# Databases: apf_test_customers, apf_test_transactions

REGION="us-east-2"
PROJECT_ACCOUNT="261399254793"
DOMAIN_ACCOUNT="994753223772"
DOMAIN_ID="dzd-4h7jbz76qckoh5"
PROJECT_ID="5237hturzpp5ih"
DZ_ROLE="arn:aws:iam::${PROJECT_ACCOUNT}:role/datazone_usr_role_${PROJECT_ID}_b2no4uzn8mttt5"

echo "============================================================"
echo "  LF Debug Trace - Step 1: Inspect Current State"
echo "  Project: $PROJECT_ID"
echo "  Project Account: $PROJECT_ACCOUNT"
echo "  Domain Account: $DOMAIN_ACCOUNT"
echo "  DZ User Role: $DZ_ROLE"
echo "============================================================"
echo ""

# -- DOMAIN ACCOUNT -----------------------------------------------
echo ">>> Switching to DOMAIN account ($DOMAIN_ACCOUNT)..."
eval $(isengardcli credentials amirbo+3@amazon.com)
echo ""

echo "--- Domain Account: Identity ---"
aws sts get-caller-identity --region $REGION --output json
echo ""

echo "--- Domain Account: LF Data Lake Settings (admins) ---"
aws lakeformation get-data-lake-settings --region $REGION --output json | python3 -m json.tool
echo ""

echo "--- Domain Account: LF Permissions on apf_test_customers DB ---"
aws lakeformation list-permissions \
    --resource '{"Database":{"Name":"apf_test_customers"}}' \
    --region $REGION --output json | python3 -m json.tool
echo ""

echo "--- Domain Account: LF Permissions on apf_test_customers Tables ---"
aws lakeformation list-permissions \
    --resource '{"Table":{"DatabaseName":"apf_test_customers","TableWildcard":{}}}' \
    --region $REGION --output json | python3 -m json.tool
echo ""

echo "--- Domain Account: LF Permissions on apf_test_transactions DB ---"
aws lakeformation list-permissions \
    --resource '{"Database":{"Name":"apf_test_transactions"}}' \
    --region $REGION --output json | python3 -m json.tool
echo ""

echo "--- Domain Account: LF Permissions on apf_test_transactions Tables ---"
aws lakeformation list-permissions \
    --resource '{"Table":{"DatabaseName":"apf_test_transactions","TableWildcard":{}}}' \
    --region $REGION --output json | python3 -m json.tool
echo ""

# -- PROJECT ACCOUNT (via DomainAccess role) ----------------------
echo ">>> Inspecting PROJECT account ($PROJECT_ACCOUNT) via DomainAccess role..."
echo ""
