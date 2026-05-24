from typer.testing import CliRunner

from mddatanet.cli import app
from mddatanet.format.validation import validate_package

from tests.helpers import write_tiny_multimodel_pdb


def test_cli_convert_featurize_label_split_validate_pipeline(tmp_path):
    runner = CliRunner()
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    raw = tmp_path / "raw.mddatanet"
    features_pkg = tmp_path / "features.mddatanet"
    labeled = tmp_path / "labeled.mddatanet"
    ready = tmp_path / "ready.mddatanet"
    features = tmp_path / "features.yaml"
    events = tmp_path / "events.yaml"
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
    events.write_text(
        """
events:
  - name: far
    type: feature_threshold
    feature: n_ca_distance
    operator: greater_than
    threshold: 1.5
    horizon_frames: 1
""",
        encoding="utf-8",
    )

    assert runner.invoke(app, ["convert", "--topology", str(pdb), "--name", "tiny", "--out", str(raw)]).exit_code == 0
    assert runner.invoke(app, ["featurize", "--input", str(raw), "--features", str(features), "--out", str(features_pkg)]).exit_code == 0
    assert runner.invoke(app, ["label", "--input", str(features_pkg), "--events", str(events), "--out", str(labeled)]).exit_code == 0
    assert runner.invoke(app, ["split", "--input", str(labeled), "--out", str(ready)]).exit_code == 0
    assert runner.invoke(app, ["validate", str(ready)]).exit_code == 0
    assert runner.invoke(app, ["inspect", str(ready), "--labels"]).exit_code == 0
    assert validate_package(ready).ok

