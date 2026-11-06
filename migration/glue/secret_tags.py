"""Tag an existing connection secret so SMUS project roles can read it.

The secret is never copied and its value is never read. Access for project roles
comes from SageMakerStudioAdminIAMPermissiveExecutionPolicy:
  * ManagePrivateSecret: any secret that HAS an AmazonDataZoneProject tag
    (the value is not compared);
  * ManageSharedSecret: no AmazonDataZoneProject tag AND
    for-use-with-all-datazone-projects=true.
Both tag forms can grant access to other admin project roles. Untagged and
foreign-project secrets are shared automatically. A shared secret must never
gain a project tag.
"""
from __future__ import annotations

from dataclasses import dataclass

PROJECT_TAG = "AmazonDataZoneProject"
DOMAIN_TAG = "AmazonDataZoneDomain"
SHARED_TAG = "for-use-with-all-datazone-projects"


class ForeignProjectSecret(PermissionError):
    """Legacy exception retained for imports; automatic sharing no longer raises it."""


@dataclass(frozen=True)
class TagChange:
    secret_arn: str
    prior: dict  # tag key -> previous value, or None if the key was absent

    def to_json(self) -> dict:
        return {"secretArn": self.secret_arn, "prior": dict(self.prior)}

def plan_tags(tags: dict, *, domain_id: str, project_id: str, shared: bool = False) -> dict:
    """Tags to write; shared is accepted for compatibility and has no effect."""
    owner = tags.get(PROJECT_TAG)
    is_shared = tags.get(SHARED_TAG) == "true"
    if owner is None and is_shared:
        return {}  # already readable by every project; a project tag would break that
    if owner != project_id:
        return {} if is_shared else {SHARED_TAG: "true"}
    return {} if DOMAIN_TAG in tags else {DOMAIN_TAG: domain_id}


def restore_ops(prior: dict) -> tuple[dict, list]:
    """(tags to put back, keys to remove) that undo a change recorded as `prior`."""
    return ({k: v for k, v in prior.items() if v is not None},
            sorted(k for k, v in prior.items() if v is None))


def _current_tags(sm, arn: str) -> dict:
    return {t["Key"]: t.get("Value", "") for t in sm.describe_secret(SecretId=arn).get("Tags", [])}


def tag_secret(sm, arn: str, *, domain_id: str, project_id: str, shared: bool = False) -> TagChange:
    """Apply plan_tags and record prior tags; failed writes retain possible sharing grants."""
    tags = _current_tags(sm, arn)
    change = plan_tags(tags, domain_id=domain_id, project_id=project_id, shared=shared)
    tag_change = TagChange(secret_arn=arn, prior={k: tags.get(k) for k in change})
    if change:
        try:
            sm.tag_resource(SecretId=arn, Tags=[{"Key": k, "Value": v} for k, v in change.items()])
        except (Exception, KeyboardInterrupt) as err:
            # A timeout can occur after AWS applies the tags.
            try:
                restore_secret_tags(sm, tag_change, error=err)
            except (Exception, KeyboardInterrupt) as cleanup_err:
                err.add_note(
                    f"cleanup failed, do it manually: restore tags on {arn} "
                    f"to {tag_change.prior} ({cleanup_err})")
            raise
    return tag_change


def restore_secret_tags(sm, change: TagChange, *, error: BaseException | None = None) -> None:
    """Restore prior tags; automatic failure cleanup retains potentially adopted access."""
    prior = dict(change.prior)
    if error is not None and SHARED_TAG in prior:
        # A concurrent process may have adopted the grant; tag reads cannot prove otherwise.
        previous = prior.pop(SHARED_TAG)
        error.add_note(
            f"sharing grant retained if applied on {change.secret_arn}: {SHARED_TAG}=true; "
            f"before manual cleanup, verify no consumers need it, then restore its prior "
            f"value {previous!r} (None means absent)")
    retag, untag = restore_ops(prior)
    if untag:
        sm.untag_resource(SecretId=change.secret_arn, TagKeys=untag)
    if retag:
        sm.tag_resource(SecretId=change.secret_arn, Tags=[{"Key": k, "Value": v} for k, v in retag.items()])
