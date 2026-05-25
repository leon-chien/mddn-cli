# MDDataNet Agent Guide

This repository is the source for **MDDataNet**, a Python CLI and library named
`mddatanet`.

Treat `docs/MDDataNet_CLI_Full_Build_Specification.md` as the canonical product
specification for package format, command behavior, schemas, and scientific
intent. Keep this `AGENTS.md` updated when major architecture or roadmap choices
change.

## Product Idea

MDDataNet converts raw molecular dynamics simulation data into standardized,
labeled, machine-learning-ready dataset packages.

The CLI reads MDAnalysis-readable topology and trajectory files, extracts
trajectory-derived features, applies reproducible event definitions, generates
current-event and future-event labels, creates train/validation/test splits,
tracks provenance, validates package integrity, and writes shareable
`.mddatanet.zip` archives.

The core scientific principle is that labels must be reproducible operational
rules, not vague manual tags. For example, `ligand_unbinding` is a human-facing
event family, but the actual label is a measurable rule such as:

```yaml
event:
  name: ligand_unbinding
  definition:
    feature: ligand_pocket_min_distance
    operator: greater_than
    threshold_angstrom: 15.0
    horizon_frames: 500
```

The intended ML task shape is:

```text
trajectory window -> future event label
```

MDDataNet should become an ImageNet/ProteinNet-style standard for labeled MD
datasets: common package format, reproducible labels, official splits, dataset
cards, checksums, provenance, and a future public discovery/download registry.

## Core Conceptual Analogy

MDDataNet should conceptually resemble trajectory-learning ecosystems such as:

- Waymo Open Dataset
- nuScenes
- Ego4D
- Kinetics

but for molecular dynamics trajectories.

The core dataset object is not a feature table and not merely a stored
simulation trajectory. The core dataset object is:

```text
trajectory window -> temporal ML task
```

MDDataNet packages should behave more like temporal trajectory-learning datasets
than traditional simulation archives.

Analogy:

```text
Waymo:
past object trajectories -> predict future object motion

MDDataNet:
past molecular trajectories -> predict future molecular events
```

Examples:

- ligand-pocket trajectory -> ligand unbinding within next 500 frames
- protein interface trajectory -> dimerization within next 1000 frames
- residue contact trajectory -> salt bridge breaking
- protein conformational trajectory -> unfolding or native contact loss

MDRepo and similar projects focus primarily on simulation storage, retrieval,
and FAIR archival. MDDataNet focuses on standardizing how ML models learn from
trajectories.

The key differentiator is:

```text
standardized trajectories + temporal labels + future-event prediction targets
+ benchmark semantics + reproducible operational definitions
+ canonical package format + benchmark split policies
```

The intended outcome is an ML-ready benchmark ecosystem for molecular dynamics
trajectory learning.

## Repository Separation

Keep the separation intentional:

- `mddatanet`: this repo. CLI, Python library, package format, schemas,
  validation, local processing, and Hub metadata export.
- `mddatanet-hub`: future curated metadata registry of approved datasets.
  It should store small metadata files, not huge trajectory packages.
- `mddatanet-site`: optional future search UI and documentation site.

The Hub should use a pull-request model first:

1. User runs `mddatanet validate my_dataset.mddatanet.zip`.
2. User runs `mddatanet export-manifest my_dataset.mddatanet.zip`.
3. User uploads the large package to Hugging Face Datasets, Zenodo, S3/R2,
   Google Cloud, or institutional storage.
4. User opens a PR to `mddatanet-hub` with metadata, dataset card, checksum,
   download link, license, citation, and optional baseline stats.
5. Hub CI validates schema, URL/checksum, and dataset card.
6. Maintainer reviews and merges.

Do not implement upload targets, GitHub PR automation, or Hub website code in
this repo until the local package format and manifest workflow are stable.

## Current Implementation State

The current CLI supports:

- `mddatanet convert`
- `mddatanet featurize`
- `mddatanet label`
- `mddatanet analyze`
- `mddatanet split`
- `mddatanet validate`
- `mddatanet inspect`
- `mddatanet pack`
- `mddatanet unpack`
- `mddatanet split-package`
- `mddatanet card`
- `mddatanet export-manifest`
- `mddatanet export-schema`
- `mddatanet demo`
- `mddatanet presets list/show/explain/validate-yaml`

The current pipeline can:

- convert MDAnalysis-readable raw data into `.mddatanet/` or `.mddatanet.zip`
  packages;
