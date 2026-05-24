from mddatanet.presets.resolver import resolve_preset


def test_preset_parameter_substitution():
    resolved = resolve_preset(
        {
            "name": "ligand_unbinding",
            "required_args": ["ligand", "pocket"],
            "default_params": {"distance_threshold": 15.0, "horizon_frames": 500},
            "features": [
                {
                    "name": "ligand_pocket_min_distance",
                    "type": "min_distance",
                    "selection_a": "{ligand}",
                    "selection_b": "{pocket}",
                }
            ],
            "event": {
                "name": "ligand_unbinding",
                "type": "feature_threshold",
                "feature": "ligand_pocket_min_distance",
                "operator": "greater_than",
                "threshold": "{distance_threshold}",
                "horizon_frames": "{horizon_frames}",
            },
        },
        args={"ligand": "resname LIG", "pocket": "protein"},
        param_overrides={"distance_threshold": 12.0},
    )

    assert resolved.feature_config["features"][0]["selection_a"] == "resname LIG"
    assert resolved.event_config["events"][0]["threshold"] == 12.0

