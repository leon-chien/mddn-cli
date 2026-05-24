import zipfile
from pathlib import Path

from typer.testing import CliRunner

from mddatanet.cli import app
from mddatanet.demo import run_ligand_unbinding_demo
from mddatanet.format.validation import inspect_package, validate_package


def test_ligand_unbinding_demo_creates_valid_package(tmp_path):
    result = run_ligand_unbinding_demo(output_dir=tmp_path, overwrite=True)

    assert result.output_zip.exists()
    assert result.validation_ok is True
    assert 0.0 < result.event_positive_rate < 1.0

    validation = validate_package(result.output_zip)
    summary = inspect_package(result.output_zip, include_features=True, include_labels=True)
    assert validation.ok
    assert "ligand_pocket_min_distance" in summary["feature_arrays"]
    assert "ligand_unbinding" in summary["label_arrays"]
    with zipfile.ZipFile(result.output_zip) as archive:
        card_name = next(name for name in archive.namelist() if name.endswith("dataset_card.md"))
        assert "Synthetic runtime demo" in archive.read(card_name).decode("utf-8")


def test_cli_demo_default_and_named_demo(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        default_result = runner.invoke(app, ["demo"])
        named_result = runner.invoke(app, ["demo", "ligand_unbinding"])

        assert default_result.exit_code == 0
        assert named_result.exit_code == 0
        package = Path("outputs/ligand_unbinding_demo.mddatanet.zip")
        assert package.exists()
        assert validate_package(package).ok


def test_cli_demo_unknown_name_fails():
    result = CliRunner().invoke(app, ["demo", "not_a_demo"])

    assert result.exit_code == 1
    assert "Unknown demo" in result.output


def test_cli_demo_alanine_alias_runs_ligand_demo(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["demo", "alanine"])

        assert result.exit_code == 0
        assert "running ligand_unbinding" in result.output
        assert Path("outputs/ligand_unbinding_demo.mddatanet.zip").exists()