- ingest repeated `--trajectory` inputs as multi-run packages;
- store per-frame `run_ids`, `trajectory_ids`, and `source_frame_indices`;
- store standardized trajectory/topology data by default under
  `dataset.zarr/trajectory/*` and `dataset.zarr/topology/*`;
- write compressed chunked coordinates by default using `hybrid + compressed`
  storage;
- create linked-coordinate packages for huge datasets using external coordinate
  URLs and checksums;
- compute first-pass features such as distance, min distance, contact,
  contact count, dihedral, RMSD, radius of gyration, native contact fraction,
  and center-of-geometry distance;
- apply custom event YAML, built-in presets, or user preset YAML;
- run high-level preset analyses through `mddatanet analyze`;
- generate `event_now`, fixed-horizon `event_future_H`,
  `event_future_H_valid`, and per-run `time_to_event`;
- split temporally, randomly, or by trajectory/run IDs;
- validate package structure, schemas, array lengths, splits, run records, and
  checksums;
- inspect package summaries, per-run details, and descriptive label metrics;
- split coordinate-heavy packages into a lightweight labels package plus a
  coordinate archive for Hub-scale sharing;
- run a runtime-generated ligand unbinding demo without committed demo data;
- export Hub-schema registry metadata files for
  `mddn-hub/datasets/<dataset_name>/`, including named download/checksum
  assets, task metadata, metrics files, and optional `citation.bib`.

## Current Package Format

An unpacked package should be shaped like:

```text
dataset.mddatanet/
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
  metadata.json
  provenance.json
  feature_config.yaml
  events.yaml
  presets_used.json
  user_presets/
  splits.json
  checksums.json
  label_statistics.json
  baseline_metrics.json
  dataset_card.md
  README.md
  LICENSE
```

Not every file exists at every stage. A raw converted package may not yet have
features, labels, events, or splits.

Important Zarr arrays include:

- `trajectory/frame_indices`
- `trajectory/source_frame_indices`
- `trajectory/frame_times`
- `trajectory/trajectory_ids`
- `trajectory/run_ids`
- `trajectory/positions`, included by default unless `features-only`,
  `--no-coordinates`, or `linked` storage is used
- `trajectory/box_vectors`
- `topology/atom_names`
- `topology/atom_types`
- `topology/residue_ids`
- `topology/residue_names`
- `topology/chain_ids`
- `topology/masses`
- `topology/charges`
- `topology/bonds`
- `features/{feature_name}`
- `labels/{event_name}/event_now`
- `labels/{event_name}/event_future_{horizon}`
- `labels/{event_name}/event_future_{horizon}_valid`
- `labels/{event_name}/time_to_event`
- `splits/train`
- `splits/val`
- `splits/test`
- `index/feature_names`
- `index/event_names`

The older `dataset.zarr/arrays/*` layout is legacy read compatibility only.
Do not write new packages in that layout.

## Trajectory-First Storage Rules

The conceptual rule is:

```text
MDDataNet package = standardized MD trajectory + topology + temporal labels
                    + metadata + provenance + splits + optional features
```

Features are useful derived analyses, but they are not the core dataset. The
core dataset should look more like a video ML dataset: coordinates over time
plus frame-level and future-window labels.

The trajectory itself is the primary ML object. Features are useful derived
analyses and annotations, but they are not the canonical data representation.
MDDataNet should support models that train directly on:

```text
coordinates over time + topology + temporal labels
```

similar to how autonomous-driving datasets support models that learn directly
from temporal sensor trajectories.

The package should therefore always preserve:

- frame ordering
- run identity
- trajectory identity
- source frame identity
- temporal continuity

unless explicitly removed by the user.

`mddatanet convert` defaults:

- `--data-mode hybrid`
- `--storage-profile compressed`
- `--coordinate-dtype float32`
- `--compression zstd`
- `--chunk-frames 100`
- `--chunk-atoms 1000`
- coordinates included by default

Storage profiles:

- `compressed`: default. Embedded chunked compressed Zarr coordinates.
- `full`: embedded chunked coordinates using the user-requested precision; no
  downsampling or quantization unless explicitly requested.
- `linked`: no embedded `trajectory/positions`; package must include
  `download.yaml` with coordinate URL/checksum metadata.

Linked packages and `split-package` exist so Hub-scale datasets can keep large
coordinates in Hugging Face Datasets, Zenodo, S3/R2, GCS, or institutional
storage while GitHub/the Hub registry stores metadata only.

## Hub Registry Format

`mddatanet export-manifest` should produce a small Hub registry folder shaped
for `mddn-hub/datasets/<dataset_name>/`:

