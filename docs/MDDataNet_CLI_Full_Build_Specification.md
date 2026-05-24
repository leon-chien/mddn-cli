# MDDataNet CLI Full Build Specification

## Project

- Project name: **MDDataNet**
- CLI command name: `mddatanet`
- Primary purpose: convert raw molecular dynamics simulation files into
  standardized, labeled, machine-learning-ready dataset packages.
- Final package suffix: `.mddatanet.zip`
- Future destination: MDDataNet Hub, a public FAIR database of labeled MD
  simulation datasets.

The CLI must be useful by itself before the Hub exists.

## Core Concept

The user provides raw MD files such as PDB, PSF, DCD, XTC, TRR, NC, PRMTOP, or
GRO. The CLI reads the simulation, extracts trajectory features, applies default
or custom event definitions, generates labels and future-event labels, creates
train/validation/test splits, validates the package, and writes a shareable
`.mddatanet.zip`.

The CLI must not require manual event tagging. Users choose a built-in event
preset or provide YAML rules. Labels are computed from measurable trajectory
features.

Example:

- Preset: `ligand_unbinding`
- Feature: `ligand_pocket_min_distance`
- `event_now[t] = ligand_pocket_min_distance[t] > threshold`
- `event_future_500[t] = event occurs at any frame from t through t + 500`
- `time_to_event[t] = frames until next event, or -1 if no future event exists`

## Main User Flows

Beginner preset flow:

```bash
mddatanet convert --topology system.pdb --trajectory traj.xtc --name my_run --out my_run.mddatanet.zip
mddatanet label --input my_run.mddatanet.zip --preset ligand_unbinding --ligand "resname LIG" --pocket "protein" --out labeled.mddatanet.zip
```

Advanced YAML flow:

```bash
mddatanet featurize --input my_run.mddatanet.zip --features features.yaml --out features.mddatanet.zip
mddatanet label --input features.mddatanet.zip --events events.yaml --out labeled.mddatanet.zip
```

Final flow:

```bash
mddatanet split --input labeled.mddatanet.zip --strategy temporal --gap 100 --out ready.mddatanet.zip
mddatanet validate ready.mddatanet.zip
mddatanet inspect ready.mddatanet.zip
```

## Technologies

Required:

- Python 3.10+
- Typer
- Rich
- Pydantic
- MDAnalysis
- NumPy
- Zarr
- Numcodecs
- PyYAML
- Pandas where useful
- Tqdm where useful

Optional later:

- MDTraj
- PyTorch
- H5py
- PyArrow/Parquet
- Scikit-learn utilities

## Source-First Repository Shape

This initial source phase must not create example datasets, config templates, or
preset YAML files. Use this structure:

```text
AGENTS.md
README.md
pyproject.toml
docs/
  MDDataNet_CLI_Full_Build_Specification.md
src/
  mddatanet/
    __init__.py
    cli.py
    io/
    format/
    features/
    labels/
    presets/
    splits/
    demo/
    utils/
tests/
```

## Package Layout

An unpacked package should look like:

```text
my_dataset.mddatanet/
  dataset.zarr/
    arrays/
    features/
    labels/
    splits/
    index/
  metadata.json
  provenance.json
  feature_config.yaml
  events.yaml
  presets_used.json
  splits.json
  checksums.json
  dataset_card.md
  README.md
  LICENSE
```

Only files relevant to the package stage need to exist. A raw converted package
may not yet contain features, labels, or splits.

## Large MD Data Requirements

- Never load full trajectories into memory by default.
- Scan metadata before writing arrays.
- Store positions only when requested, and write them chunk-by-chunk.
- Use Zarr chunks and compression from the beginning.
- Stream checksums in blocks.
- Pack/unpack with streaming filesystem operations.
- Validate metadata, shape, and group structure without reading full arrays.
- Compute features frame-by-frame or chunk-by-chunk.
- Generate future/time-to-event labels with chunked forward/reverse scans where
  possible.

## Commands

Required commands:

- `mddatanet convert`
- `mddatanet featurize`
- `mddatanet label`
- `mddatanet split`
- `mddatanet validate`
- `mddatanet inspect`
- `mddatanet pack`
- `mddatanet unpack`
- `mddatanet card`
- `mddatanet demo`
- `mddatanet presets list`
- `mddatanet presets show`
- `mddatanet presets explain`

Future Hub commands:

