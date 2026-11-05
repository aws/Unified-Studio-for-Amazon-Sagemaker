"""The local module commands work without installing the migration package."""
from pathlib import Path
import subprocess
import sys

import pytest

from migration.glue import cli, cli_connections, discover_cli


@pytest.mark.parametrize("module", [
    "migration.glue.cli",
    "migration.glue.cli_connections",
    "migration.glue.discover_cli",
])
def test_module_help_from_repository_root(module):
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert f"python -m {module}" in result.stdout
    assert "--apply" in result.stdout


@pytest.mark.parametrize("entrypoint,args", [
    (cli.main, ["--job-name", "job", "--domain-id", "domain", "--project-id", "project"]),
    (cli_connections.main, [
        "--connection-name", "connection", "--domain-id", "domain", "--project-id", "project"]),
    (discover_cli.main, []),
])
def test_unknown_option_rejected_before_aws_access(monkeypatch, capsys, entrypoint, args):
    monkeypatch.setattr(cli.session_mod, "build_session",
                        lambda **kw: pytest.fail("created AWS session"))
    with pytest.raises(SystemExit) as error:
        entrypoint([*args, "--unknown-option"])
    assert error.value.code == 2
    assert "unrecognized arguments: --unknown-option" in capsys.readouterr().err