```text
dataset_id/
  metadata.json
  dataset_card.md
  checksums.json
  manifest.json
  download.yaml
  citation.bib
  baseline_metrics.json
  label_statistics.json
```

The Hub repo should not store huge `.mddatanet.zip` files. It should store
metadata, manifests, dataset cards, checksums, citations, optional baseline
metrics, and download instructions.

The exported `metadata.json` is Hub-schema metadata, not a direct copy of the
package's internal `metadata.json`. It must include machine-readable task
metadata (`task_type`, `target_event`, `horizon_frames`, and
`input_type: trajectory_window`), storage profile, coordinate storage,
statistics, splits, provenance, license, and extensions. `download.yaml` and
`checksums.json` use matching named assets such as `package`, `coordinates`,
and `topology`.

Structured tags should be multi-level and multi-label, for example:

```yaml
system:
  type: protein_ligand
  organism: human
  protein: EGFR
  ligand_present: true
simulation:
  engine: NAMD
  force_field: CHARMM36
  solvent: explicit
  ensemble: NPT
task:
  task_type: future_event_prediction
  event_family: ligand_unbinding
  horizon_frames: 500
  label_source: rule_based
  preset: ligand_unbinding
features:
  feature_types:
    - min_distance
    - contact_count
ml:
  split_strategy: temporal
  leakage_gap_frames: 100
license:
  data_license: CC-BY-4.0
```

## Benchmark Task Semantics

MDDataNet datasets should explicitly define ML task semantics.

Supported task categories include:

- future_event_prediction
- transition_detection
- state_classification
- trajectory_forecasting
- interaction_prediction

Examples:

- ligand_unbinding_future_500
- ligand_binding_future_500
- dimerization_future_1000
- dissociation_future_1000
- salt_bridge_breaking_future_200
- native_contact_loss_future_500
- protein_unfolding_future_1000

Datasets should expose machine-readable task metadata. Recommended metadata
structure:

```yaml
task:
  task_type: future_event_prediction
  target_event: ligand_unbinding
  horizon_frames: 500
  input_type: trajectory_window
```

The Hub should eventually index datasets primarily by ML task semantics rather
than only by molecular system.

## Architecture Rules

- Keep the CLI useful without MDDataNet Hub.
- Keep Hub upload/download commands out of scope until explicitly requested.
- Keep direct Hub upload, download, submit, PR automation, and Hub website code
  out of scope unless explicitly requested.
- Keep command functions thin; put real behavior in service modules.
- Prefer Typer for CLI commands, Rich for terminal output, Pydantic for schemas,
  MDAnalysis for MD loading, Zarr for array storage, PyYAML for config parsing,
  and NumPy for numerical work.
- Keep modules small and testable.
- Preserve backward compatibility for CLI flags unless a change is unavoidable.
- Keep scientific labels framed as reproducible operational labels, not
  universal biological truths.
- Design future APIs around trajectory windows.
- The canonical ML training pattern should be:

```text
frames t-W:t -> predict event in t:t+H
```

Future loaders and APIs should naturally expose:

- window length
- prediction horizon
- valid masks
- trajectory IDs
- run IDs
- topology metadata

The long-term Python API target is:

```python
from mddatanet import MDDataNetDataset

dataset = MDDataNetDataset(
    "ligand_unbinding_v1.mddatanet.zip",
    window_length=64,
    target="ligand_unbinding_future_500",
)
```

Each item should eventually provide:

- trajectory coordinate window
- topology/atom metadata
- labels
- valid masks
- dataset/task metadata

## Large MD Data Rules

- Never assume trajectory data fits in RAM.
- Use streaming file operations for checksums, pack/unpack, and source
  inspection.
- Use chunked Zarr writes for large arrays.
- Prefer unpacked `.mddatanet/` directories during active processing of huge
  data; use `.mddatanet.zip` for sharing/export.
- Store coordinates by default, but always with chunking and compression.
- For huge datasets, prefer linked coordinates or `split-package` rather than
  putting massive coordinate blobs in the labels archive.
- Never add lossy coordinate quantization by default; only use it when the user
  explicitly passes coordinate precision.
- Validate package structure and array shapes without materializing full arrays.
- Generate labels in chunks where possible. Future-event and time-to-event
  labels may require reverse scans; do not load raw MD coordinates to do this.
- Keep distance/contact calculations blockwise for large selections.
- Multi-run packages require one shared topology and atom ordering unless a
  future design explicitly supports heterogeneous systems.
- Trajectory continuity is scientifically important.
- Do not randomly reorder frames internally unless explicitly requested by the
  user.
