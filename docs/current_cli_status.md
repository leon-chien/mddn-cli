# Current CLI Status

This document records the current stopping point for MDDataNet CLI development.
The local CLI is now a usable prototype for trajectory-first molecular dynamics
dataset packaging and temporal ML labeling. Direct Hub upload/submit automation
is intentionally not implemented yet.

## What The CLI Does Today

MDDataNet converts MDAnalysis-readable molecular dynamics files into
standardized `.mddatanet/` directories or `.mddatanet.zip` archives. A package
stores trajectory data, topology metadata, derived features, temporal labels,
splits, provenance, checksums, metrics, and a dataset card.

The default package is trajectory-first:

```text
dataset.zarr/
  trajectory/
    positions
    box_vectors
    frame_indices
    source_frame_indices
    frame_times
    trajectory_ids
    run_ids
  topology/
    atom_names
    atom_types
    residue_names
    residue_ids
    chain_ids
    masses
    charges
    bonds
  features/
  labels/
  splits/
  index/
```

By default, coordinates are stored as chunked compressed Zarr arrays using
`hybrid + compressed` storage. Huge datasets can use linked coordinate metadata
or `split-package` to separate labels/metadata from coordinates.

## Supported Commands

Current user-facing commands:

- `mddatanet convert`: create a trajectory-first package from raw MD files.
- `mddatanet analyze`: run a built-in or user YAML preset in one step.
- `mddatanet featurize`: compute custom feature YAML arrays.
- `mddatanet label`: generate event labels from events YAML or presets.
- `mddatanet split`: create train/validation/test splits.
- `mddatanet validate`: verify schemas, arrays, labels, splits, checksums, and package integrity.
- `mddatanet inspect`: print a readable package summary.
- `mddatanet pack` / `mddatanet unpack`: archive and unpack packages.
- `mddatanet split-package`: split a coordinate-heavy package into labels and coordinate archives.
- `mddatanet card`: refresh `dataset_card.md`.
- `mddatanet export-manifest`: export Hub-ready metadata files.
- `mddatanet export-schema`: export JSON schemas for future Hub CI.
- `mddatanet demo`: run a generated ligand-unbinding demo.
- `mddatanet presets list/show/explain/validate-yaml`: inspect and validate presets.

## Data The CLI Can Ingest

The converter supports MDAnalysis-readable workflows, including generated test
coverage for:

- PDB trajectories
- PDB + XTC
- PDB coordinates + DCD
- repeated trajectory files as multi-run packages
- PBC-aware distance/contact feature behavior when unit-cell information exists

Other MDAnalysis-supported formats such as PSF, PRMTOP, GRO, TRR, and NC are
part of the intended interface, but broader real-world fixture validation should
continue before calling those paths production-hardened.

## Feature And Label Support

Supported feature types include:

- `distance`
- `center_of_geometry_distance`
- `min_distance`
- `contact`
- `contact_count`
- `dihedral`
- `rmsd`
- `radius_of_gyration`
- `native_contact_fraction`

Supported event types include:

- `feature_threshold`
- `feature_window`
- `feature_bool`
- `composite`

Labels are frame-level temporal labels:

- `event_now`
- `event_future_{H}`
- `event_future_{H}_valid`
- `time_to_event`

Future labels are fixed-horizon and run-aware. Invalid trajectory-tail frames
are masked with `event_future_{H}_valid` instead of being treated as false
training labels.

## Built-In Presets

The CLI includes built-in operational presets such as:

- `ligand_binding`
- `ligand_unbinding`
- `dimerization`
- `dissociation`
- `salt_bridge_formation`
- `salt_bridge_breaking`
- `hydrogen_bond_formation`
- `hydrogen_bond_breaking`
- `protein_unfolding`
- `native_contact_loss`
- `dihedral_transition`
- `domain_opening`
- `loop_opening`

These presets define reproducible rule-based labels. They are task definitions,
not universal biological truth.

## Python Loader

The package now exposes a minimal framework-agnostic loader:

```python
from mddatanet import MDDataNetDataset

dataset = MDDataNetDataset(
    "outputs/ligand_unbinding_demo.mddatanet.zip",
    window_length=2,
    target="ligand_unbinding_future_2",
)

item = dataset[0]
print(item["coordinates"].shape)
print(item["label"], item["valid"])
dataset.close()
```

Each item is a NumPy/Python dictionary containing coordinates, label, valid
mask, frame indices, source frame indices, trajectory IDs, run IDs, target name,
and metadata. The loader skips invalid future-label samples by default and does
not require PyTorch.

## How To Test The CLI Now

Install in a local environment:

```bash
python -m pip install -e ".[dev]"
```

Run the main smoke test:

```bash
mddatanet demo
mddatanet inspect outputs/ligand_unbinding_demo.mddatanet.zip --features --labels --splits
mddatanet validate outputs/ligand_unbinding_demo.mddatanet.zip
```

Run the Python loader smoke test:

```bash
python -c 'from mddatanet import MDDataNetDataset; ds=MDDataNetDataset("outputs/ligand_unbinding_demo.mddatanet.zip", window_length=2, target="ligand_unbinding_future_2"); item=ds[0]; print(item["coordinates"].shape); print(bool(item["label"]), bool(item["valid"])); ds.close()'
```

Run development checks:

```bash
python -m pytest
python -m ruff check src tests
python -m build
```

## What Is Intentionally Not Done Yet

The CLI does not yet:

- upload packages to a Hub;
- submit pull requests to a Hub registry;
- download packages from a Hub;
- provide a full PyTorch/JAX training dataset adapter;
- define official benchmark leaderboards;
- ship large real MD fixture datasets;
- guarantee production-hardening across every MDAnalysis-supported format.

The next major product phase should be the separate `mddatanet-hub` metadata
registry and official benchmark task definitions.

## Current Positioning

MDDataNet is not just a simulation archive format. It is a trajectory-learning
dataset format for molecular dynamics:

```text
past molecular trajectory window -> future molecular event target
```

The CLI currently provides the local tooling needed to create, label, validate,
inspect, split, and load these packages for early ML experimentation.
