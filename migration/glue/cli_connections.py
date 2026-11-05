"""Clone connections into an SMUS project without changing any job."""
from __future__ import annotations

import argparse
import json
import sys

from . import connmigrate, session as session_mod


def _clients(args) -> dict:
    sess = session_mod.build_session(profile=args.profile, region=args.region)
    return {"glue": sess.client("glue"), "sm": sess.client("secretsmanager"),
            "dz": session_mod.datazone_client(sess, args.domain_region or args.region)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m migration.glue.cli_connections",
        description="Clone Glue connections into an SMUS project; jobs and scripts are unchanged.")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--job-name", help="read the connections attached to this job")
    source.add_argument("--connection-name", action="append",
                        help="connection to clone (repeat for multiple connections)")
    p.add_argument("--domain-id", required=True)
    p.add_argument("--project-id", required=True)
    p.add_argument("--region", default="us-east-2")
    p.add_argument("--domain-region", default=None,
                   help="DataZone domain region (defaults to --region)")
    p.add_argument("--profile", default=None)
    p.add_argument("--shared-secret", action="store_true",
                   help="compatibility option; untagged and foreign-project secrets are shared automatically")
    p.add_argument("--apply", action="store_true", help="execute (default is dry-run)")
    args = p.parse_args(argv)

    c = _clients(args)
    if args.job_name:
        job = c["glue"].get_job(JobName=args.job_name)["Job"]
        names = (job.get("Connections") or {}).get("Connections") or []
    else:
        names = args.connection_name
    result = connmigrate.migrate_connections(
        **c, names=names, domain_id=args.domain_id, project_id=args.project_id,
        apply=args.apply, shared_secret=args.shared_secret)
    print(f"=== {'APPLIED' if result['applied'] else 'DRY-RUN (nothing changed)'} ===")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
