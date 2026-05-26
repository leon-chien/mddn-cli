# MDDataNet Agent Guide

This repository is the source for **MDDataNet**, a Python CLI and library named
`mddatanet`.

MDDataNet is now a Hugging Face-native trajectory-to-ML-dataset tool. Treat
`docs/MDDataNet_CLI_Full_Build_Specification.md` as the canonical product
specification and keep this file updated when architecture or roadmap choices
change.

## Product Idea

MDDataNet converts raw molecular dynamics simulation data into standardized,
searchable, streaming-ready Hugging Face dataset assets.

The current product direction intentionally removes the custom `.mddatanet.zip`
archive and custom `mddn-hub` registry workflow from the public CLI. The CLI now
prepares a local project workspace, writes per-frame Parquet tensors, creates a
lightweight `metadata_index` split, validates the local cache, and publishes the
result directly to Hugging Face Datasets.

The core scientific principle is still that event labels must be reproducible
operational rules or explicitly declared interval annotations, not vague manual
tags.

The intended ML task shape is:

```text
trajectory frame or window -> physical metric / temporal event target
```

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

The conceptual target remains:

```text
Waymo Open Dataset for molecular dynamics trajectories
```

## Current Public CLI

The public command surface is:

- `mddatanet init`
- `mddatanet inspect`
- `mddatanet prepare`
- `mddatanet analyze`
- `mddatanet tag`
- `mddatanet package`
- `mddatanet validate`
- `mddatanet publish`
- `mddatanet load`
- `mddatanet benchmark`
- `mddatanet demo`
- `mddatanet presets list/show/explain/validate-yaml`

Removed from the public architecture:

- `.mddatanet.zip` as the final dataset target
- `convert`
- `push-to-hub`
- `convert-and-tag`
- `split`
- `split-package`
- `pack`
- `unpack`
- `export-manifest`
- custom `mddn-hub` registry validation

Legacy modules may still exist temporarily for backward-looking tests or
internal reuse, but they are not the public product direction.

## Workspace Format

An active project is shaped like:

```text
project_root/
  mddatanet.yaml
  .mddn_cache/
    mddatanet.json
    dataset_card.md
    validation_report.json
    data/
      train-00000-of-00001.parquet
      validation-00000-of-00001.parquet
      test-00000-of-00001.parquet
    metadata_index/
      index-00000-of-00001.parquet
```

`mddatanet prepare` may temporarily write `shard-*.parquet` files under
`.mddn_cache/data/`. `mddatanet package` replaces those with official
Hugging Face split files.

## Core Schemas

`mddatanet.yaml` is the user-editable project descriptor. It stores dataset
identity, task, license, visibility, system metadata, simulation metadata, and
allowed event names.

`.mddn_cache/mddatanet.json` is the generated structural manifest. It stores the
MDDataNet version, dataset name, selected atom count, total frames, selection
string, force availability, timestep, duration, shard summaries, split summaries,
and analysis summaries.

Heavy Parquet rows are per-frame:

- `frame_id`
- `time_ps`
- `coordinates`
- `forces`
- `rmsd`
- `radius_of_gyration`
- `event_label`
- `event_confidence`

The remote-search split is lightweight:

- `dataset_name`
- `protein_name`
- `forcefield`
- `max_rmsd`
- `min_radius_of_gyration`
- `tagged_events`
- `hf_repo_link`

## Benchmark Task Semantics

MDDataNet datasets should explicitly define ML task semantics even when they are
published as ordinary Hugging Face datasets.

Supported task categories include:

- rare_event_prediction
- future_event_prediction
- transition_detection
- state_classification
- trajectory_forecasting
- interaction_prediction

The long-term canonical training pattern remains:

```text
frames t-W:t -> predict event in t:t+H
```

Hugging Face metadata, dataset cards, and `metadata_index` rows should make task
intent searchable by event type, metric, horizon, and molecular system.

## Architecture Rules

- Hugging Face Datasets is the canonical storage and registry target.
- Keep direct custom Hub registry code out of scope.
- Keep command functions thin; put behavior in service modules.
- Use Typer for CLI commands, Rich for terminal output, MDAnalysis for MD
  reading, Ray for required distributed prepare execution, PyArrow/Parquet for
  final data, and Hugging Face Hub APIs for publish.
- Zarr may exist only as legacy/internal scratch; the public final format is
  Parquet inside `.mddn_cache/`.
- Preserve frame ordering, run identity, trajectory identity, source frame
  identity, and temporal continuity unless explicitly requested otherwise.
- Future multi-run schemas should preserve `trajectory_ids`, `run_ids`, and
  `source_frame_indices` when row-level traceability is expanded beyond the
  current per-frame Parquet MVP.
- Design future APIs around trajectory windows:

```text
frames t-W:t -> predict event or state in t:t+H
```

## Large MD Data Rules

- Never assume trajectory data fits in RAM.
- `prepare` must shard work by frame ranges.
- Ray workers must reopen MDAnalysis Universes independently.
- Ray workers must write Parquet files directly and return only lightweight JSON
  summaries to the coordinator.
- Do not return coordinate arrays through Ray object results.
- Strip solvent by default, unless `--keep-solvent` or `--atom-selection` says
  otherwise.
- If forces are unavailable, record `has_forces: false` and write null force
  tensors rather than fake zeros.

## Testing Rules

- Use synthetic tiny arrays and generated toy trajectories in tests.
- Do not require large real MD files in CI.
- Test CLI registration, project initialization, source inspection, Ray-backed
  prepare behavior, Parquet schemas, analysis metrics, manual tagging, package
  split generation, validation reports, publish dry-runs, and demo execution.
- Keep `mddatanet demo` runtime-generated; do not commit demo datasets.

## What Is Still Needed

- Replace remaining legacy `.mddatanet.zip` internals with HF-native internals or
  remove them once no tests depend on them.
- Expand real-world ingestion validation beyond tiny generated fixtures.
- Add richer built-in event presets and metric columns.
- Add force-vector support for formats that expose forces.
- Add official benchmark task definitions and reference model baselines.
- Add HPC scheduler script generation later; it is out of scope for the current
  HF MVP.

## Final Project Positioning

MDDataNet is not merely a repository for MD simulations.

MDDataNet is a standardized benchmark and dataset ecosystem for molecular
dynamics trajectory learning.

Its purpose is to convert heterogeneous molecular dynamics simulations into
reproducible, ML-ready temporal prediction tasks using standardized per-frame
tensor storage, operational event definitions, provenance tracking, validation
reports, metadata indexing, Hugging Face dataset cards, and streaming-compatible
Parquet assets.
