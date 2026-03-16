#!/usr/bin/env python3
"""Debug: inspect DataZone Athena connection structure."""
import json, boto3, yaml, os

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
with open(os.path.join(PROJECT_ROOT, 'domain-config.yaml')) as f:
    cfg = yaml.safe_load(f)

DOMAIN_ID = cfg.get('domain_id', '')
REGION = cfg.get('region', 'us-east-2')

# Use a known project that has an Athena connection
# We'll list recent projects to find one
dz = boto3.client('datazone', region_name=REGION)

# List projects to find one with environments
projects = dz.list_projects(domainIdentifier=DOMAIN_ID, maxResults=5)
for p in projects.get('items', []):
    pid = p['id']
    pname = p['name']
    print(f"\nProject: {pname} ({pid})")
    try:
        conns = dz.list_connections(
            domainIdentifier=DOMAIN_ID,
            projectIdentifier=pid,
        )
        for c in conns.get('items', []):
            cid = c.get('connectionId', '')
            ctype = c.get('type', '')
            print(f"  Connection: {cid} type={ctype}")
            if ctype == 'ATHENA':
                detail = dz.get_connection(
                    domainIdentifier=DOMAIN_ID,
                    identifier=cid,
                    withSecret=True
                )
                # Print the full response structure (redact secrets)
                for key in detail:
                    if key == 'ResponseMetadata':
                        continue
                    val = detail[key]
                    if isinstance(val, dict) and 'secret' in str(val).lower():
                        print(f"  {key}: [REDACTED]")
                    else:
                        print(f"  {key}: {json.dumps(val, default=str, indent=4)}")
    except Exception as e:
        print(f"  Error: {e}")
