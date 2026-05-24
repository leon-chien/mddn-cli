from typer.testing import CliRunner

from mddatanet.cli import app


def test_cli_help_works():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "mddatanet" in result.output.lower()


def test_documented_command_help_works():
    runner = CliRunner()
    commands = [
        ["convert"],
        ["featurize"],
        ["label"],
        ["split"],
        ["validate"],
        ["inspect"],
        ["pack"],
        ["unpack"],
        ["card"],
        ["export-manifest"],
        ["export-schema"],
        ["demo"],
        ["presets", "list"],
        ["presets", "show"],
        ["presets", "explain"],
    ]

    for command in commands:
        args = [*command, "--help"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0, args
