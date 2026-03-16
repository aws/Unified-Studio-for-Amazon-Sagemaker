#!/usr/bin/env python3
"""Delete a project and wait for full completion."""
import boto3, sys, time

DOMAIN_ID = 'dzd-4h7jbz76qckoh5'
REGION = 'us-east-2'
PROJECT_ID = sys.argv[1] if len(sys.argv) > 1 else 'ccs8js7cy92p7t'

dz = boto3.client('datazone', region_name=REGION)

print(f"Deleting project {PROJECT_ID}...")

# Delete data sources
try:
    ds_resp = dz.list_data_sources(domainIdentifier=DOMAIN_ID, projectIdentifier=PROJECT_ID)
    for ds in ds_resp.get('items', []):
        print(f"  Deleting data source {ds['dataSourceId']}...")
        try:
            dz.delete_data_source(domainIdentifier=DOMAIN_ID, identifier=ds['dataSourceId'])
        except Exception as e:
            print(f"    Warning: {e}")
except Exception as e:
    print(f"  Data sources: {e}")

# Delete environments
start = time.time()
while time.time() - start < 300:
    try:
        envs = dz.list_environments(domainIdentifier=DOMAIN_ID, projectIdentifier=PROJECT_ID)
        active = [e for e in envs.get('items', []) if e.get('status') not in ('DELETED',)]
        if not active:
            break
        for env in active:
            if env.get('status') not in ('DELETE_IN_PROGRESS',):
                print(f"  Deleting env {env['id']} ({env.get('status')})...")
                try:
                    dz.delete_environment(domainIdentifier=DOMAIN_ID, identifier=env['id'])
                except Exception:
                    pass
    except Exception:
        break
    time.sleep(10)

# Delete project
try:
    dz.delete_project(domainIdentifier=DOMAIN_ID, identifier=PROJECT_ID)
    print("  Delete request accepted")
except Exception as e:
    print(f"  Delete error: {e}")

# Wait for deletion
start = time.time()
while time.time() - start < 300:
    try:
        proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=PROJECT_ID)
        status = proj.get('projectStatus', '?')
        print(f"  [{int(time.time()-start)}s] status={status}")
        if status == 'DELETE_FAILED':
            print("FAILED")
            sys.exit(1)
    except dz.exceptions.ResourceNotFoundException:
        print(f"  Project deleted after {int(time.time()-start)}s")
        break
    time.sleep(15)

print("Done")
