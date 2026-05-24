import zarr

from mddatanet.convert import convert_package
from mddatanet.features.compute import featurize_package

from tests.helpers import write_tiny_multimodel_pdb


def test_featurize_falls_back_to_stored_positions_when_trajectory_missing(tmp_path):
    topology = write_tiny_multimodel_pdb(tmp_path / "topology.pdb")
    run_a = write_tiny_multimodel_pdb(tmp_path / "run_a.pdb")
    raw = tmp_path / "raw.mddatanet"
    featured = tmp_path / "featured.mddatanet"
    features = tmp_path / "features.yaml"
    features.write_text(
        """
features:
  - name: n_ca_distance
    type: distance
    selection_a: "name N"
    selection_b: "name CA"
    mode: single_atom
""",
        encoding="utf-8",
    )
    convert_package(
        topology=topology,
        trajectory=[run_a],
        coordinates=None,
        name="stored",
        out=raw,
        run_id=["stored_run"],
        store_positions=True,
        overwrite=True,
    )
    run_a.unlink()

    featurize_package(input_path=raw, features_path=features, out=featured, overwrite=True)

    root = zarr.open_group(str(featured / "dataset.zarr"), mode="r")
    assert root["features"]["n_ca_distance"][:].tolist() == [1.0, 2.0]
