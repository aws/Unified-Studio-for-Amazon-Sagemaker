"""Standalone connection cloning never needs job updates or S3 access."""
from unittest.mock import Mock

import pytest

from migration.glue import cli, cli_connections, connmigrate, discover_cli, migrate

BASE = ["--domain-id", "dzd-1", "--project-id", "p1", "--region", "eu-north-1"]


@pytest.fixture
def calls(monkeypatch):
    got = {}
    glue = Mock(spec=["get_job"])
    glue.get_job.return_value = {"Job": {"Connections": {"Connections": ["old-a", "old-b"]}}}
    monkeypatch.setattr(cli_connections, "_clients", lambda args: {"glue": glue, "sm": 3, "dz": 4})
    monkeypatch.setattr(connmigrate, "migrate_connections", lambda **kw:
                        got.update(kw) or {"applied": kw["apply"], "connections": []})
    return got, glue


def test_dry_run_reads_job_connections_without_updating_job(calls):
    got, glue = calls
    assert cli_connections.main(["--job-name", "j", *BASE]) == 0
    assert (got["names"], got["apply"], got["shared_secret"]) == (["old-a", "old-b"], False, False)
    glue.get_job.assert_called_once_with(JobName="j")
    assert set(got) == {"glue", "sm", "dz", "names", "domain_id", "project_id", "apply", "shared_secret"}


def test_explicit_connections_do_not_read_a_job(calls):
    got, glue = calls
    cli_connections.main(["--connection-name", "a", "--connection-name", "b", *BASE, "--apply", "--shared-secret"])
    assert (got["names"], got["apply"], got["shared_secret"]) == (["a", "b"], True, True)
    glue.get_job.assert_not_called()


def test_no_connections_is_valid(calls):
    got, glue = calls
    glue.get_job.return_value = {"Job": {}}
    assert cli_connections.main(["--job-name", "j", *BASE]) == 0
    assert got["names"] == []


@pytest.mark.parametrize("options", [[], ["--job-name", "j", "--connection-name", "a"],
                                       ["--job-name", "j", "--scan"],
                                       ["--job-name", "j", "--rollback", "old.json"]])
def test_invalid_or_removed_options_are_rejected(calls, options):
    with pytest.raises(SystemExit):
        cli_connections.main([*BASE, *options])


def test_job_migration_cli_never_clones_connections(monkeypatch):
    monkeypatch.setattr(cli.session_mod, "build_session", lambda **kw: None)
    monkeypatch.setattr(migrate, "migrate_job", lambda *a, **kw: {"applied": False})
    monkeypatch.setattr(connmigrate, "migrate_connections", lambda **kw: pytest.fail("called"))
    assert cli.main(["--job-name", "j", "--domain-id", "d", "--project-id", "p"]) == 0


@pytest.mark.parametrize("entrypoint,options", [
    (cli.main, ["--job-name", "j", *BASE]),
    (discover_cli.main, []),
])
def test_job_migration_clis_reject_force_before_creating_session(
        monkeypatch, capsys, entrypoint, options):
    monkeypatch.setattr(cli.session_mod, "build_session",
                        lambda **kw: pytest.fail("created AWS session"))
    with pytest.raises(SystemExit) as error:
        entrypoint([*options, "--force", "--apply"])
    assert error.value.code == 2
    assert "unrecognized arguments: --force" in capsys.readouterr().err
