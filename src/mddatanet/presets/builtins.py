"""Built-in preset definitions.

These are product resources, not user-facing config templates.
"""

from __future__ import annotations

BUILTIN_PRESETS: list[dict] = [
    {
        "name": "ligand_unbinding",
        "category": "Ligand",
        "description": "Detect ligand unbinding using ligand-pocket minimum distance.",
        "required_args": ["ligand", "pocket"],
        "default_params": {"distance_threshold": 15.0, "horizon_frames": 500},
        "features": [
            {
                "name": "ligand_pocket_min_distance",
                "type": "min_distance",
                "selection_a": "{ligand}",
                "selection_b": "{pocket}",
                "units": "angstrom",
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
    {
        "name": "ligand_binding",
        "category": "Ligand",
        "description": "Detect ligand binding using ligand-pocket minimum distance.",
        "required_args": ["ligand", "pocket"],
        "default_params": {"distance_threshold": 4.5, "horizon_frames": 500},
        "features": [
            {
                "name": "ligand_pocket_min_distance",
                "type": "min_distance",
                "selection_a": "{ligand}",
                "selection_b": "{pocket}",
                "units": "angstrom",
            }
        ],
        "event": {
            "name": "ligand_binding",
            "type": "feature_threshold",
            "feature": "ligand_pocket_min_distance",
            "operator": "less_than",
            "threshold": "{distance_threshold}",
            "horizon_frames": "{horizon_frames}",
        },
    },
    {
        "name": "salt_bridge_breaking",
        "category": "Interactions",
        "description": "Detect salt bridge breaking with a distance threshold.",
        "required_args": ["selection_a", "selection_b"],
        "default_params": {"distance_threshold": 5.0, "horizon_frames": 500},
        "features": [
            {
                "name": "salt_bridge_distance",
                "type": "distance",
                "selection_a": "{selection_a}",
                "selection_b": "{selection_b}",
                "mode": "center_of_geometry",
                "units": "angstrom",
            }
        ],
        "event": {
            "name": "salt_bridge_breaking",
            "type": "feature_threshold",
            "feature": "salt_bridge_distance",
            "operator": "greater_than",
            "threshold": "{distance_threshold}",
            "horizon_frames": "{horizon_frames}",
        },
    },
    {
        "name": "salt_bridge_formation",
        "category": "Interactions",
        "description": "Detect salt bridge formation with a distance threshold.",
        "required_args": ["selection_a", "selection_b"],
        "default_params": {"distance_threshold": 4.0, "horizon_frames": 500},
        "features": [
            {
                "name": "salt_bridge_distance",
                "type": "distance",
                "selection_a": "{selection_a}",
                "selection_b": "{selection_b}",
                "mode": "center_of_geometry",
                "units": "angstrom",
            }
        ],
        "event": {
            "name": "salt_bridge_formation",
            "type": "feature_threshold",
            "feature": "salt_bridge_distance",
            "operator": "less_than",
            "threshold": "{distance_threshold}",
            "horizon_frames": "{horizon_frames}",
        },
    },
    {
        "name": "protein_unfolding",
        "category": "Protein",
        "description": "Operational unfolding label using RMSD, native contact fraction, and radius of gyration.",
        "required_args": ["reference"],
        "default_params": {
            "rmsd_threshold": 8.0,
            "native_contact_threshold": 0.4,
            "rgyr_threshold": 18.0,
            "native_contact_cutoff": 8.0,
            "horizon_frames": 500,
        },
        "features": [
            {
                "name": "rmsd_to_native",
                "type": "rmsd",
                "selection": "protein and backbone",
                "reference": "{reference}",
                "units": "angstrom",
            },
            {
                "name": "native_contact_fraction",
                "type": "native_contact_fraction",
                "selection": "protein and name CA",
                "reference": "{reference}",
                "threshold_angstrom": "{native_contact_cutoff}",
            },
            {
                "name": "protein_rgyr",
                "type": "radius_of_gyration",
                "selection": "protein",
                "units": "angstrom",
            },
        ],
        "event": {
            "name": "protein_unfolding",
            "type": "composite",
            "logic": "all",
            "horizon_frames": "{horizon_frames}",
            "conditions": [
                {"feature": "rmsd_to_native", "operator": "greater_than", "threshold": "{rmsd_threshold}"},
                {
                    "feature": "native_contact_fraction",
                    "operator": "less_than",
                    "threshold": "{native_contact_threshold}",
                },
                {"feature": "protein_rgyr", "operator": "greater_than", "threshold": "{rgyr_threshold}"},
            ],
        },
    },
    {
        "name": "hydrogen_bond_breaking",
        "category": "Interactions",
        "description": "Detect hydrogen bond breaking with a distance threshold.",
        "required_args": ["selection_a", "selection_b"],
        "default_params": {"distance_threshold": 3.5, "horizon_frames": 500},
        "features": [
            {
                "name": "hbond_distance",
                "type": "min_distance",
                "selection_a": "{selection_a}",
                "selection_b": "{selection_b}",
                "units": "angstrom",
            }
        ],
        "event": {
            "name": "hydrogen_bond_breaking",
            "type": "feature_threshold",
            "feature": "hbond_distance",
            "operator": "greater_than",
            "threshold": "{distance_threshold}",
            "horizon_frames": "{horizon_frames}",
        },
    },
    {
        "name": "hydrogen_bond_formation",
        "category": "Interactions",
        "description": "Detect hydrogen bond formation with a distance threshold.",
        "required_args": ["selection_a", "selection_b"],
        "default_params": {"distance_threshold": 3.0, "horizon_frames": 500},
        "features": [
            {
                "name": "hbond_distance",
                "type": "min_distance",
                "selection_a": "{selection_a}",
                "selection_b": "{selection_b}",
                "units": "angstrom",
            }
        ],
        "event": {
            "name": "hydrogen_bond_formation",
            "type": "feature_threshold",
            "feature": "hbond_distance",
            "operator": "less_than",
            "threshold": "{distance_threshold}",
            "horizon_frames": "{horizon_frames}",
        },
    },
    {
        "name": "dihedral_transition",
        "category": "Conformation",
        "description": "Detect transition of a dihedral angle past a threshold.",
        "required_args": ["atoms"],
        "default_params": {"angle_threshold": 0.0, "horizon_frames": 500},
        "features": [
            {
                "name": "target_dihedral",
                "type": "dihedral",
                "atoms": "{atoms}",
                "units": "degrees",
            }
        ],
        "event": {
            "name": "dihedral_transition",
            "type": "feature_threshold",
            "feature": "target_dihedral",
            "operator": "greater_than",
            "threshold": "{angle_threshold}",
            "horizon_frames": "{horizon_frames}",
        },
    },
    {
        "name": "domain_opening",
        "category": "Protein",
        "description": "Detect domain opening using center-of-geometry distance.",
        "required_args": ["selection_a", "selection_b"],
        "default_params": {"distance_threshold": 25.0, "horizon_frames": 500},
        "features": [
            {
                "name": "domain_distance",
                "type": "distance",
                "selection_a": "{selection_a}",
                "selection_b": "{selection_b}",
                "mode": "center_of_geometry",
                "units": "angstrom",
            }
        ],
        "event": {
            "name": "domain_opening",
            "type": "feature_threshold",
            "feature": "domain_distance",
            "operator": "greater_than",
            "threshold": "{distance_threshold}",
            "horizon_frames": "{horizon_frames}",
        },
    },
    {
        "name": "loop_opening",
        "category": "Protein",
        "description": "Detect loop opening using center-of-geometry distance to a reference point.",
        "required_args": ["selection_a", "selection_b"],
        "default_params": {"distance_threshold": 10.0, "horizon_frames": 500},
        "features": [
            {
                "name": "loop_distance",
                "type": "distance",
                "selection_a": "{selection_a}",
                "selection_b": "{selection_b}",
                "mode": "center_of_geometry",
                "units": "angstrom",
            }
        ],
        "event": {
            "name": "loop_opening",
            "type": "feature_threshold",
            "feature": "loop_distance",
            "operator": "greater_than",
            "threshold": "{distance_threshold}",
            "horizon_frames": "{horizon_frames}",
        },
    },
]

