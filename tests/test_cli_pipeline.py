from typer.testing import CliRunner

from mddatanet.cli import app

from tests.helpers import write_ligand_unbinding_pdb


def test_cli_init_prepare_analyze_package_validate_publish_dry_run(tmp_path):
    runner = CliRunner()
    pdb = write_ligand_unbinding_pdb(tmp_path / "tiny.pdb")
    project = tmp_path / "project"
    parquet = tmp_path / "upload"

    init = runner.invoke(app, ["init", str(project)])
    assert init.exit_code == 0, init.output

    prepare = runner.invoke(
        app,
        [
            "prepare",
            str(project),
            "--topology",
            str(pdb),
            "--keep-solvent",
            "--chunk-size",
            "2",
            "--overwrite",
        ],
    )
    assert prepare.exit_code == 0, prepare.output
    assert (project / ".mddn_cache" / "mddatanet.json").exists()

    analyze = runner.invoke(
        app,
        [
            "analyze",
            str(project),
            "--preset",
            "ligand_unbinding",
            "--ligand",
            "resname LIG",
            "--pocket",
            "protein",
            "--param",
            "distance_threshold=5.0",
        ],
    )
    assert analyze.exit_code == 0, analyze.output

    tag = runner.invoke(
        app,
        [
            "tag",
            str(project),
            "--event",
            "ligand_unbinding",
            "--start-frame",
            "1",
            "--end-frame",
            "2",
        ],
    )
    assert tag.exit_code == 0, tag.output

    package = runner.invoke(app, ["package", str(project), "--hf-repo-link", "mddatanet/tiny"])
    assert package.exit_code == 0, package.output

    validate = runner.invoke(app, ["validate", str(project)])
    assert validate.exit_code == 0, validate.output
    inspect = runner.invoke(app, ["inspect", str(project)])
    assert inspect.exit_code == 0
    assert "ligand_unbinding" in inspect.output

    publish = runner.invoke(
        app,
        [
            "publish",
            str(project),
            "--repo-id",
            "mddatanet/tiny",
            "--dry-run-out",
            str(parquet),
        ],
    )
    assert publish.exit_code == 0, publish.output
    assert (parquet / "README.md").exists()
    assert (parquet / "data" / "train-00000-of-00001.parquet").exists()