- All transformations must preserve traceability back to:
  - original trajectory file
  - original frame index
  - original run
- Traceability must be stored through:
  - `trajectory_ids`
  - `run_ids`
  - `source_frame_indices`
- This traceability is required for reproducibility and leakage-safe ML splits.

## Testing Rules

- Use synthetic tiny arrays and temporary packages in tests.
- Do not require large real MD files in CI.
- Add tests when changing package structure, schemas, conversion, feature math,
  label math, split logic, manifests, checksums, validation, pack/unpack, or CLI
  registration.
- Validation changes should include both passing and failing cases.
- Keep `mddatanet demo` runtime-generated; do not commit demo datasets.

## What Is Still Needed For A Fully Working Project

High-priority local CLI work (MOSTLY DONE):

- [x] Harden conversion across more real-world formats: PSF/PDB+DCD, PDB+XTC,
  GRO+XTC, PRMTOP/NC, TRR.
- [x] Add integration tests with tiny generated or minimal fixture files for those
  format pairs.
- [x] Improve stored-position featurization so supported feature types work from
  `trajectory/positions`, including PBC support via stored `box_vectors`.
- [x] Add more robust unit handling and document Angstrom/picosecond assumptions.
- [x] Improve periodic boundary handling for distances/contacts using MDAnalysis
  box information.
- [x] Add chunk-size CLI/config options for very large datasets.
- [x] Improve progress reporting for long trajectories.
- [x] Add better resume/retry behavior via atomic temporary workspace creation.

Feature and label work (MOSTLY DONE):

- [x] Expand built-in presets: protein unfolding, ligand binding, salt bridge
  formation/breaking, hydrogen bond formation/breaking, dihedral transition,
  domain opening, loop opening.
- [x] Store richer feature metadata and label statistics in machine-readable JSON (`label_statistics.json`).
- [x] Validate that future labels match fixed-horizon semantics with per-run
  valid masks.
- [x] Add window extraction utilities for downstream ML training (`mddatanet.utils.windows`).
- [x] Add descriptive baseline dataset metrics generation.

Hub-readiness work (NEXT PHASE):

- [x] Stabilize versioned `manifest.json` and `download.yaml` schemas.
- [x] Add JSON Schema exports for Hub CI (`export-schema`).
- [x] Add `citation.bib` and `baseline_metrics.json` support in manifest export.
- [x] Add opt-in URL size verification for external downloads.
- [x] Make `export-manifest` produce Hub-shaped registry entries that validate
  against the sibling `mddn-hub` schemas.
- [ ] Build `mddatanet-hub` as a separate metadata registry repository.

Documentation and packaging work:

- Expand README with a real installation section, quickstart, custom YAML
  examples, preset examples, package format docs, Hub registry workflow, and
  contribution guide.
- Add API docs for Python users.
- Add CI for tests, linting, and package build. (DONE for GitHub Actions)
- Add release workflow for PyPI once the API stabilizes. (TestPyPI manual
  workflow exists; PyPI remains intentionally manual)
- Add a changelog and semantic versioning policy.

Scientific/product work:

- Clarify that MDDataNet standardizes operational tasks and reproducible labels,
  not universal scientific truth.
- Define official benchmark split policies for common MD task families.
- Decide which dataset licenses are acceptable for Hub inclusion.
- Decide required metadata fields for curated Hub approval.
- Add responsible-use language to dataset cards.

Benchmark ecosystem work:

- Define official benchmark tasks for common MD trajectory-learning problems.
- Define leakage-safe canonical split policies for:
  - trajectory-level splits
  - run-level splits
  - temporal splits with gaps
  - future protein-family splits
  - future ligand-scaffold splits
- Define standard evaluation metrics for:
  - future-event prediction
  - transition detection
  - interaction prediction
  - trajectory forecasting
- Add baseline reference models and benchmark baselines later.
- Ensure all operational labels remain reproducible rule-based definitions
  rather than subjective annotations.

## Final Project Positioning

MDDataNet is not merely a repository for MD simulations.

MDDataNet is a standardized benchmark and dataset ecosystem for molecular
dynamics trajectory learning.

Its purpose is to convert heterogeneous molecular dynamics simulations into
reproducible, ML-ready temporal prediction tasks using standardized trajectory
storage, topology representation, operational event definitions, future-event
labels, benchmark splits, provenance tracking, and dataset cards.

The conceptual target is:

```text
Waymo Open Dataset for molecular dynamics trajectories
```

rather than a generic simulation archive.
