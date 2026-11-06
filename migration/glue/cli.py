"""gs-smus-migrate CLI -- single script-job migration, dry-run by default."""
from __future__ import annotations

import argparse
import json
import sys

from . import migrate, session as session_mod


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m migration.glue.cli",
        description="Migrate a Glue script job into a SageMaker Unified Studio project.",
    )
    p.add_argument("--job-name", required=True)
    p.add_argument("--domain-id", required=True)
    p.add_argument("--project-id", required=True)
    p.add_argument("--bucket", default=None,
                   help="SMUS project default S3 bucket (optional override; "
                        "resolved from DataZone when omitted)")
    p.add_argument("--region", default="us-east-2")
    p.add_argument("--domain-region", default=None,
                   help="DataZone domain region (defaults to --region)")
    p.add_argument("--profile", default=None, help="AWS profile (else default credential chain)")
    p.add_argument("--apply", action="store_true", help="execute (default is dry-run)")
    args = p.parse_args(argv)

    sess = session_mod.build_session(profile=args.profile, region=args.region)
    result = migrate.migrate_job(
        sess,
        job_name=args.job_name,
        bucket=args.bucket,
        domain_id=args.domain_id,
        project_id=args.project_id,
        region=args.region,
        domain_region=args.domain_region,
        apply=args.apply,
    )

    if result.get("skipped") and result["applied"]:
        mode = "APPLIED (PassRole ensured; job already belongs to project)"
    elif result.get("skipped") and result["passRole"]["needsUpdate"]:
        mode = "DRY-RUN (PassRole planned; job already belongs to project)"
    elif result.get("skipped"):
        mode = "SKIPPED (already belongs to project)"
    elif result["applied"]:
        mode = "APPLIED"
    else:
        mode = "DRY-RUN (nothing changed)"
    print(f"=== {mode} ===")
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
