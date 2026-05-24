from typer.testing import CliRunner

from mddatanet.cli import app


def test_cli_help_works():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "mddatanet" in result.output.lower()

