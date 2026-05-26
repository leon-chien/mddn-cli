from typer.testing import CliRunner

from mddatanet.cli import app


def test_cli_help_works():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "mddatanet" in result.output.lower()


def test_documented_command_help_works():
    runner = CliRunner()
    commands = [
        ["init"],
        ["inspect"],
        ["prepare"],
        ["analyze"],
        ["tag"],
        ["package"],
        ["validate"],
        ["publish"],
        ["load"],
        ["benchmark"],
        ["demo"],
        ["presets", "list"],
        ["presets", "show"],
        ["presets", "explain"],
    ]

    for command in commands:
        args = [*command, "--help"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0, args


def test_removed_package_commands_are_not_public():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("convert", "push-to-hub", "convert-and-tag", "split-package", "unpack", "export-manifest"):
        assert command not in result.output
