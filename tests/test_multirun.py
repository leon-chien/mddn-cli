import zarr
from typer.testing import CliRunner

from mddatanet.cli import app
from mddatanet.convert import convert_package
from mddatanet.format.provenance import read_provenance
from mddatanet.format.validation import inspect_package, validate_package
from mddatanet.splits.service import split_package
from mddatanet.utils.errors import PackageError

from tests.helpers import write_mismatched_pdb, write_tiny_multimodel_pdb


def test_multirun_convert_stores_run_arrays_and_trajectory_split(tmp_path):
    topology = write_tiny_multimodel_pdb(tmp_path / "topology.pdb")
    run_a = write_tiny_multimodel_pdb(tmp_path / "run_a.pdb")
    run_b = write_tiny_multimodel_pdb(tmp_path / "run_b.pdb")
    package = tmp_path / "multi.mddatanet"
    ready = tmp_path / "ready.mddatanet"

    convert_package(
        topology=topology,
        trajectory=[run_a, run_b],
        coordinates=None,
        name="multi",
        out=package,
        run_id=["run_a", "run_b"],
        overwrite=True,
    )
    split_package(input_path=package, out=ready, strategy="trajectory", train=0.5, val=0.0, test=0.5, overwrite=True)

    root = zarr.open_group(str(ready / "dataset.zarr"), mode="r")
    provenance = read_provenance(ready)
    summary = inspect_package(ready)
    assert validate_package(ready).ok
    assert [(run.run_id, run.package_start, run.package_stop) for run in provenance.runs] == [
        ("run_a", 0, 2),
        ("run_b", 2, 4),
    ]
    assert root["trajectory"]["run_ids"][:].tolist() == ["run_a", "run_a", "run_b", "run_b"]
    assert root["trajectory"]["source_frame_indices"][:].tolist() == [0, 1, 0, 1]
    assert root["splits"]["train"][:].tolist() == [0, 1]
    assert root["splits"]["test"][:].tolist() == [2, 3]
    assert summary["num_runs"] == 2


def test_cli_convert_accepts_repeated_trajectories(tmp_path):
    topology = write_tiny_multimodel_pdb(tmp_path / "topology.pdb")
    run_a = write_tiny_multimodel_pdb(tmp_path / "run_a.pdb")
    run_b = write_tiny_multimodel_pdb(tmp_path / "run_b.pdb")
    project = tmp_path / "multi"

    init = CliRunner().invoke(app, ["init", str(project)])
    assert init.exit_code == 0

    result = CliRunner().invoke(
        app,
        [
            "prepare",
            str(project),
            "--topology",
            str(topology),
            "--trajectory",
            str(run_a),
            "--trajectory",
            str(run_b),
            "--overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = __import__("json").loads((project / ".mddn_cache" / "mddatanet.json").read_text())
    assert len({shard["run_index"] for shard in manifest["shards"]}) == 2


def test_convert_rejects_mismatched_run_ids(tmp_path):
    topology = write_tiny_multimodel_pdb(tmp_path / "topology.pdb")
    run_a = write_tiny_multimodel_pdb(tmp_path / "run_a.pdb")
    run_b = write_tiny_multimodel_pdb(tmp_path / "run_b.pdb")

    try:
        convert_package(
            topology=topology,
            trajectory=[run_a, run_b],
            coordinates=None,
            name="bad",
            out=tmp_path / "bad.mddatanet",
            run_id=["only_one"],
        )
    except PackageError:
        return
    raise AssertionError("mismatched run IDs should be rejected")


def test_convert_rejects_incompatible_atom_counts(tmp_path):
    topology = write_tiny_multimodel_pdb(tmp_path / "topology.pdb")
    run_a = write_tiny_multimodel_pdb(tmp_path / "run_a.pdb")
    run_b = write_mismatched_pdb(tmp_path / "run_b.pdb")

    try:
        convert_package(
            topology=topology,
            trajectory=[run_a, run_b],
            coordinates=None,
            name="bad",
            out=tmp_path / "bad.mddatanet",
        )
    except Exception:
        return
    raise AssertionError("incompatible atom counts should be rejected")
