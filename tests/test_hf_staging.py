import json

import numpy as np
import pyarrow.parquet as pq
import pytest

from mddatanet.hf.workspace import (
    analyze_workspace,
    init_workspace,
    package_workspace,
    prepare_workspace,
    tag_workspace,
    validate_workspace,
)
from mddatanet.utils.errors import PackageError

from tests.helpers import write_ligand_unbinding_pdb


def _prepared_project(tmp_path, *, keep_solvent=True):
    pdb = write_ligand_unbinding_pdb(tmp_path / "tiny.pdb")
    project = tmp_path / "project"
    init_workspace(project)
    prepare_workspace(
        project_root=project,
        topology=pdb,
        keep_solvent=keep_solvent,
        chunk_size=2,
        overwrite=True,
    )
    return project


def test_init_refuses_overwrite(tmp_path):
    project = tmp_path / "project"
    path = init_workspace(project)

    assert path.exists()
    with pytest.raises(PackageError):
        init_workspace(project)


def test_prepare_writes_per_frame_parquet_and_manifest(tmp_path):
    project = _prepared_project(tmp_path)

    manifest = json.loads((project / ".mddn_cache" / "mddatanet.json").read_text())
    assert manifest["format"] == "mddatanet_hf_workspace"
    assert manifest["total_frames"] == 4
    assert manifest["num_atoms_selected"] == 4
    assert manifest["has_forces"] is False
    shard = sorted((project / ".mddn_cache" / "data").glob("shard-*.parquet"))[0]
    table = pq.read_table(shard)
    assert table.column_names == [
        "frame_id",
        "time_ps",
        "coordinates",
        "forces",
        "rmsd",
        "radius_of_gyration",
        "event_label",
        "event_confidence",
    ]
    assert np.asarray(table.to_pylist()[0]["coordinates"]).shape == (4, 3)


def test_prepare_strips_solvent_by_default_and_atom_selection_filters(tmp_path):
    project = _prepared_project(tmp_path, keep_solvent=False)
    manifest = json.loads((project / ".mddn_cache" / "mddatanet.json").read_text())
    assert manifest["num_atoms_selected"] == 4

    pdb = write_ligand_unbinding_pdb(tmp_path / "selected.pdb")
    selected = tmp_path / "selected_project"
    init_workspace(selected)
    prepare_workspace(project_root=selected, topology=pdb, atom_selection="name CA", overwrite=True)
    selected_manifest = json.loads((selected / ".mddn_cache" / "mddatanet.json").read_text())
    assert selected_manifest["num_atoms_selected"] == 1


def test_analyze_ligand_unbinding_updates_metrics_and_events(tmp_path):
    project = _prepared_project(tmp_path)

    analyze_workspace(
        project_root=project,
        preset="ligand_unbinding",
        ligand="resname LIG",
        pocket="protein",
        param_overrides={"distance_threshold": 5.0},
    )

    manifest = json.loads((project / ".mddn_cache" / "mddatanet.json").read_text())
    assert manifest["analysis"]["primary_metric"] == "ligand_pocket_min_distance"
    labels = []
    for path in sorted((project / ".mddn_cache" / "data").glob("*.parquet")):
        labels.extend(row["event_label"] for row in pq.read_table(path).to_pylist())
    assert labels == ["", "", "ligand_unbinding", "ligand_unbinding"]


def test_analyze_custom_script_validates_one_scalar_per_frame(tmp_path):
    project = _prepared_project(tmp_path)
    script = tmp_path / "metric.py"
    script.write_text(
        "def my_metric(positions, metadata):\n"
        "    return positions[:, :, 0].max(axis=1)\n",
        encoding="utf-8",
    )

    analyze_workspace(project_root=project, custom_script=script, func="my_metric")

    manifest = json.loads((project / ".mddn_cache" / "mddatanet.json").read_text())
    assert manifest["analysis"]["primary_metric"] == "metric"


def test_tag_validates_allowed_events_and_package_writes_splits(tmp_path):
    project = _prepared_project(tmp_path)

    tag_workspace(project_root=project, event="ligand_unbinding", start_frame=1, end_frame=3)
    package_workspace(project_root=project, hf_repo_link="mddatanet/tiny")

    assert (project / ".mddn_cache" / "data" / "train-00000-of-00001.parquet").exists()
    assert (project / ".mddn_cache" / "metadata_index" / "index-00000-of-00001.parquet").exists()
    assert (project / ".mddn_cache" / "dataset_card.md").exists()
    assert validate_workspace(project) == []
