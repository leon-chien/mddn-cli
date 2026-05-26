from pathlib import Path

from typer.testing import CliRunner

from mddatanet.cli import app
from mddatanet.demo import run_ligand_unbinding_demo
from mddatanet.hf.workspace import validate_workspace


def test_ligand_unbinding_demo_creates_hf_staging_and_parquet(tmp_path):
    result = run_ligand_unbinding_demo(output_dir=tmp_path, overwrite=True)

    assert result.project_dir.exists()
    assert result.parquet_dir.exists()
    assert result.validation_ok is True
    assert 0.0 < result.event_positive_rate < 1.0
    assert not validate_workspace(result.project_dir)
    assert (result.parquet_dir / "metadata_index" / "index-00000-of-00001.parquet").exists()


def test_cli_demo_default_and_named_demo(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        default_result = runner.invoke(app, ["demo"])
        named_result = runner.invoke(app, ["demo", "ligand_unbinding"])

        assert default_result.exit_code == 0, default_result.output
        assert named_result.exit_code == 0, named_result.output
        project = Path("outputs/ligand_unbinding_demo_hf")
        assert project.exists()
        assert not validate_workspace(project)


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
        assert Path("outputs/ligand_unbinding_demo_hf").exists()
