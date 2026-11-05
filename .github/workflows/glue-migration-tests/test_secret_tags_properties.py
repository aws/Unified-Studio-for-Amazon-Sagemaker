"""Property tests for secret tagging (pure planning + restore)."""
from unittest.mock import Mock

import pytest
from hypothesis import given, strategies as st

from migration.glue import secret_tags as st_mod
from migration.glue.secret_tags import PROJECT_TAG, DOMAIN_TAG, SHARED_TAG

D, P = "dzd-mine", "proj-mine"
_ids = st.sampled_from(["proj-mine", "proj-other", "x"])
_other = st.dictionaries(st.sampled_from(["team", "env", "Name"]), st.text(min_size=1, max_size=5), max_size=2)


@st.composite
def tag_sets(draw):
    tags = draw(_other)
    if draw(st.booleans()):
        tags[PROJECT_TAG] = draw(_ids)
    if draw(st.booleans()):
        tags[DOMAIN_TAG] = draw(st.sampled_from([D, "dzd-other"]))
    if draw(st.booleans()):
        tags[SHARED_TAG] = draw(st.sampled_from(["true", "false"]))
    return tags


def project_can_read(tags):
    """Model of SageMakerStudioAdminIAMPermissiveExecutionPolicy secret statements."""
    return PROJECT_TAG in tags or tags.get(SHARED_TAG) == "true"


def other_projects_can_read(tags):
    return project_can_read(tags)


def _apply(tags, change):
    out = dict(tags)
    out.update(change)
    return out


def _plan(tags, shared):
    return st_mod.plan_tags(tags, domain_id=D, project_id=P, shared=shared)


@given(tag_sets(), st.booleans())
def test_after_tagging_project_can_read(tags, shared):
    change = _plan(tags, shared)
    assert project_can_read(_apply(tags, change))


@given(tag_sets(), st.booleans())
def test_never_touches_existing_project_tag_or_shared_access(tags, shared):
    change = _plan(tags, shared)
    if PROJECT_TAG in tags:
        assert PROJECT_TAG not in change
    if other_projects_can_read(tags):
        assert other_projects_can_read(_apply(tags, change))


@given(tag_sets(), st.booleans())
def test_only_datazone_keys_written(tags, shared):
    change = _plan(tags, shared)
    assert set(change) <= {PROJECT_TAG, DOMAIN_TAG, SHARED_TAG}
    assert all(tags.get(k) != v for k, v in change.items())  # no no-op writes


@given(tag_sets(), st.booleans())
def test_foreign_project_is_shared_without_changing_ownership(tags, shared):
    if tags.get(PROJECT_TAG) not in (None, P):
        after = _apply(tags, _plan(tags, shared))
        assert after[SHARED_TAG] == "true"
        assert after[PROJECT_TAG] == tags[PROJECT_TAG]


@given(tag_sets(), st.booleans())
def test_idempotent(tags, shared):
    change = _plan(tags, shared)
    assert _plan(_apply(tags, change), shared) == {}


@pytest.mark.parametrize("tags", [{}, {DOMAIN_TAG: D}, {SHARED_TAG: "false"}, {"team": "data"}])
@pytest.mark.parametrize("shared", [False, True])
def test_private_secret_without_project_is_shared_automatically(tags, shared):
    assert _plan(tags, shared) == {SHARED_TAG: "true"}


@given(tag_sets(), st.booleans())
def test_restore_ops_invert_change(tags, shared):
    change = _plan(tags, shared)
    prior = {k: tags.get(k) for k in change}
    retag, untag = st_mod.restore_ops(prior)
    after = _apply(tags, change)
    after.update(retag)
    for k in untag:
        after.pop(k)
    assert after == tags


def test_tag_secret_preserves_tag_without_value():
    sm = Mock(spec=["describe_secret", "tag_resource"])
    sm.describe_secret.return_value = {
        "Tags": [{"Key": PROJECT_TAG, "Value": P}, {"Key": DOMAIN_TAG}]}
    change = st_mod.tag_secret(sm, "secret", domain_id=D, project_id=P)
    assert change.prior == {}
    sm.tag_resource.assert_not_called()


@pytest.mark.parametrize("prior", [None, "false", ""])
@pytest.mark.parametrize("error_type", [TimeoutError, KeyboardInterrupt])
def test_failed_tag_write_retains_possible_sharing_grant(prior, error_type):
    original = {"team": "data"}
    if prior is not None:
        original[SHARED_TAG] = prior
    tags = dict(original)
    sm = Mock(spec=["describe_secret", "tag_resource", "untag_resource"])
    sm.describe_secret.return_value = {
        "Tags": [{"Key": k, "Value": v} for k, v in tags.items()]}
    failure = error_type("tag write interrupted")

    def write_tags(*, SecretId, Tags):
        assert SecretId == "secret"
        tags.update({t["Key"]: t["Value"] for t in Tags})
        if tags[SHARED_TAG] == "true":
            raise failure

    def remove_tags(*, SecretId, TagKeys):
        assert SecretId == "secret"
        for key in TagKeys:
            tags.pop(key, None)

    sm.tag_resource.side_effect = write_tags
    sm.untag_resource.side_effect = remove_tags
    with pytest.raises(error_type) as err:
        st_mod.tag_secret(sm, "secret", domain_id=D, project_id=P, shared=True)
    assert err.value is failure
    assert tags == {**original, SHARED_TAG: "true"}
    sm.untag_resource.assert_not_called()
    assert any("secret" in note and SHARED_TAG in note and "retained" in note
               and repr(prior) in note and "manual" in note for note in failure.__notes__)


@pytest.mark.parametrize("cleanup_type", [PermissionError, KeyboardInterrupt])
def test_failed_metadata_cleanup_preserves_original_error_and_reports_prior(cleanup_type):
    sm = Mock(spec=["describe_secret", "tag_resource", "untag_resource"])
    sm.describe_secret.return_value = {"Tags": [{"Key": PROJECT_TAG, "Value": P}]}
    failure = TimeoutError("tag write timed out")
    sm.tag_resource.side_effect = failure
    sm.untag_resource.side_effect = cleanup_type("cleanup denied")
    with pytest.raises(TimeoutError) as err:
        st_mod.tag_secret(sm, "secret", domain_id=D, project_id=P)
    assert err.value is failure
    assert any("secret" in note and DOMAIN_TAG in note and "None" in note
               and "cleanup denied" in note for note in err.value.__notes__)
