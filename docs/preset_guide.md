# Preset Guide

Presets generate feature and event definitions from standard operational rules.
They are product behavior, not user config templates.

List presets:

```bash
mddatanet presets list
```

Show one preset:

```bash
mddatanet presets show ligand_unbinding
```

Explain one preset:

```bash
mddatanet presets explain ligand_unbinding
```

## Ligand Presets

### `ligand_unbinding`

Required:

- `--ligand`
- `--pocket`

Default rule:

```text
ligand_pocket_min_distance > 15.0 angstrom
```

Overrides:

- `--param distance_threshold=15.0`
- `--param horizon_frames=500`

### `ligand_binding`

Required:

- `--ligand`
- `--pocket`

Default rule:

```text
ligand_pocket_min_distance < 4.5 angstrom
```

## Interaction Presets

- `salt_bridge_breaking`
- `salt_bridge_formation`
- `hydrogen_bond_breaking`
- `hydrogen_bond_formation`

These currently use distance-based operational rules. Hydrogen bond angle
criteria are a future scientific refinement.

## Protein And Conformation Presets

- `protein_unfolding`
- `dihedral_transition`
- `domain_opening`
- `loop_opening`

Reference-dependent presets require `--reference` when the computed features
need a native/reference structure.

## Limitations

Preset labels are standardized task labels. They are useful for reproducible ML
benchmarks, but they are not universal scientific definitions.
