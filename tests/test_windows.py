import pytest
from pathlib import Path
import numpy as np
from mddatanet.convert import convert_package
from mddatanet.features.compute import featurize_package
from mddatanet.labels.service import label_package
from mddatanet.utils.windows import iter_windows
from tests.helpers import write_tiny_multimodel_pdb

def test_iter_windows(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    out = tmp_path / "tiny.mddatanet"
    
    # Need at least 4 frames for windowing tests (helpers only has 2)
    pdb.write_text(
        """MODEL        1
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ENDMDL
MODEL        2
ATOM      1  N   ALA A   1       1.000   0.000   0.000  1.00  0.00           N
ENDMDL
MODEL        3
ATOM      1  N   ALA A   1       2.000   0.000   0.000  1.00  0.00           N
ENDMDL
MODEL        4
ATOM      1  N   ALA A   1       3.000   0.000   0.000  1.00  0.00           N
ENDMDL
END
""",
        encoding="utf-8",
    )
    
    convert_package(topology=pdb, trajectory=None, coordinates=None, name="tiny", out=out, overwrite=True)
    
    feature_config = {
        "features": [
            {
                "name": "x",
                "type": "distance",
                "selection_a": "index 0",
                "selection_b": "index 0", # Distance to self is 0, but whatever
                "mode": "single_atom"
            }
        ]
    }
    feat_out = tmp_path / "feat.mddatanet"
    featurize_package(input_path=out, out=feat_out, feature_config=feature_config, overwrite=True)
    
    event_config = {
        "events": [
            {
                "name": "my_event",
                "type": "feature_threshold",
                "feature": "x",
                "operator": "greater_than",
                "threshold": -1.0, # Always true
                "horizon_frames": 1
            }
        ]
    }
    # Write events.yaml for label_package
    import yaml
    (tmp_path / "events.yaml").write_text(yaml.dump(event_config))

    label_out = tmp_path / "label.mddatanet"
    label_package(input_path=feat_out, out=label_out, events_path=tmp_path / "events.yaml", overwrite=True)

    windows = list(iter_windows(label_out, window_size=2, label_name="my_event/event_now"))

    assert len(windows) == 3 # 4 frames, window 2 -> [0,1], [1,2], [2,3]
    assert windows[0]["features"].shape == (2, 1)
    assert "label" in windows[0]
