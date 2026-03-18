#!/usr/bin/env python3
"""
Re-annotate lf-trace-cli-output.txt:
1. Strip all existing # comment lines
2. Add summary at top
3. Add step numbers and expected-result markers
"""

with open('experimental/AccountPoolFactory/.kiro/tmp/lf-trace-cli-output.txt') as f:
    lines = f.readlines()

# Strip existing annotations (lines starting with #)
raw = [l for l in lines if not l.startswith('#')]

# Re-index after stripping
# Find key line numbers in the raw output
line_index = {}
for i, line in enumerate(raw, 1):
    s = line.strip()
    if s:
        line_index[i] = s

def find_line(pattern, start=1):
    for i in range(start, len(raw)+1):
        if i in line_index and pattern in line_index[i]:
            return i
    return None

SUMMARY = """# ===========================================================================
# ISSUE SUMMARY
# ===========================================================================
#
# Problem: Glue resource link databases in a consumer account are not visible
# via get-databases to a DataZone user role, even though get-tables on those
# same databases succeeds and returns data.
#
# Setup:
#   - Domain account 994753223772 owns Glue databases (apf_test_customers,
#     apf_test_transactions) backed by S3 data.
#   - Project account 261399254793 has Glue resource link databases pointing
#     to the domain account databases (created via CloudFormation StackSet).
#   - DataZone user role (datazone_usr_role_5237hturzpp5ih_b2no4uzn8mttt5)
#     in the project account is the role used by end users via DataZone
#     connection credentials.
#
# What we tried (3 phases):
#   Phase 1: Cross-account LF grant from domain to project account ID
#   Phase 2: Grant IAM_ALLOWED_PRINCIPALS on resource link DBs in project account
#   Phase 3: Cross-account LF grant from domain directly to the DZ user role ARN
#
# Result after all 3 phases:
#   - get-databases (DZ user role): does NOT show apf_test_customers or
#     apf_test_transactions. Only shows 'default' and DataZone-managed DB.
#   - get-tables (DZ user role): SUCCEEDS and returns full table metadata
#     from the source account for both databases.
#   - list-permissions in project account: always empty (no local LF grants).
#   - IAM_ALLOWED_PRINCIPALS grant on table wildcard: REJECTED by LF with
#     "Grant on table wildcard is not allowed" for resource link databases.
#
# Expected behavior: If get-tables works, get-databases should also show
# the resource link databases. The role has cross-account access to the
# underlying tables but cannot discover the databases.
#
# ===========================================================================

"""

annotations = {}

# BASELINE section
bl = find_line('BASELINE')
if bl:
    annotations[bl] = [
        "# ---------------------------------------------------------------------------",
        "# STEP 1: Verify clean starting state",
        "# Show existing LF permissions in both accounts and what each role can see.",
        "# ---------------------------------------------------------------------------",
    ]

# Domain identity
di = find_line('>>> aws sts get-caller-identity', 1)
if di:
    annotations[di] = [
        "# Caller: domain account Admin role (994753223772)",
    ]

# Domain list-permissions
dlp = find_line('list-permissions --resource Database:apf_test_customers (filtered', 1)
if dlp:
    annotations[dlp] = [
        "# Check cross-account LF grants in the DOMAIN account for project account 261399254793.",
    ]

# Project account switch
pa = find_line('assumed-role/SMUS-AccountPoolFactory-DomainAccess/lf-trace')
if pa:
    annotations[pa-1] = [
        "# Switch to PROJECT account (261399254793) via DomainAccess role.",
        "# This role has AdministratorAccess but is NOT a Lake Formation admin.",
    ]

# LF data lake settings
dls = find_line('aws lakeformation get-data-lake-settings')
if dls:
    annotations[dls] = [
        "# LF admins in project account. Note: datazone_usr_role is NOT listed.",
    ]

# LF list-permissions in project
plp = find_line('aws lakeformation list-permissions', dls+1 if dls else 1)
if plp:
    annotations[plp] = [
        "# All LF permissions in project account — expected empty.",
    ]

# DomainAccess get-databases
dag = find_line('DomainAccess — admin view, shows what SHOULD be there')
if dag:
    annotations[dag] = [
        "# DomainAccess role sees all Glue databases (admin view).",
        "# This shows what SHOULD be visible: apf_test_customers and apf_test_transactions",
        "# are resource links pointing to catalog 994753223772.",
    ]

# DomainAccess get-tables
dagt = find_line('get-tables --database-name apf_test_customers (DomainAccess')
if dagt:
    annotations[dagt] = [
        "# DomainAccess get-tables fails — it has no cross-account LF grant.",
        "# This is expected: AdminAccess alone is not enough for cross-account Glue.",
    ]

# DZ user role switch
dzs = find_line('assumed-role/datazone_usr_role_5237hturzpp5ih')
if dzs:
    annotations[dzs-1] = [
        "# Switch to the actual DZ user role via DataZone connection credentials.",
        "# This is the role end users get when they use the Athena connection.",
    ]

# DZ get-databases baseline
dzgd = find_line('get-databases (DZ User Role — actual user view)')
if dzgd:
    annotations[dzgd] = [
        "# *** UNEXPECTED RESULT ***",
        "# get-databases does NOT show apf_test_customers or apf_test_transactions.",
        "# Only 'default' and the DataZone-managed DB are visible.",
        "# The resource link databases are MISSING.",
    ]

