"""Property-based tests for Glue connection name -> DataZone connection name.

See the adjacent README.md for dependencies and test commands.
"""
import re

from hypothesis import given, strategies as st

from migration.glue import naming

# Glue ConnectionInput.Name: 1-255 chars of [\u0020-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF\t].
_glue_char = st.one_of(
    st.just("\t"),
    st.characters(min_codepoint=0x20, blacklist_categories=("Cs",)).filter(
        lambda c: c not in "\ufffe\uffff"
    ),
)
glue_names = st.text(alphabet=_glue_char, min_size=1, max_size=255)

# Generated names fit the SMUS UI's 41-character limit and contain no '.'.
DATAZONE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]{0,40}$")
P = "project-example"
projects = st.from_regex(r"[a-z0-9]{1,36}", fullmatch=True)


def _dz(name, project=P):
    return naming.datazone_connection_name(name, project_id=project)


def _resolve(name, existing, project=P):
    return naming.resolve_datazone_connection_name(name, existing, project_id=project)


@given(glue_names)
def test_output_is_datazone_valid(name):
    assert DATAZONE_NAME.fullmatch(_dz(name))


@given(glue_names)
def test_deterministic(name):
    assert _dz(name) == _dz(name)


@given(glue_names, glue_names)
def test_distinct_inputs_give_distinct_outputs(a, b):
    if a != b:
        assert _dz(a) != _dz(b)


@given(glue_names)
def test_ends_with_hash_and_clone_suffix(name):
    assert re.search(r"-[0-9a-f]{8}-SMUSClone$", _dz(name))


@given(st.from_regex(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,21}", fullmatch=True))
def test_already_valid_short_name_is_kept_as_readable_prefix(name):
    assert _dz(name).startswith(name + "-")


@given(glue_names, projects, projects)
def test_same_connection_in_two_projects_gets_two_names(name, p1, p2):
    """Glue connection names are account-wide and DataZone names the clone after the
    DataZone connection, so the project must be part of the name."""
    if p1 != p2:
        assert _dz(name, project=p1) != _dz(name, project=p2)


@given(glue_names, projects)
def test_names_never_contain_a_dot(name, project):
    assert "." not in _dz(name, project=project)


def test_names_differing_only_in_sanitized_chars_do_not_collide():
    # "a b" and "a_b" sanitize to the same prefix; the hash must separate them.
    assert _dz("a b") != _dz("a_b")


# Glue connection Name: 1-255, single-line Unicode (botocore glue ConnectionInput.Name).
GLUE_NAME = re.compile("^[\u0020-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF\t]{1,255}$")
glue_names = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r")
    .filter(lambda c: c == "\t" or ord(c) >= 0x20),
    min_size=1, max_size=255,
).filter(lambda n: GLUE_NAME.match(n))


# --- DataZone name dedupe -------------------------------------------------
# `existing` models the target scope's DataZone connections:
#   DataZone connection name -> source Glue connection it was migrated from
#   (our ownership marker), or None if it is not ours.
import pytest  # noqa: E402


@pytest.mark.parametrize("length", [22, 23, 255])
def test_long_name_keeps_hash_and_clone_suffix_within_ui_limit(length):
    out = _dz("a" * length)
    assert len(out) == 41
    assert out.startswith("a" * 22 + "-")
    assert re.search(r"-[0-9a-f]{8}-SMUSClone$", out)


@given(glue_names)
def test_no_existing_gives_base_name(name):
    r = _resolve(name, {})
    assert r == naming.ResolvedName(_dz(name), reuse=False)


@given(glue_names)
def test_prior_migration_is_reused(name):
    existing = {_dz(name): name}
    assert _resolve(name, existing) == naming.ResolvedName(_dz(name), reuse=True)


@given(glue_names)
def test_rerun_is_idempotent(name):
    """Creating the resolved connection, then resolving again, returns the same name as reuse."""
    r = _resolve(name, {})
    assert _resolve(name, {r.name: name}) == naming.ResolvedName(r.name, reuse=True)


@given(glue_names)
def test_unknown_ownership_raises_immediately(name):
    candidate = _dz(name)
    with pytest.raises(ValueError, match=re.escape(candidate)):
        _resolve(name, {candidate: None})


@given(glue_names, glue_names)
def test_foreign_ownership_raises_immediately(name, foreign_source):
    if foreign_source != name:
        candidate = _dz(name)
        with pytest.raises(ValueError, match=re.escape(candidate)):
            _resolve(name, {candidate: foreign_source})


@given(glue_names, glue_names)
def test_source_marker_distinguishes_sources(a, b):
    assert (naming.source_marker(a) == naming.source_marker(b)) == (a == b)
    assert len(naming.source_marker(a)) < 40


@given(glue_names, st.text(max_size=40), st.text(max_size=40))
def test_clone_marker_is_recognised_anywhere_in_a_description(name, before, after):
    assert naming.is_clone_description(before + naming.source_marker(name) + after)


@given(st.text(max_size=200).filter(lambda t: "[gs-smus-src:" not in t))
def test_description_without_marker_is_not_a_clone(desc):
    assert not naming.is_clone_description(desc)
