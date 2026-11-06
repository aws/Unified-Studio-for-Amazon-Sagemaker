"""gs-smus-discover CLI -- auto-match Glue jobs by project execution role.

Enumerates accessible DataZone domains/projects in the account (region-scoped),
resolves each project's execution role, lists the account's Glue jobs, and matches
a job's Role to a project's execution role. A unique match migrates that job into the
project (via migrate.migrate_job); zero matches are left alone; multiple matches
are reported as ambiguous and skipped.

Dry-run by default: prints the full plan (project roles, matched/unmatched/
ambiguous jobs) and mutates nothing. Pass --apply to run the migrations.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import discover, migrate, session as session_mod


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m migration.glue.discover_cli",
        description="Discover and migrate Glue jobs into SMUS projects by matching "
                    "a job's Role to a project's execution role.",
    )
    p.add_argument("--region", default="us-east-2")
    p.add_argument("--profile", default=None, help="AWS profile (else default credential chain)")
    p.add_argument("--domain-id", default=None, help="restrict discovery to one domain")
    p.add_argument("--project-id", default=None, help="restrict discovery to one project")
    p.add_argument("--apply", action="store_true", help="execute the matched migrations (default is dry-run)")
    args = p.parse_args(argv)

    sess = session_mod.build_session(profile=args.profile, region=args.region)
    glue = sess.client("glue")
    dz = session_mod.datazone_client(sess, args.region)
    account = sess.client("sts").get_caller_identity()["Account"]
    partition = sess.get_partition_for_region(args.region)

    project_roles, without_role = discover.collect_project_roles(
        dz, domain_filter=args.domain_id, project_filter=args.project_id)
    jobs = discover.list_glue_jobs(glue)
    plan = discover.plan_discovery(project_roles, jobs, account=account, partition=partition)
    plan.projects_without_role = without_role

    result = {"applied": False, "plan": plan.to_json()}

    if not args.apply:
        print("=== DRY-RUN (nothing changed) ===")
        _print_summary(plan)
        print(json.dumps(result, indent=2, default=str))
        return 0

    migrations = []
    for m in plan.matched:
        outcome = migrate.migrate_job(
            sess, job_name=m.job_name, domain_id=m.domain_id, project_id=m.project_id,
            region=args.region, apply=True)
        migrations.append({"jobName": m.job_name, "domainId": m.domain_id,
                           "projectId": m.project_id, "result": outcome})
    result["applied"] = True
    result["migrations"] = migrations
    print("=== APPLIED ===")
    _print_summary(plan)
    print(json.dumps(result, indent=2, default=str))
    return 0


def _print_summary(plan: discover.DiscoveryPlan) -> None:
    print(f"Projects with an execution role: {len(plan.project_roles)}")
    print(f"Projects without a resolvable execution role: {len(plan.projects_without_role)}")
    print(f"Matched jobs (will migrate): {len(plan.matched)}")
    for m in plan.matched:
        print(f"  - {m.job_name}  ->  {m.project_name} ({m.domain_id}/{m.project_id})")
    print(f"Unsupported jobs (skipped): {len(plan.unsupported)}")
    print(f"Unmatched jobs (left alone): {len(plan.unmatched)}")
    print(f"Ambiguous jobs (skipped -- role maps to >1 project): {len(plan.ambiguous)}")
    for a in plan.ambiguous:
        projs = ", ".join(f"{d}/{p}" for d, p in a.projects)
        print(f"  - {a.job_name}  ->  AMBIGUOUS [{projs}]")


if __name__ == "__main__":
    sys.exit(main())
