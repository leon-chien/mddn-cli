# Preset Guide

Presets are built-in operational task definitions for `mddatanet analyze`.

```bash
mddatanet presets list
mddatanet presets show ligand_unbinding
mddatanet presets explain ligand_unbinding
```

## Implemented HF MVP Presets

### `ligand_unbinding`

Required selections:

- `--ligand`
- `--pocket`

Default concept:

```text
ligand_pocket_min_distance > distance_threshold
```

Useful overrides:

- `--param distance_threshold=15.0`
- `--param horizon_frames=500`

### `ligand_binding`

Required selections:

- `--ligand`
- `--pocket`

Default concept:

```text
ligand_pocket_min_distance < distance_threshold
```

### `protein_unfolding`

The current HF MVP uses radius of gyration as the primary metric. Reference-based
RMSD unfolding is planned for a later metric expansion.

## Limitations

Presets are standardized operational labels for ML tasks. They are not universal
scientific definitions. The metric value, threshold, horizon, and source
trajectory context must travel with the dataset.
