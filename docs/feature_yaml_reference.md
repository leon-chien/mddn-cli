# Feature YAML Reference

Feature YAML files define arrays computed from trajectories.

```yaml
features:
  - name: ligand_pocket_min_distance
    type: min_distance
    selection_a: "resname LIG"
    selection_b: "protein"
    units: angstrom
```

Feature names must be unique and path-safe.

## Selection Syntax

Selections use MDAnalysis atom selection syntax. Examples:

- `protein`
- `resname LIG`
- `name CA`
- `resid 10 and name CA`
- `protein and backbone`

If a selection matches zero atoms, MDDataNet raises a selection error with the
failing selection.

## Supported Feature Types

### `distance`

Distance between two selections.

```yaml
features:
  - name: ligand_center_distance
    type: distance
    selection_a: "resname LIG"
    selection_b: "protein"
    mode: center_of_geometry
    units: angstrom
```

Modes: `single_atom`, `center_of_geometry`, `center_of_mass`.

### `min_distance`

Minimum pairwise distance between two selections.

```yaml
features:
  - name: ligand_pocket_min_distance
    type: min_distance
    selection_a: "resname LIG"
    selection_b: "protein"
    units: angstrom
```

### `contact`

Boolean feature for whether two selections are within a threshold.

```yaml
features:
  - name: ligand_contact
    type: contact
    selection_a: "resname LIG"
    selection_b: "protein"
    threshold_angstrom: 4.5
```

### `contact_count`

Count atom pairs within a threshold.

```yaml
features:
  - name: ligand_contact_count
    type: contact_count
    selection_a: "resname LIG"
    selection_b: "protein"
    threshold_angstrom: 4.5
```

### `dihedral`

Dihedral angle from four one-atom selections.

```yaml
features:
  - name: phi
    type: dihedral
    atoms:
      - "resid 1 and name C"
      - "resid 2 and name N"
      - "resid 2 and name CA"
      - "resid 2 and name C"
    units: degrees
```

### `rmsd`

RMSD to a reference structure.

```yaml
features:
  - name: rmsd_to_native
    type: rmsd
    selection: "protein and backbone"
    reference: native.pdb
    units: angstrom
```

### `radius_of_gyration`

Radius of gyration for one selection.

```yaml
features:
  - name: protein_rgyr
    type: radius_of_gyration
    selection: "protein"
    units: angstrom
```

### `native_contact_fraction`

Fraction of reference native contacts retained.

```yaml
features:
  - name: native_contact_fraction
    type: native_contact_fraction
    selection: "protein and name CA"
    reference: native.pdb
    threshold_angstrom: 8.0
```

## Large Trajectories

MDDataNet computes features frame-by-frame or chunk-by-chunk. Raw trajectories
are not loaded fully into memory by default.
