#!/usr/bin/env python3
"""
Delete all DataZone projects in parallel (except a preserve list),
then wait for all environments to be fully deleted.

Usage:
    eval $(isengardcli credentials amirbo+3@amazon.com)
    python3 02-domain-account/scripts/utils/delete-all-projects.py [--dry-run]
"""
import sys
import os
import time
import argparse
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed

REGION    = 'us-east-2'
DOMAIN_ID = 'dzd-4h7jbz76qckoh5'
PRESERVE  = {'5nqv5cescnezl5'}  # GenerativeAIModelGovernanceProject

dz = boto3.client('datazone', region_name=REGION)


def list_all_projects():
    projects = []
    kwargs = {'domainIdentifier': DOMAIN_ID, 'maxResults': 50}
    while True:
        resp = dz.list_projects(**kwargs)
        projects.extend(resp.get('items', []))
        token = resp.get('nextToken')
        if not token:
            break
        kwargs['nextToken'] = token
    return projects


def wait_envs_deleted(project_id, timeout=900):
    """Wait until all environments in the project are DELETED or gone."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = dz.list_environments(domainIdentifier=DOMAIN_ID, projectIdentifier=project_id)
            active = [e for e in resp.get('items', [])
                      if e.get('status') not in ('DELETED', 'DELETE_FAILED')]
            if not active:
                return True
            statuses = [e.get('status') for e in active]
            elapsed = int(time.time() - start)
            print(f"  [{project_id}] [{elapsed}s] waiting for {len(active)} envs: {statuses}")
        except dz.exceptions.ResourceNotFoundException:
            return True
        except Exception as e:
            # AccessDenied after project delete is expected — treat as done
            if 'AccessDenied' in str(e) or 'not permitted' in str(e):
                return True
            print(f"  [{project_id}] Warning listing envs: {e}")
        time.sleep(20)
    print(f"  [{project_id}] ⚠️  Timeout waiting for env deletion")
    return False


def delete_and_wait(project):
    pid  = project['id']
    name = project['name']

    # Step 1: delete data sources
    try:
        resp = dz.list_data_sources(domainIdentifier=DOMAIN_ID, projectIdentifier=pid)
        for ds in resp.get('items', []):
            ds_id = ds['dataSourceId']
            try:
                dz.delete_data_source(domainIdentifier=DOMAIN_ID, identifier=ds_id)
                print(f"  [{pid}] deleted data source {ds_id}")
            except Exception as e:
                print(f"  [{pid}] warning deleting data source {ds_id}: {e}")
    except Exception as e:
        print(f"  [{pid}] warning listing data sources: {e}")

    # Step 2: delete environments
    try:
        resp = dz.list_environments(domainIdentifier=DOMAIN_ID, projectIdentifier=pid,
                                    status='ACTIVE')
        for env in resp.get('items', []):
            env_id = env['id']
            try:
                dz.delete_environment(domainIdentifier=DOMAIN_ID, identifier=env_id)
                print(f"  [{pid}] delete issued for env {env_id}")
            except Exception as e:
                print(f"  [{pid}] warning deleting env {env_id}: {e}")
    except Exception as e:
        print(f"  [{pid}] warning listing environments: {e}")

    # Step 3: wait for environments to finish deleting
    ok = wait_envs_deleted(pid)
    if not ok:
        print(f"  [{pid}] ⚠️  some envs still present, proceeding anyway")

    # Step 4: issue project delete
    try:
        dz.delete_project(domainIdentifier=DOMAIN_ID, identifier=pid)
        print(f"  [{pid}] project delete issued ({name})")
    except dz.exceptions.ResourceNotFoundException:
        print(f"  [{pid}] already gone ({name})")
        return pid, True
    except Exception as e:
        print(f"  [{pid}] ❌ project delete failed: {e}")
        return pid, False

    # Step 5: wait for project to disappear
    start = time.time()
    while time.time() - start < 300:
        try:
            proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=pid)
            status = proj.get('projectStatus', '?')
            if status == 'DELETE_FAILED':
                print(f"  [{pid}] ❌ DELETE_FAILED")
                return pid, False
        except dz.exceptions.ResourceNotFoundException:
            elapsed = int(time.time() - start)
            print(f"  [{pid}] ✅ deleted ({elapsed}s)")
            return pid, True
        time.sleep(15)

    print(f"  [{pid}] ⚠️  project still exists after 300s")
    return pid, False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    projects = list_all_projects()
    to_delete = [p for p in projects if p['id'] not in PRESERVE]

    print(f"Found {len(projects)} projects, {len(to_delete)} to delete, {len(PRESERVE)} preserved")
    for p in to_delete:
        print(f"  {p['id']}  {p['name']}")

    if args.dry_run:
        print("\nDry run — no deletions performed")
        return

    print(f"\nDeleting {len(to_delete)} projects in parallel...")
    results = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(delete_and_wait, p): p['id'] for p in to_delete}
        for f in as_completed(futures):
            pid, ok = f.result()
            results[pid] = ok

    succeeded = sum(1 for ok in results.values() if ok)
    failed    = sum(1 for ok in results.values() if not ok)
    print(f"\n{'='*50}")
    print(f"Done: {succeeded} deleted, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
