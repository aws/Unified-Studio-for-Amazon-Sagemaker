#!/usr/bin/env python3
"""
Delete a DataZone project and wait for deletion to complete.

Usage:
    python3 tests/integration/delete-project.py <project_id> [--timeout 300]
"""
import sys
import os
import time
import argparse
import boto3
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..', '..')

_cfg_file = os.path.join(PROJECT_ROOT, '02-domain-account/config.yaml')
if not os.path.exists(_cfg_file):
    _cfg_file = os.path.join(PROJECT_ROOT, 'config.yaml')
with open(_cfg_file) as f:
    config = yaml.safe_load(f)

DOMAIN_ID = config.get('domain_id') or config.get('datazone', {}).get('domain_id', '')
REGION    = config.get('region') or config.get('aws', {}).get('region', 'us-east-2')


def delete_project(project_id: str, timeout: int) -> bool:
    dz = boto3.client('datazone', region_name=REGION)

    print(f"Deleting project {project_id}...")
    try:
        dz.delete_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
        print(f"  Delete request accepted")
    except dz.exceptions.ResourceNotFoundException:
        print(f"  Project {project_id} not found — already deleted")
        return True
    except Exception as e:
        print(f"❌ Delete failed: {e}")
        return False

    # Poll until project is gone
    start = time.time()
    interval = 15
    print(f"Waiting for project deletion (timeout={timeout}s)...")

    while time.time() - start < timeout:
        try:
            proj = dz.get_project(domainIdentifier=DOMAIN_ID, identifier=project_id)
            status = proj.get('projectStatus', 'UNKNOWN')
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] projectStatus={status}")
            if status in ('DELETE_FAILED',):
                print(f"❌ Project deletion failed with status: {status}")
                return False
        except dz.exceptions.ResourceNotFoundException:
            elapsed = int(time.time() - start)
            print(f"\n✅ Project {project_id} deleted after {elapsed}s")
            return True
        except Exception as e:
            print(f"  Warning: {e}")
        time.sleep(interval)

    print(f"\n❌ Timeout: project {project_id} not deleted within {timeout}s")
    return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('project_id', help='DataZone project ID to delete')
    parser.add_argument('--timeout', type=int, default=300, help='Max wait seconds (default: 300)')
    args = parser.parse_args()

    ok = delete_project(args.project_id, args.timeout)
    sys.exit(0 if ok else 1)