- `mddatanet upload`
- `mddatanet download`
- `mddatanet list`

Do not implement Hub commands in the first local CLI.

## Convert

Purpose: create an initial raw MDDataNet package from topology, coordinates, and
trajectory files.

Important behavior:

- Validate input paths.
- Load topology and trajectory with MDAnalysis.
- Count atoms, residues, frames, timestep, and periodic box availability.
- Create `dataset.zarr` root groups.
- Store frame indices and frame times.
- Store atom names, residue IDs, and residue names.
- Optionally store positions using chunked writes.
- Write `metadata.json`, `provenance.json`, `dataset_card.md`, and
  `checksums.json`.
- Pack output if the target ends with `.zip`.

## Featurize

Purpose: add trajectory-derived features to an existing package.

Supported first feature types:

- `distance`
- `min_distance`
- `contact`
- `contact_count`
- `dihedral`
- `rmsd`
- `radius_of_gyration`
- `native_contact_fraction`

Feature computation must be chunked and should reopen original source files if
positions were not stored in the package.

## Label

Purpose: generate event labels from features using custom YAML or built-in
presets.

Supported custom event types:

- `feature_threshold`
- `feature_window`
- `feature_bool`
- `composite`

For every event, write:

```text
dataset.zarr/labels/{event_name}/event_now
dataset.zarr/labels/{event_name}/event_future_{horizon}
dataset.zarr/labels/{event_name}/time_to_event
```

Definitions:

- `event_now[t]`: event is happening at frame `t`.
- `event_future_H[t]`: event happens at any frame from `t` through `t + H`.
- `time_to_event[t]`: frames until next event, or `-1`.

## Presets

Built-in presets to implement later:

- `protein_unfolding`
- `ligand_unbinding`
- `ligand_binding`
- `salt_bridge_breaking`
- `salt_bridge_formation`
- `hydrogen_bond_breaking`
- `hydrogen_bond_formation`
- `dihedral_transition`
- `native_contact_loss`
- `loop_opening`
- `domain_opening`

Preset resolver behavior:

- Load preset YAML.
- Check required args.
- Merge defaults with CLI `--param` overrides.
- Substitute placeholders.
- Generate feature and event configs.
- Compute missing features.
- Store resolved preset info in `presets_used.json`.

Preset YAML files are deferred in the source-first phase.

## Split

Strategies:

- `temporal`: natural frame order, recommended for one trajectory.
- `random_window`: randomized window sampling with leakage controls.
- `trajectory`: split by independent trajectory/run IDs.

Store:

```text
dataset.zarr/splits/train
dataset.zarr/splits/val
dataset.zarr/splits/test
splits.json
```

Validation must ensure split indices are in range and non-overlapping.

## Validate

Validation checks include:

- Package opens.
- `metadata.json` and `provenance.json` exist and match schemas.
- `dataset.zarr` exists and has required root groups.
- Frame arrays exist.
- Feature and label arrays match frame count.
- Events reference existing features.
- Future labels match horizon semantics where feasible.
- Splits are valid and non-overlapping.
- Optional YAML/JSON manifests are valid.
- Dataset card exists.
- Checksums match.

## Inspect

Inspect should print a human-readable package summary:

- Dataset name and description.
- System type, atoms, residues, frames, timestep.
- Feature names, dtypes, and shapes.
- Events, horizons, and positive rates.
- Splits.
- Files present.
- Validation status.

It should also support JSON output.

## Dataset Card

`dataset_card.md` should include:

- Title and summary.
- Source files.
- System information.
- Features.
- Events and label statistics.
- Split strategy.
- Known limitations.
- License.
- Citation.
- How to load.
- How to reproduce.

## Error Handling

Use clear custom errors:

- `MDDataNetError`
- `PackageError`
- `ValidationError`
- `SelectionError`
- `FeatureError`
- `LabelError`
- `PresetError`

Errors should name the failing object and suggest the next action where useful.

## Testing Requirements

Use synthetic data for most tests. Do not require large real MD files in CI.

Cover:

- CLI help.
- Package create/pack/unpack.
- Metadata and provenance schemas.
- Feature config validation.
- Event config validation.
- Preset loading and parameter substitution.
- Feature math.
- Event labeling.
- Future labels and time-to-event.
- Temporal splits and gaps.
- Validation failures.
- Inspect output.
- Demo command surface.

