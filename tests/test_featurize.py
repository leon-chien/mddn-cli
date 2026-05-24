import zarr

from mddatanet.convert import convert_package
from mddatanet.features.compute import featurize_package

from tests.helpers import write_tiny_multimodel_pdb


def test_featurize_computes_first_pass_feature_types(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    raw = tmp_path / "raw.mddatanet"
    features = tmp_path / "features.yaml"
    features.write_text(
        """
features:
  - name: n_ca_distance
    type: distance
    selection_a: "name N"
    selection_b: "name CA"
    mode: single_atom
  - name: n_c_min_distance
    type: min_distance
    selection_a: "name N"
    selection_b: "name C"
  - name: n_ca_contact
    type: contact
    selection_a: "name N"
    selection_b: "name CA"
    threshold_angstrom: 1.5
  - name: n_many_contact_count
    type: contact_count
    selection_a: "name N"
    selection_b: "name CA C"
    threshold_angstrom: 2.1
  - name: backbone_dihedral
    type: dihedral
    atoms:
      - "name N"
      - "name CA"
      - "name C"
      - "name O"
  - name: all_rmsd
    type: rmsd
    selection: "all"
    reference: "tiny.pdb"
  - name: all_rgyr
    type: radius_of_gyration
    selection: "all"
  - name: native_fraction
    type: native_contact_fraction
    selection: "all"
    reference: "tiny.pdb"
    threshold_angstrom: 1.5
""",
        encoding="utf-8",
    )
    out = tmp_path / "features.mddatanet"
    convert_package(topology=pdb, trajectory=None, coordinates=None, name="tiny", out=raw, overwrite=True)

    featurize_package(input_path=raw, features_path=features, out=out, overwrite=True)

    root = zarr.open_group(str(out / "dataset.zarr"), mode="r")
    assert root["features"]["n_ca_distance"][:].tolist() == [1.0, 2.0]
    assert root["features"]["n_ca_contact"][:].tolist() == [True, False]
    assert root["features"]["all_rmsd"].shape == (2,)
    assert root["features"]["native_fraction"].shape == (2,)