# DZ get-tables baseline
dzgt = find_line('get-tables --database-name apf_test_customers (DZ User Role)', 1)
if dzgt:
    annotations[dzgt] = [
        "# *** PARADOX ***",
        "# get-tables SUCCEEDS — the DZ user role CAN read tables from the source account.",
        "# But the databases don't appear in get-databases above.",
    ]

# PHASE 1
p1 = find_line('PHASE 1')
if p1:
    annotations[p1] = [
        "# ---------------------------------------------------------------------------",
        "# STEP 2: Grant cross-account LF permissions (domain -> project account ID)",
        "# Grant DESCRIBE on databases and SELECT+DESCRIBE on tables, with grant option.",
        "# ---------------------------------------------------------------------------",
    ]

# After Phase 1 verify
p1v = find_line('AFTER Phase 1')
if p1v:
    annotations[p1v] = [
        "# Verify grants were created in domain account.",
    ]

# Phase 1 DZ get-databases
p1dzgd = find_line('get-databases (DZ User Role — after Phase 1)')
if p1dzgd:
    annotations[p1dzgd] = [
        "# *** UNEXPECTED RESULT ***",
        "# After granting to account ID: get-databases STILL does not show apf_test_* databases.",
    ]

# Phase 1 DZ get-tables
p1dzgt = find_line('get-tables --database-name apf_test_customers (DZ User Role — after Phase 1)')
if p1dzgt:
    annotations[p1dzgt] = [
        "# get-tables still works (tables accessible). Database discovery is the problem.",
    ]

# PHASE 2
p2 = find_line('PHASE 2')
if p2:
    annotations[p2] = [
        "# ---------------------------------------------------------------------------",
        "# STEP 3: Grant IAM_ALLOWED_PRINCIPALS in project account on resource link DBs",
        "# Temporarily add DomainAccess as LF admin to perform this operation.",
        "# ---------------------------------------------------------------------------",
    ]

# IAP table wildcard error
iap_err = find_line('Grant on table wildcard is not allowed')
if iap_err:
    annotations[iap_err] = [
        "# *** LF LIMITATION ***",
        "# Cannot grant IAM_ALLOWED_PRINCIPALS on table wildcard for resource link databases.",
    ]

# Phase 2 DZ get-databases
p2dzgd = find_line('get-databases (DZ User Role — after Phase 2)')
if p2dzgd:
    annotations[p2dzgd] = [
        "# *** UNEXPECTED RESULT ***",
        "# After IAM_ALLOWED_PRINCIPALS grant on DBs: get-databases STILL missing apf_test_*.",
    ]

# PHASE 3
p3 = find_line('PHASE 3')
if p3:
    annotations[p3] = [
        "# ---------------------------------------------------------------------------",
        "# STEP 4: Grant cross-account LF directly to the DZ user role ARN",
        "# This grants from domain account directly to the specific IAM role.",
        "# ---------------------------------------------------------------------------",
    ]

# Phase 3 project list-permissions
p3plp_line = find_line('aws lakeformation list-permissions', (find_line('AFTER Phase 3') or 1))
if p3plp_line:
    annotations[p3plp_line+2] = [  # the empty result line
        "# Project account STILL shows no local LF permissions.",
    ]

# Phase 3 DZ get-databases
p3dzgd = find_line('get-databases (DZ User Role — after Phase 3)')
if p3dzgd:
    annotations[p3dzgd] = [
        "# *** UNEXPECTED RESULT — FINAL ***",
        "# After ALL three phases of grants, get-databases STILL does not show",
        "# apf_test_customers or apf_test_transactions.",
    ]

# Phase 3 DZ get-tables
p3dzgt = find_line('get-tables --database-name apf_test_customers (DZ User Role — after Phase 3)')
if p3dzgt:
    annotations[p3dzgt] = [
        "# get-tables STILL works — tables are accessible but databases are not discoverable.",
    ]

# Trace complete
tc = find_line('Trace complete')
if tc:
    annotations[tc] = [
        "# ===========================================================================",
        "# CONCLUSION",
        "# ===========================================================================",
        "# Despite having:",
        "#   1. Cross-account LF grants to the project account ID (with grant option)",
        "#   2. IAM_ALLOWED_PRINCIPALS DESCRIBE on resource link databases",
        "#   3. Cross-account LF grants directly to the DZ user role ARN",
        "#   4. RAM resource shares created by LF for each grant",
        "#",
        "# The DZ user role:",
        "#   - CAN call get-tables and see table metadata from the source account",
        "#   - CANNOT see the resource link databases in get-databases",
        "#",
        "# This prevents Athena and other query tools from discovering these databases.",
        "# ===========================================================================",
    ]

# Build output
output = [SUMMARY]
for i, line in enumerate(raw, 1):
    if i in annotations:
        for comment in annotations[i]:
            output.append(comment + '\n')
    output.append(line)

with open('experimental/AccountPoolFactory/.kiro/tmp/lf-trace-cli-output.txt', 'w') as f:
    f.writelines(output)

print(f"Annotated {len(annotations)} sections")
