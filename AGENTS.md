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
- `mddatanet split`
- `mddatanet validate`
- `mddatanet inspect`
- `mddatanet pack`
- `mddatanet unpack`
- `mddatanet card`
- `mddatanet export-manifest`
- `mddatanet demo`
- `mddatanet presets list/show/explain`

The current pipeline can:

- convert MDAnalysis-readable raw data into `.mddatanet/` or `.mddatanet.zip`
  packages;
- ingest repeated `--trajectory` inputs as multi-run packages;
- store per-frame `run_ids`, `trajectory_ids`, and `source_frame_indices`;
- store raw positions only when requested via `--store-positions`;
- compute first-pass features such as distance, min distance, contact,
  contact count, dihedral, RMSD, radius of gyration, and native contact
  fraction;
- apply custom event YAML or built-in presets such as `ligand_unbinding`;
- generate `event_now`, inclusive `event_future_H`, and `time_to_event`;
- split temporally, randomly, or by trajectory/run IDs;
- validate package structure, schemas, array lengths, splits, run records, and
  checksums;
- inspect package summaries;
- run a runtime-generated ligand unbinding demo without committed demo data;
- export Hub-ready registry metadata files.

## Current Package Format

An unpacked package should be shaped like:

```text
dataset.mddatanet/
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

Not every file exists at every stage. A raw converted package may not yet have
features, labels, events, or splits.

Important Zarr arrays include:

- `arrays/frame_indices`
- `arrays/source_frame_indices`
- `arrays/frame_times`
- `arrays/trajectory_ids`
- `arrays/run_ids`
- `arrays/atom_names`
- `arrays/residue_ids`
- `arrays/residue_names`
- `arrays/positions`, optional
- `features/{feature_name}`
- `labels/{event_name}/event_now`
- `labels/{event_name}/event_future_{horizon}`
- `labels/{event_name}/time_to_event`
- `splits/train`
- `splits/val`
- `splits/test`
- `index/feature_names`
- `index/event_names`

## Hub Registry Format

`mddatanet export-manifest` should produce a small Hub registry folder:

```text
dataset_id/
  metadata.json
  dataset_card.md
  checksums.json
  manifest.json
  download.yaml
```

The Hub repo should not store huge `.mddatanet.zip` files. It should store
metadata, manifests, dataset cards, checksums, citations, optional baseline
metrics, and download instructions.

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

## Architecture Rules

- Keep the CLI useful without MDDataNet Hub.
- Keep Hub upload/download commands out of scope until explicitly requested.
- Keep command functions thin; put real behavior in service modules.
- Prefer Typer for CLI commands, Rich for terminal output, Pydantic for schemas,
  MDAnalysis for MD loading, Zarr for array storage, PyYAML for config parsing,
  and NumPy for numerical work.
- Keep modules small and testable.
- Preserve backward compatibility for CLI flags unless a change is unavoidable.
- Keep scientific labels framed as reproducible operational labels, not
  universal biological truths.

## Large MD Data Rules

- Never assume trajectory data fits in RAM.
- Use streaming file operations for checksums, pack/unpack, and source
  inspection.
- Use chunked Zarr writes for large arrays.
- Prefer unpacked `.mddatanet/` directories during active processing of huge
  data; use `.mddatanet.zip` for sharing/export.
- Store raw positions only when explicitly requested, and always with chunking.
- Validate package structure and array shapes without materializing full arrays.
- Generate labels in chunks where possible. Future-event and time-to-event
  labels may require reverse scans; do not load raw MD coordinates to do this.
- Keep distance/contact calculations blockwise for large selections.
- Multi-run packages require one shared topology and atom ordering unless a
  future design explicitly supports heterogeneous systems.

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
- [x] Improve stored-position featurization so all feature types work from
  `arrays/positions`, including PBC support via stored `dimensions`.
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
- [ ] Validate that future labels match horizon semantics more deeply.
- [x] Add window extraction utilities for downstream ML training (`mddatanet.utils.windows`).
- [ ] Add optional baseline metrics generation later.

Hub-readiness work (NEXT PHASE):

- [ ] Stabilize `manifest.json` and `download.yaml` schemas.
- [x] Add JSON Schema exports for Hub CI (`export-schema`).
- [ ] Add `citation.bib` and `baseline_metrics.json` support in manifest export.
- [ ] Add URL/checksum verification for external downloads.
- [ ] Build `mddatanet-hub` as a separate metadata registry repository.

Documentation and packaging work:

- Expand README with a real installation section, quickstart, custom YAML
  examples, preset examples, package format docs, Hub registry workflow, and
  contribution guide.
- Add API docs for Python users.
- Add CI for tests, linting, and package build.
- Add release workflow for PyPI once the API stabilizes.
- Add a changelog and semantic versioning policy.

Scientific/product work:

- Clarify that MDDataNet standardizes operational tasks and reproducible labels,
  not universal scientific truth.
- Define official benchmark split policies for common MD task families.
- Decide which dataset licenses are acceptable for Hub inclusion.
- Decide required metadata fields for curated Hub approval.
- Add responsible-use language to dataset cards.

